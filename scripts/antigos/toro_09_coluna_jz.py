#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
09_coluna_jz.py
===============
A COLUNA DO Jz: linha do tempo empilhada das perturbações, andar por andar,
da ionosfera à baixa troposfera — sobre a AMAS.

MOTIVAÇÃO (correção do Reinaldo): nêutrons/múons medem só o ANDAR DE BAIXO
(ionização troposférica por GCR -> resistência colunar). O Jz responde à
coluna inteira: região F (potencial/TEC), região D sobre a AMAS (precipitação
do cinturão interno + prótons solares -> condutividade), e o andar de baixo.
Cada camada tem seu instrumento; este script as empilha no tempo.

CAMADAS (de cima para baixo):
  1. Driver geomagnético : Kp (GFZ, API pública) + Dst (Kyoto WDC)  [AUTO]
  2. Região F            : anomalia de TEC — CSV do script 03       [você]
  3. Região D / AMAS     : VLF SAVNET ou riômetro — CSV             [você]
  4. Baixo (0-25 km)     : nêutrons NMDB (script 01) ou múons SMS   [AUTO/você]

CSVs opcionais (colunas: tempo,valor — header livre, 1ª col vira datetime):
  --tec anomalia_tec.csv   --vlf savnet.csv   --muon sms.csv

Uso:
  python 09_coluna_jz.py                          # Kp+Dst+nêutrons, maio/24
  python 09_coluna_jz.py --tec tec.csv --vlf vlf.csv
