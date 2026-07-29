#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06_compara_curvas.py
====================
SOBREPÕE as curvas medianas r_e(T)/BTD de vários casos num gráfico só —
o confronto direto toró-sem-FD vs. pós-FD vs. controles.

As curvas vêm dos CSVs `curva_*.csv` que o 04 salva em cada saida_<caso>/.
(Rode o 04 de novo nos casos antigos se os CSVs ainda não existirem.)

Uso:
  python 06_compara_curvas.py saida_Toro_01-02mai/curva_2024-05-02_0200UT.csv \\
                              saida_Cheia12mai_noite/curva_2024-05-12_0600UT.csv
  python 06_compara_curvas.py "saida_*/curva_*.csv"          # tudo (glob)
  python 06_compara_curvas.py ... --saida comparacao.png

CUIDADO metodológico: só compare curvas do MESMO regime (noturno com
noturno, diurno com diurno) — a física do BTD muda entre dia e noite.
"""

import argparse
import glob
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("csvs", nargs="+", help="CSVs de curva (aceita glob)")
    ap.add_argument("--saida", default="comparacao_curvas.png")
    ap.add_argument("--n-min", type=int, default=200,
                    help="ignora curvas com menos pixels que isso")
    a = ap.parse_args()

    arquivos = []
    for padrao in a.csvs:
        arquivos += glob.glob(padrao)
    if not arquivos:
        raise SystemExit("Nenhum CSV encontrado. Rode o 04 primeiro.")

    fig, ax = plt.subplots(figsize=(8.5, 7))
    cores = plt.cm.tab10.colors
    i = 0
    regimes = set()
    for f in sorted(set(arquivos)):
        df = pd.read_csv(f)
        n = int(df.n_pixels.iloc[0])
        if n < a.n_min:
            print(f"  pulando {f} (N={n} < {a.n_min})")
            continue
        regime = df.regime.iloc[0] if "regime" in df.columns else "?"
        if regime == "crepusculo":
            print(f"  pulando {f} (CREPÚSCULO — 3,9um contaminada pelo sol)")
            continue
        regimes.add(regime)
        estilo = "-o" if regime == "noturno" else "--s"
        rotulo = f"{df.caso.iloc[0]} {df.quando.iloc[0]} [{regime}] (N={n})"
        ax.plot(df.mediana, df.T_bin + 2.5, estilo, ms=4, lw=1.8,
                color=cores[i % 10], label=rotulo)
        i += 1
    if len(regimes - {"?"}) > 1:
        print("\n  ATENÇÃO: curvas de regimes DIFERENTES no mesmo gráfico "
              "(noturno=linha cheia, diurno=tracejada). Não compare entre si!")
    ax.axhline(-20, color="purple", ls="--", lw=1, label="-20 C (limiar SLW)")
    ax.invert_yaxis()
    ax.set_xlabel("proxy r_e / BTD (não calibrado — comparação relativa)")
    ax.set_ylabel("Temperatura do topo (C)")
    ax.set_title("Curvas medianas r_e(T) — comparação entre casos\n"
                 "(compare só mesmo regime: noite c/ noite, dia c/ dia)")
    ax.legend(fontsize=7, loc="best")
    ax.grid(alpha=0.25)
    plt.tight_layout(); plt.savefig(a.saida, dpi=150)
    print("Figura salva:", a.saida)

if __name__ == "__main__":
    main()
