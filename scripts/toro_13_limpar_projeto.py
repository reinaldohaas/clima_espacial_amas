#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
13_limpar_projeto.py
====================
LIMPEZA do projeto — apaga o que não é mais necessário, com segurança:
por padrão só LISTA (dry-run); nada é apagado sem --confirmar.

Categorias:
  SEMPRE (com --confirmar):
    - __pycache__/ (regenerável)
    - arquivos temporários do Word (~$*.docx)
    - rio_taquari_antas.geojson da RAIZ (duplicata exata de dados_geo/;
      o 00_caso.py usa a cópia de dados_geo/)
    - resultados/graficos_antigos_raiz/ (PNGs da janela curta, supersedidos
      pelos de resultados/solar_espacial_desde0104/)
  OPCIONAL (--propostas-antigas):
    - docs/propostas/proposta_MR_CPAM.docx, _v2, _v3 (mantém a v4)

NUNCA apaga: dados_* (caches caros de rebaixar), resultados/controles/
(baseline de março — o caso usa como controle), resultados/sismica/,
resultados/evento_desde2704/, docs/.

Uso:
  python 13_limpar_projeto.py                     # só mostra o que faria
  python 13_limpar_projeto.py --confirmar         # apaga o padrão
  python 13_limpar_projeto.py --confirmar --propostas-antigas
"""

import argparse
import shutil
from pathlib import Path

AQUI = Path(__file__).resolve().parents[1]

def alvos(propostas_antigas=False):
    itens = []
    # busca rasa (não varre os caches dados_*, que são enormes)
    for base in (AQUI, AQUI / "docs", AQUI / "docs" / "propostas",
                 AQUI / "resultados"):
        if base.exists():
            itens += [p for p in base.glob("__pycache__")]
            itens += [p for p in base.glob("~$*.docx")]
    dup = AQUI / "rio_taquari_antas.geojson"
    if dup.exists() and (AQUI / "dados/geo" / "rio_taquari_antas.geojson").exists():
        itens.append(dup)
    ga = AQUI / "resultados" / "graficos_antigos_raiz"
    if ga.exists():
        itens.append(ga)
    if propostas_antigas:
        for v in ("proposta_MR_CPAM.docx", "proposta_MR_CPAM_v2.docx",
                  "proposta_MR_CPAM_v3.docx"):
            f = AQUI / "docs" / "propostas" / v
            if f.exists():
                itens.append(f)
    return itens

def tamanho(p):
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return p.stat().st_size

def main():
    ap = argparse.ArgumentParser(description="Limpeza segura do projeto")
    ap.add_argument("--confirmar", action="store_true",
                    help="apaga de verdade (sem isso, só lista)")
    ap.add_argument("--propostas-antigas", action="store_true",
                    help="inclui propostas v1-v3 (mantém a v4)")
    a = ap.parse_args()

    itens = alvos(a.propostas_antigas)
    if not itens:
        print("Nada a limpar."); return
    total = 0
    for p in itens:
        t = tamanho(p); total += t
        print(f"  {'[DIR] ' if p.is_dir() else '      '}"
              f"{p.relative_to(AQUI)}  ({t/1024:.0f} kB)")
    print(f"\nTotal: {total/1e6:.1f} MB em {len(itens)} item(ns).")
    if not a.confirmar:
        print("Dry-run — nada foi apagado. Rode com --confirmar para apagar.")
        return
    for p in itens:
        try:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
            print("apagado:", p.relative_to(AQUI))
        except Exception as e:
            print(f"!! falhou {p}: {e}")

if __name__ == "__main__":
    main()
