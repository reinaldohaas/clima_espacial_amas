# -*- coding: utf-8 -*-
"""Funde Eventos_toro dentro de clima_espacial_amas, organizando POR FUNCAO.

    python migrar.py                 -> DRY-RUN: so imprime o que faria
    python migrar.py --executar      -> executa de verdade

Estrutura final:
    clima_espacial_amas/
      scripts/     todo o codigo .py dos dois projetos (os do toro com prefixo toro_)
      notebooks/   nb01..nb04
      tools/       utilitarios
      dados/       TODAS as entradas
      resultados/  TODAS as saidas
      docs/        documentos e guias

Nada e apagado: tudo e MOVIDO. Se um destino ja existir, o item e reportado como
colisao e NAO e movido. Ao final o Eventos_toro fica vazio e voce apaga a pasta.
"""
import argparse, os, re, shutil, sys
from pathlib import Path

# ---------------------------------------------------------------- movimentos
# (origem relativa a raiz de origem, destino relativo a raiz do amas)
MOV_AMAS_DIR = [
    ("dados", "dados/amas"),
    ("dados_2023_completo", "dados/magnetometros_2023"),
    ("dados_2024_completo", "dados/magnetometros_2024"),
    ("cache_abi", "dados/cache_abi"),
    ("graficos", "resultados/graficos"),
    ("graficos_todas_estacoes", "resultados/graficos_estacoes"),
]
MOV_AMAS_GLOB = [
    ("*.py", "scripts"),
    ("nb0*.ipynb", "notebooks"),
    ("rede_*.csv", "dados/jz"),
    ("resumo_cobertura*.csv", "dados/jz"),
    ("*.gif", "resultados"),
    ("LEIA-ME_dados.md", "docs"),
    ("Fundamentacao_*.docx", "docs"),
]
MOV_TORO_DIR = [
    ("dados_era5", "dados/era5"), ("dados_geo", "dados/geo"),
    ("dados_geomag", "dados/geomag"), ("dados_gnss", "dados/gnss"),
    ("dados_goes", "dados/goes"), ("dados_goesp", "dados/goesp"),
    ("dados_magnet", "dados/magnet"), ("dados_muons", "dados/muons"),
    ("dados_nmdb", "dados/nmdb"), ("dados_tec", "dados/tec"),
    ("dados_sondagens", "dados/sondagens"),
]
MOV_TORO_GLOB = [
    ("saida_*", "resultados/saidas_toro"),
    ("*.png", "resultados"),
    ("*.csv", "resultados"),
    ("GUIA_SCRIPTS.*", "docs"),
]

# ---------------------------------------------------------------- reescritas
# literais COM as aspas, para nao casar prefixo de nome maior
REESC_TORO = [
    (".resolve().parent", ".resolve().parents[1]"),
    ('"dados_era5"', '"dados/era5"'), ('"dados_geo"', '"dados/geo"'),
    ('"dados_geomag"', '"dados/geomag"'), ('"dados_gnss"', '"dados/gnss"'),
    ('"dados_goes"', '"dados/goes"'), ('"dados_goesp"', '"dados/goesp"'),
    ('"dados_magnet"', '"dados/magnet"'), ('"dados_muons"', '"dados/muons"'),
    ('"dados_nmdb"', '"dados/nmdb"'), ('"dados_tec"', '"dados/tec"'),
    ('"dados_sondagens"', '"dados/sondagens"'),
]
REESC_AMAS = [
    ('"dados_2024_completo"', '"dados/magnetometros_2024"'),
    ('"dados_2023_completo"', '"dados/magnetometros_2023"'),
    ('"graficos_todas_estacoes"', '"resultados/graficos_estacoes"'),
    ('"graficos"', '"resultados/graficos"'),
    ('"cache_abi"', '"dados/cache_abi"'),
    ('"rede_completa_14_estacoes_currents_2024.csv"',
     '"dados/jz/rede_completa_14_estacoes_currents_2024.csv"'),
    ('"rede_multiestacoes_currents_2024.csv"',
     '"dados/jz/rede_multiestacoes_currents_2024.csv"'),
    ('"resumo_cobertura_19_estacoes_2024.csv"',
     '"dados/jz/resumo_cobertura_19_estacoes_2024.csv"'),
]
# literais ambiguos: NAO reescrever, so reportar para revisao manual
SUSPEITOS = ['"dados"', "'dados'"]