"""

import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent

MARCOS = [
    ("2024-05-01 18:00", "toró 01-02/mai (pico ~20-00 UT)", "green"),
    ("2024-05-08 22:36", "CME lançado", "orange"),
    ("2024-05-10 17:05", "SSC — CME chega", "red"),
    ("2024-05-11 03:00", "GLE74 (prótons solares)", "blue"),
    ("2024-05-12 06:00", "cheia máxima RS", "darkgreen"),
]

def _carregar(nome, alias):
    spec = importlib.util.spec_from_file_location(alias, AQUI / nome)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def baixar_kp(ini, fim):
    """Kp definitivo do GFZ (API JSON pública, sem chave)."""
    import requests
    url = ("https://kp.gfz-potsdam.de/app/json/?start="
           f"{ini}T00:00:00Z&end={fim}T23:59:59Z&index=Kp")
    j = requests.get(url, timeout=60).json()
    return pd.DataFrame(dict(tempo=pd.to_datetime(j["datetime"]),
                             kp=j["Kp"]))

def baixar_dst(ini, fim):
    """Dst horário do WDC Kyoto. Tenta index.html e o ASCII .for.request;
    limpa tags HTML antes de parsear. Formato WDC: 'DSTyyMM*DD...' com 24
    valores de 4 dígitos a partir da coluna 21."""
    import re
    import requests
    dfs = []
    for mes in pd.period_range(ini, fim, freq="M"):
        linhas = []
        urls = []
        for base in ("dst_final", "dst_provisional", "dst_realtime"):
            d = f"{mes.year}{mes.month:02d}"
            urls += [f"https://wdc.kugi.kyoto-u.ac.jp/{base}/{d}/index.html",
                     f"https://wdc.kugi.kyoto-u.ac.jp/{base}/{d}/"
                     f"dst{str(mes.year)[2:]}{mes.month:02d}.for.request"]
        for url in urls:
            try:
                txt = requests.get(url, timeout=60).text
                txt = re.sub(r"<[^>]+>", "", txt)      # remove tags HTML
                linhas = [l for l in txt.splitlines()
                          if l.startswith("DST") and len(l) >= 116]
                if linhas:
                    break
            except Exception:
                continue
        if not linhas:
            print(f"  Dst: nada parseável p/ {mes} (última URL: {url})")
        for l in linhas:
            try:
                dia = int(l[8:10])
                base_t = pd.Timestamp(mes.year, mes.month, dia)
            except ValueError:
                continue
            for h in range(24):
                v = l[20 + 4 * h:24 + 4 * h]
                try:
                    x = float(v)
                    if abs(x) < 9998:                  # 9999 = faltante
                        dfs.append((base_t + pd.Timedelta(hours=h), x))
                except ValueError:
                    pass
    df = pd.DataFrame(dfs, columns=["tempo", "dst"]).sort_values("tempo")
    return df[(df.tempo >= ini) & (df.tempo <= fim)]

def ler_csv_camada(caminho):
    df = pd.read_csv(caminho, sep=None, engine="python")
    df.columns = ["tempo", "valor"] + list(df.columns[2:])
    df["tempo"] = pd.to_datetime(df["tempo"])
    return df

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("--ini", default="2024-04-25")
    ap.add_argument("--fim", default="2024-05-16")
    ap.add_argument("--tec", help="CSV anomalia de TEC (script 03)")
    ap.add_argument("--vlf", help="CSV VLF/SAVNET ou riômetro (região D/AMAS)")
    ap.add_argument("--muon", help="CSV múons São Martinho (OES/INPE)")
    ap.add_argument("--saida", default="coluna_jz.png")
    a = ap.parse_args()

    camadas = []   # (rotulo, df, cor, tipo)

    try:
        kp = baixar_kp(a.ini, a.fim)
        camadas.append(("Kp (driver geomagnético)", kp.rename(
            columns={"kp": "valor"}), "tab:red", "bar"))
    except Exception as e:
        print("!! Kp falhou:", e)
    try:
        dst = baixar_dst(a.ini, a.fim)
        if len(dst):
            camadas.append(("Dst (nT) — anel de corrente", dst.rename(
                columns={"dst": "valor"}), "tab:purple", "linha"))
        else:
            print("!! Dst veio VAZIO — camada descartada (veja mensagens acima)")
    except Exception as e:
        print("!! Dst falhou:", e)
    if a.tec:
        camadas.append(("Anomalia TEC — região F (AMAS)",
                        ler_csv_camada(a.tec), "tab:orange", "linha"))
    if a.vlf:
        camadas.append(("VLF/riômetro — região D (AMAS)",
                        ler_csv_camada(a.vlf), "tab:brown", "linha"))
    try:
        m1 = _carregar("01_timeline_may2024.py", "t01")
        nm = m1.baixar_nmdb_multi(a.ini, a.fim, ["IRK3", "MXCO"])
        for e in ("IRK3", "MXCO"):
            if e in nm and not nm[e].isna().all():
                b = nm.loc[nm.tempo < nm.tempo.min() + pd.Timedelta(days=2), e].mean()
                nm[e] = 100 * (nm[e] - b) / b
                nm[e] = nm[e].where(nm[e] > -15)   # spikes instrumentais
        # painel duplo: IRK3 (corte baixo, sensível) + MXCO (corte ~RS)
        nm["valor"] = nm["MXCO"]
        if "IRK3" in nm and not nm["IRK3"].isna().all():
            nm["valor2"] = nm["IRK3"]
        camadas.append(("GCR %: cinza=MXCO (~RS), azul=IRK3 (sensível) — andar de baixo",
                        nm, "tab:gray", "linha2"))
    except Exception as e:
        print("!! NMDB falhou:", e)
    if a.muon:
        camadas.append(("Múons São Martinho — andar de baixo (AMAS!)",
                        ler_csv_camada(a.muon), "black", "linha"))

    if not camadas:
        raise SystemExit("Nenhuma camada disponível.")

    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(len(camadas), 1, figsize=(13, 2.3 * len(camadas)),
                            sharex=True)
    axs = np.atleast_1d(axs)
    for ax, (rot, df, cor, tipo) in zip(axs, camadas):
        if tipo == "bar":
            ax.bar(df.tempo, df.valor, width=0.11, color=cor, alpha=0.8)
        elif tipo == "linha2":
            ax.plot(df.tempo, df.valor, color=cor, lw=1.2)
            if "valor2" in df.columns:
                ax.plot(df.tempo, df.valor2, color="tab:blue", lw=0.8, alpha=0.7)
        else:
            ax.plot(df.tempo, df.valor, color=cor, lw=1)
        ax.set_ylabel(rot, fontsize=8)
        for t, lab, c in MARCOS:
            ax.axvline(pd.to_datetime(t), color=c, lw=1.2, alpha=0.7)
    for t, lab, c in MARCOS:
        axs[0].annotate(lab, (pd.to_datetime(t), axs[0].get_ylim()[1]),
                        rotation=90, fontsize=7, color=c, va="top", ha="right")
    axs[-1].set_xlim(pd.to_datetime(a.ini), pd.to_datetime(a.fim))
    axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    axs[0].set_title("A coluna do Jz — perturbações andar por andar (AMAS), "
                     f"{a.ini} a {a.fim}")
    plt.tight_layout(); plt.savefig(a.saida, dpi=150)
    print("Figura salva:", a.saida)
    print("\nCamadas que faltam (fontes p/ pedir/baixar):")
    print("  VLF região D : SAVNET (CRAAM/Mackenzie) — dado sob pedido")
    print("  Digissonda   : EMBRACE/INPE Santa Maria (foF2, h'F)")
    print("  Múons        : Observatório Espacial do Sul (São Martinho/INPE)")
    print("  TEC          : script 03 + portal EMBRACE")

if __name__ == "__main__":
    main()
