#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exporta_kp_dst_2024.py
======================
Separa as séries de Kp (GFZ Potsdam) e Dst (WDC Kyoto) do ANO de 2024 e grava
um CSV horário. Reusa os downloaders CACHE-PRIMEIRO do 01_series_espaciais
(mesmo cache dados_geomag/ — só baixa os meses que faltam, nada é rebaixado).

Uso:
  python exporta_kp_dst_2024.py                        # ano inteiro 2024
  python exporta_kp_dst_2024.py --ini 2024-01-01 --fim 2024-12-31
  python exporta_kp_dst_2024.py --saida meu_arquivo.csv

Saída padrão: resultados/kp_dst_2024.csv
  colunas: datetime_utc, Kp, Dst_nT
  - Dst é horário nativo (WDC Kyoto).
  - Kp é de 3 em 3 h (GFZ); na grade horária é repetido dentro de cada bloco
    de 3 h (valor constante no bloco). Se quiser só os instantes nativos do Kp,
    filtre as linhas onde datetime_utc.hour % 3 == 0.

Fontes: Kp — https://kp.gfz-potsdam.de/ (CC BY 4.0); Dst — WDC Kyoto,
https://wdc.kugi.kyoto-u.ac.jp/
"""
import argparse
import importlib.util
import pathlib

import pandas as pd

AQUI = pathlib.Path(__file__).resolve().parents[1]


def _mod(nome, alias):
    spec = importlib.util.spec_from_file_location(alias, AQUI / nome)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser(description="Exporta Kp+Dst de 2024 para CSV")
    ap.add_argument("--ini", default="2024-01-01")
    ap.add_argument("--fim", default="2024-12-31")
    ap.add_argument("--saida", default=None)
    a = ap.parse_args()

    s = _mod("toro_01_series_espaciais.py", "s01")   # reusa kp_gfz / dst_kyoto
    print(f">> Kp (GFZ) e Dst (Kyoto) de {a.ini} a {a.fim} — cache primeiro")
    kp = s.kp_gfz(a.ini, a.fim).rename(columns={"v": "Kp"})
    dst = s.dst_kyoto(a.ini, a.fim).rename(columns={"v": "Dst_nT"})

    # grade horária de todo o intervalo
    idx = pd.date_range(a.ini,
                        pd.to_datetime(a.fim) + pd.Timedelta(hours=23),
                        freq="h")
    d = (dst.drop_duplicates("tempo").set_index("tempo")["Dst_nT"]
         .reindex(idx))
    # Kp (3 h) repetido dentro do bloco de 3 h (ffill no máx. 2 horas)
    k = (kp.drop_duplicates("tempo").set_index("tempo")["Kp"]
         .reindex(idx, method="ffill", limit=2))

    out = pd.DataFrame({"datetime_utc": idx, "Kp": k.values,
                        "Dst_nT": d.values})
    OUT = AQUI / "resultados"
    OUT.mkdir(exist_ok=True)
    f = pathlib.Path(a.saida) if a.saida else OUT / "kp_dst_2024.csv"
    out.to_csv(f, index=False)
    print(f"[OK] {len(out)} linhas -> {f}")
    print(f"     Kp: {out.Kp.notna().sum()} válidos "
          f"(min {out.Kp.min():.1f}, máx {out.Kp.max():.1f})")
    print(f"     Dst: {out.Dst_nT.notna().sum()} válidos "
          f"(min {out.Dst_nT.min():.0f}, máx {out.Dst_nT.max():.0f} nT)")


if __name__ == "__main__":
    main()