CELULA_SHIM = """import os, sys, pathlib
RAIZ = pathlib.Path.cwd()
while not (RAIZ / 'scripts').is_dir() and RAIZ != RAIZ.parent:
    RAIZ = RAIZ.parent
os.chdir(RAIZ)
sys.path.insert(0, str(RAIZ / 'scripts'))
print('raiz do projeto:', RAIZ)"""

acoes, colisoes, avisos = [], [], []


def mover(src: Path, dst: Path, executar: bool):
    if not src.exists():
        return
    if dst.exists():
        colisoes.append("%s  ->  %s (destino ja existe)" % (src.name, dst))
        return
    acoes.append("mover   %-46s -> %s" % (src.name, dst))
    if executar:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dentro = str(dst).startswith(str(src) + os.sep)
        if dentro:
            tmp = src.parent / ("_mig_tmp_" + src.name)
            os.replace(src, tmp)
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(tmp, dst)
        else:
            try:
                os.replace(src, dst)
            except OSError:
                shutil.move(str(src), str(dst))


def funde_dir(src: Path, dst: Path, executar: bool):
    """Move o CONTEUDO de src para dst, item a item (dst pode ja existir)."""
    if not src.is_dir():
        return
    for item in sorted(src.iterdir()):
        alvo = dst / item.name
        if alvo.exists():
            if item.is_file() and alvo.is_file() and item.stat().st_size == alvo.stat().st_size:
                avisos.append("identico dos dois lados, mantido um so: %s" % item.name)
                acoes.append("duplicado -> _para_apagar/  %s" % item.name)
                if executar:
                    lixo = dst.parent / "_para_apagar"
                    lixo.mkdir(parents=True, exist_ok=True)
                    os.replace(item, lixo / ("toro_" + item.name))
            else:
                colisoes.append("%s -> %s (destino ja existe)" % (item, alvo))
            continue
        acoes.append("mover   %-46s -> %s" % (item.name, alvo))
        if executar:
            dst.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(item, alvo)
            except OSError:
                shutil.move(str(item), str(alvo))


