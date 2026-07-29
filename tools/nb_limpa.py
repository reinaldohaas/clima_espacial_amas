"""Filtro de limpeza de notebooks para o git (ver .gitattributes).

Le um .ipynb na entrada padrao e escreve na saida padrao a mesma coisa sem as
saidas das celulas e sem os contadores de execucao. Serve para que o commit
guarde so o codigo: as saidas embutidas (imagens em base64) inflam o historico
- o nb04 chegou a 24,8 MB por causa disso.

Uso manual, se preferir sem o filtro do git:
    python tools/nb_limpa.py --inplace nb04_vpi.ipynb
"""
import io, json, sys


def limpa(nb):
    for c in nb.get("cells", []):
        if c.get("cell_type") == "code":
            c["outputs"] = []
            c["execution_count"] = None
        c.get("metadata", {}).pop("execution", None)
    nb.get("metadata", {}).pop("widgets", None)
    return nb


def main():
    if "--inplace" in sys.argv:
        for p in sys.argv[sys.argv.index("--inplace") + 1:]:
            with io.open(p, encoding="utf-8") as f:
                nb = limpa(json.load(f))
            with io.open(p, "w", encoding="utf-8", newline="\n") as f:
                json.dump(nb, f, ensure_ascii=False, indent=1)
                f.write("\n")
            print("limpo:", p)
        return
    nb = limpa(json.load(io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")))
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")
    json.dump(nb, out, ensure_ascii=False, indent=1)
    out.write("\n")
    out.flush()


if __name__ == "__main__":
    main()