def reescreve(caminho: Path, regras, executar: bool):
    txt = caminho.read_text(encoding="utf-8", errors="surrogateescape")
    orig, n = txt, 0
    for velho, novo in regras:
        c = txt.count(velho)
        if c:
            txt = txt.replace(velho, novo)
            n += c
    for s in SUSPEITOS:
        if s in orig:
            avisos.append("REVISAR A MAO: %s contem o literal %s" % (caminho.name, s))
    if n:
        acoes.append("editar  %-46s %d substituicao(oes)" % (caminho.name, n))
        if executar:
            caminho.write_text(txt, encoding="utf-8", errors="surrogateescape")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amas", default=r"C:\Users\haas\github\clima_espacial_amas")
    ap.add_argument("--toro", default=r"C:\Users\haas\github\Eventos_toro")
    ap.add_argument("--executar", action="store_true")
    a = ap.parse_args()
    A, T = Path(a.amas), Path(a.toro)
    exe = a.executar
    if not A.is_dir():
        sys.exit("ERRO: nao achei %s" % A)
    if not T.is_dir():
        sys.exit("ERRO: nao achei %s" % T)

    print("=" * 78)
    print("MODO: %s" % ("EXECUCAO" if exe else "DRY-RUN (nada sera alterado)"))
    print("amas: %s\ntoro: %s" % (A, T))
    print("=" * 78)

    # ---- 1. backup dos scripts do toro (nao e repo git, nao tem historico)
    bkp = A / "_backup_toro_scripts"
    if exe:
        bkp.mkdir(exist_ok=True)
    for p in sorted(T.glob("*.py")) + sorted(T.glob("scripts_antigos/*.py")):
        acoes.append("copiar  %-46s -> _backup_toro_scripts/" % p.name)
        if exe:
            shutil.copy2(p, bkp / p.name)

    # ---- 2. AMAS: pastas e arquivos
    for o, d in MOV_AMAS_DIR:
        mover(A / o, A / d, exe)
    for padrao, destino in MOV_AMAS_GLOB:
        for p in sorted(A.glob(padrao)):
            if p.is_file():
                mover(p, A / destino / p.name, exe)

    # ---- 3. TORO: scripts com prefixo toro_
    renomeados = {}
    for p in sorted(T.glob("*.py")):
        novo = "toro_" + p.name
        renomeados[p.name] = novo
        mover(p, A / "scripts" / novo, exe)
    for p in sorted(T.glob("scripts_antigos/*.py")):
        mover(p, A / "scripts" / "antigos" / ("toro_" + p.name), exe)

    # ---- 4. TORO: dados, saidas, docs, resultados
    for o, d in MOV_TORO_DIR:
        mover(T / o, A / d, exe)
    for padrao, destino in MOV_TORO_GLOB:
        for p in sorted(T.glob(padrao)):
            mover(p, A / destino / p.name, exe)
    funde_dir(T / "resultados", A / "resultados", exe)
    funde_dir(T / "docs", A / "docs", exe)
    mover(T / "README.md", A / "docs" / "README_toro.md", exe)
    mover(T / ".gitignore", A / "docs" / "gitignore_toro.txt", exe)

    # ---- 5. reescrita dos caminhos
    regras_toro = list(REESC_TORO) + [
        ('"%s"' % velho, '"%s"' % novo) for velho, novo in renomeados.items()]
    for p in sorted((A / "scripts").glob("toro_*.py")):
        reescreve(p, regras_toro, exe)
    for p in sorted((A / "scripts").glob("*.py")):
        if not p.name.startswith("toro_"):
            reescreve(p, REESC_AMAS, exe)

    # ---- 6. shim nos notebooks
    import json
    for p in sorted((A / "notebooks").glob("*.ipynb")):
        nb = json.loads(p.read_text(encoding="utf-8"))
        if nb["cells"] and "RAIZ = pathlib.Path.cwd()" in "".join(nb["cells"][0]["source"]):
            continue
        acoes.append("editar  %-46s celula de raiz do projeto no topo" % p.name)
        if exe:
            nb["cells"].insert(0, {"cell_type": "code", "metadata": {},
                                   "execution_count": None, "outputs": [],
                                   "source": CELULA_SHIM.splitlines(keepends=True)})
            p.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")

    # ---- relatorio
    print("\n--- ACOES (%d) ---" % len(acoes))
    for x in acoes:
        print("  " + x)
    if avisos:
        print("\n--- AVISOS (%d) ---" % len(avisos))
        for x in sorted(set(avisos)):
            print("  " + x)
    if colisoes:
        print("\n--- COLISOES, NAO MOVIDO (%d) ---" % len(colisoes))
        for x in colisoes:
            print("  " + x)
    if exe:
        for p in sorted(T.rglob("__pycache__"), key=lambda q: -len(str(q))):
            shutil.rmtree(p, ignore_errors=True)
        for _ in range(4):
            for p in sorted(T.rglob("*"), key=lambda q: -len(str(q))):
                if p.is_dir():
                    try:
                        p.rmdir()
                    except OSError:
                        pass
        resto = [p.name for p in T.iterdir()]
        print("\n--- SOBROU EM %s (%d) ---" % (T.name, len(resto)))
        for x in sorted(resto):
            print("  " + x)
        if not resto:
            print("  (vazio) -> pode apagar a pasta %s" % T)
        else:
            print("  NAO apague ainda: reveja os itens acima.")
    else:
        print("\nDRY-RUN: nada foi alterado. Rode de novo com --executar.")


if __name__ == "__main__":
    main()
