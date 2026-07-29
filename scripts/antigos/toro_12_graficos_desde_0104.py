#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
12_graficos_desde_0104.py
=========================
Figuras dos módulos 01 (timeline GCR), 03 (TEC) e 09 (coluna do Jz)
no período estendido 01/04–16/05/2024, usando CACHES LOCAIS:
  dados_nmdb/    OULU (1h), IRK3 e MXCO (3h) — % de desvio (NMDB nest)
  dados_geomag/  Kp (GFZ) + Dst (WDC Kyoto, provisório)
  dados_tec/     IONEX EMBRACE já baixados (10-16/04 e 08-14/05; o resto
                 do período precisa de rede — baixe com o 03)

Saídas em resultados/desde_0104/. Rode simplesmente:
    python 12_graficos_desde_0104.py
"""

import importlib.util
import pathlib

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

AQUI = pathlib.Path(__file__).resolve().parent

def _mod(nome, alias):
    spec = importlib.util.spec_from_file_location(alias, AQUI / nome)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

caso = _mod("00_caso.py", "caso")
m03 = _mod("03_gnss_tec.py", "m03")

OUT = AQUI / "resultados" / "solar_espacial_desde0104"
OUT.mkdir(parents=True, exist_ok=True)

MARCOS = [
    ("2024-04-27 00:00", "INÍCIO DAS CHUVAS (27/04)", "teal"),
    ("2024-05-03 02:00", "TORÓ (02 UT 03/05)", "green"),
    ("2024-05-08 22:36", "CME geoefetivo lançado", "orange"),
    ("2024-05-10 17:05", "SSC — CME chega à Terra", "red"),
    ("2024-05-11 00:00", "Mínimo do Forbush", "purple"),
    ("2024-05-11 03:00", "GLE74", "blue"),
]
# sismos RSBR/USP 13/05 (origem UT): jjjl 04:48, jjlb 05:37, jjlt 05:58, jjlx 06:03
SISMOS = ["2024-05-13 04:48", "2024-05-13 05:37",
          "2024-05-13 05:58", "2024-05-13 06:03"]
INI, FIM = "2024-04-01", "2024-05-17"

# ----------------------------------------------------------------------
# leitura dos caches (formato: 1 linha = 1 dia; nan = faltante)
# ----------------------------------------------------------------------
def ler_grade(arq, freq):
    vals = []
    for l in (AQUI / arq).read_text().splitlines():
        if l.startswith("#") or not l.strip():
            continue
        vals += [float(x) for x in l.replace(",", " ").split()]
    t = pd.date_range("2024-04-01 00:00", periods=len(vals), freq=freq)
    return pd.DataFrame({"tempo": t, "v": vals})

def ler_dst():
    out = []
    for mes, arq in [(4, "dados_geomag/dst_202404.txt"),
                     (5, "dados_geomag/dst_202405.txt")]:
        for l in (AQUI / arq).read_text().splitlines():
            if l.startswith("#") or not l.strip():
                continue
            p = l.split()
            dia = int(p[0])
            for h, v in enumerate(p[1:25]):
                out.append((pd.Timestamp(2024, mes, dia, h), float(v)))
    return pd.DataFrame(out, columns=["tempo", "v"]).sort_values("tempo")

oulu = ler_grade("dados_nmdb/OULU_h1_20240401_20240516.txt", "h")
irk3 = ler_grade("dados_nmdb/IRK3_h3_20240401_20240516.txt", "3h")
mxco = ler_grade("dados_nmdb/MXCO_h3_20240401_20240516.txt", "3h")
kp = ler_grade("dados_geomag/kp_20240401_20240516.txt", "3h")
dst = ler_dst()

# limpeza IRK3: spikes instrumentais (< -15%) e artefatos pós-gap
irk3.loc[irk3.v < -15, "v"] = np.nan
irk3.loc[(irk3.tempo < "2024-05-10") & (irk3.v < -5), "v"] = np.nan

# re-baseline: média 01-05/04 = 0
def rebase(df):
    b = df.loc[df.tempo < "2024-04-06", "v"].mean()
    df = df.copy(); df["pct"] = df.v - b
    return df

oulu, irk3, mxco = rebase(oulu), rebase(irk3), rebase(mxco)

def marcar(ax, rotular=False):
    for t, lab, cor in MARCOS:
        x = pd.to_datetime(t)
        ax.axvline(x, color=cor, lw=1.4, alpha=0.75)
        if rotular:
            ax.annotate(lab, (x, ax.get_ylim()[1]), rotation=90, va="top",
                        ha="right", fontsize=7, color=cor)
    for k, t in enumerate(SISMOS):
        ax.axvline(pd.to_datetime(t), color="saddlebrown", lw=0.9, ls="--",
                   alpha=0.9)
    if rotular:
        ax.annotate("SISMOS 13/05 (04:48-06:03 UT)",
                    (pd.to_datetime(SISMOS[0]), ax.get_ylim()[0]),
                    rotation=90, va="bottom", ha="right", fontsize=7,
                    color="saddlebrown")

# ----------------------------------------------------------------------
# FIG 1 (módulo 01): timeline OULU
# ----------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(14, 6))
ax.plot(oulu.tempo, oulu.pct, "k", lw=0.9,
        label="Raios cósmicos OULU (% vs. 01-05/04)")
ax.axhline(0, color="gray", lw=0.5, ls=":")
marcar(ax, rotular=True)
ax.set_ylabel("Desvio (%)")
ax.set_title("Linha do tempo 01/04–16/05/2024 — GCR (Oulu), marcos solares "
             "e eventos de toró")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
ax.legend(loc="lower left", fontsize=8)
plt.tight_layout()
plt.savefig(OUT / "timeline_desde0104.png", dpi=150)
plt.close()
imin = oulu.pct.idxmin()
print(f"[01] FD mínimo OULU: {oulu.pct[imin]:.1f}% em {oulu.tempo[imin]}")

# ----------------------------------------------------------------------
# FIG 2 (módulo 01): multi-rigidez + estimativa do FD no corte do RS
# ----------------------------------------------------------------------
series = [("OULU", 0.81, oulu, "k"), ("IRK3", 3.64, irk3, "tab:blue"),
          ("MXCO", 8.28, mxco, "tab:red")]
fig, ax = plt.subplots(figsize=(14, 5))
Rs, As = [], []
for nome, R, df, cor in series:
    ax.plot(df.tempo, df.pct, lw=1, color=cor, label=f"{nome} (R={R} GV)")
    jan = (df.tempo >= "2024-05-10 17:00") & (df.tempo <= "2024-05-12 00:00")
    amp = -df.loc[jan, "pct"].min()
    print(f"[01] amplitude do FD em {nome} (R={R} GV): {amp:.1f}%")
    if np.isfinite(amp) and amp > 0:
        Rs.append(R); As.append(amp)
gamma, lna = np.polyfit(np.log(Rs), np.log(As), 1)
fd_rs = float(np.exp(lna) * 10.5 ** gamma)
print(f"[01] ajuste A~R^{gamma:.2f} -> FD estimado no corte ~10.5 GV "
      f"(sul do Brasil): ~{fd_rs:.1f}% (AMAS reduz o corte; valor real "
      "entre isso e MXCO)")
ax.axhline(0, color="gray", lw=0.5, ls=":")
marcar(ax)
ax.set_ylabel("Desvio (%) vs. 01-05/04")
ax.set_title(f"FD de maio/2024 por corte de rigidez — estimado ~{fd_rs:.1f}% "
             "no corte do RS (~10.5 GV)")
ax.legend(fontsize=8)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
plt.tight_layout()
plt.savefig(OUT / "timeline_multi_rigidez_desde0104.png", dpi=150)
plt.close()

# ----------------------------------------------------------------------
# FIG 3 (módulo 03): TEC dos IONEX em cache (com lacunas anotadas)
# ----------------------------------------------------------------------
linhas = []
dias_ok = []
for dia in pd.date_range(INI, "2024-05-16", freq="D"):
    f = AQUI / "dados_tec" / f"INPE{dia.dayofyear:03d}0.{dia.year % 100:02d}I"
    if f.exists():
        linhas += m03._parse_ionex(f.read_text(errors="ignore"), m03.ALVO_BOX)
        dias_ok.append(dia.strftime("%d/%m"))
tec = pd.DataFrame(linhas, columns=["tempo", "tec_box"]).sort_values("tempo")
print(f"[03] IONEX em cache: {len(dias_ok)} dias ({dias_ok[0]}...{dias_ok[-1]})")
tec = m03.anomalia_tec(tec)
# quebra a linha nas lacunas (> 3 h sem dado)
tec.loc[tec.tempo.diff() > pd.Timedelta("3h"), "tec_anom"] = np.nan

fig, ax = plt.subplots(figsize=(14, 5))
ax.plot(tec.tempo, tec.tec_anom, color="darkred", lw=1.0,
        label="Anomalia de TEC na caixa AMAS/RS (EMBRACE)")
ax.axhline(0, color="gray", ls=":", lw=0.5)
ax.set_xlim(pd.to_datetime(INI), pd.to_datetime(FIM))
marcar(ax)
ax.set_ylabel("Anomalia TEC (TECU)")
ax.set_title("TEC 01/04–16/05/2024 — janelas com IONEX em cache "
             "(10-16/04 controle; 08-14/05 evento); demais dias: baixar com o 03")
ax.legend(fontsize=8)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
plt.tight_layout()
plt.savefig(OUT / "gnss_tec_desde0104.png", dpi=150)
plt.close()

ev = tec[(tec.tempo >= "2024-05-08") & (tec.tempo <= "2024-05-15")]
ct = tec[(tec.tempo >= "2024-04-10") & (tec.tempo <= "2024-04-17")]
m03.comparar_evento_controle(ev, [ct])
tec[["tempo", "tec_anom"]].to_csv(OUT / "anomalia_tec_desde0104.csv",
                                  index=False)

# ----------------------------------------------------------------------
# FIG 4 (módulo 09): a coluna do Jz empilhada
# ----------------------------------------------------------------------
camadas = [
    ("Kp (driver geomagnético)", kp.rename(columns={"v": "y"}), "tab:red", "bar"),
    ("Dst (nT) — anel de corrente", dst.rename(columns={"v": "y"}), "tab:purple", "l"),
    ("Anomalia TEC — região F (AMAS)", tec.rename(
        columns={"tec_anom": "y"}), "tab:orange", "l"),
    ("GCR %: cinza=MXCO (~RS), azul=IRK3", mxco.rename(
        columns={"pct": "y"}), "tab:gray", "l2"),
]
fig, axs = plt.subplots(len(camadas), 1, figsize=(14, 2.4 * len(camadas)),
                        sharex=True)
for ax, (rot, df, cor, tipo) in zip(axs, camadas):
    if tipo == "bar":
        ax.bar(df.tempo, df.y, width=0.11, color=cor, alpha=0.8)
    else:
        ax.plot(df.tempo, df.y, color=cor, lw=1)
        if tipo == "l2":
            ax.plot(irk3.tempo, irk3.pct, color="tab:blue", lw=0.8, alpha=0.7)
    ax.set_ylabel(rot, fontsize=8)
    marcar(ax)
for t, lab, c in MARCOS:
    axs[0].annotate(lab, (pd.to_datetime(t), axs[0].get_ylim()[1]),
                    rotation=90, fontsize=7, color=c, va="top", ha="right")
axs[-1].set_xlim(pd.to_datetime(INI), pd.to_datetime(FIM))
axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
axs[0].set_title("A coluna do Jz — 01/04 a 16/05/2024 (AMAS)")
plt.tight_layout()
plt.savefig(OUT / "coluna_jz_desde0104.png", dpi=150)
plt.close()

# ----------------------------------------------------------------------
# FIG 5: coluna do Jz EXPANDIDA — driver solar -> ionosfera -> chão
#   + Ey (campo elétrico interplanetário, OMNI) — penetra na região F
#   + AE (eletrojato auroral, correntes ionosféricas reais)
#   + evento de prótons GOES (documentado: S2 16:40 UT 10/05; GLE74
#     01:45 UT 11/05; pico >10 MeV = 238 pfu)
# ----------------------------------------------------------------------
ey = ler_grade("dados_geomag/ey_omni_20240401_20240516.txt", "h")
ae = ler_grade("dados_geomag/ae_20240401_20240516.txt", "h")
SEP_INI, SEP_FIM = pd.Timestamp("2024-05-10 16:40"), pd.Timestamp("2024-05-15")

camadas5 = [
    ("Ey (mV/m) — campo elétrico\ninterplanetário (OMNI)", ey, "tab:green", "l"),
    ("Kp — driver geomagnético", kp, "tab:red", "bar"),
    ("Dst (nT) — anel de corrente", dst, "tab:purple", "l"),
    ("AE (nT) — eletrojato\nauroral (correntes ionosf.)", ae, "tab:brown", "l"),
    ("Prótons GOES >10 MeV\n(evento documentado)", None, "tab:olive", "sep"),
    ("Anomalia TEC (TECU)\nregião F (AMAS)", tec[["tempo", "tec_anom"]].rename(
        columns={"tec_anom": "v"}), "tab:orange", "l"),
    ("GCR %: cinza=MXCO (~RS)\nazul=IRK3", mxco[["tempo", "pct"]].rename(
        columns={"pct": "v"}), "tab:gray", "l2"),
]
fig, axs = plt.subplots(len(camadas5), 1, figsize=(14, 2.1 * len(camadas5)),
                        sharex=True)
for ax, (rot, df, cor, tipo) in zip(axs, camadas5):
    if tipo == "bar":
        ax.bar(df.tempo, df.v, width=0.11, color=cor, alpha=0.8)
    elif tipo == "sep":
        ax.axvspan(SEP_INI, SEP_FIM, color=cor, alpha=0.3,
                   label="evento S2 (>10 pfu)")
        ax.axvline(pd.Timestamp("2024-05-11 02:45"), color=cor, lw=2)
        ax.annotate("GLE74 — pico 238 pfu (02:45 UT 11/05)",
                    (pd.Timestamp("2024-05-11 04:00"), 0.5),
                    fontsize=7, color="k")
        ax.set_ylim(0, 1); ax.set_yticks([])
        ax.legend(loc="upper left", fontsize=7)
    else:
        ax.plot(df.tempo, df.v, color=cor, lw=0.9)
        ax.axhline(0, color="gray", lw=0.4, ls=":")
        if tipo == "l2":
            ax.plot(irk3.tempo, irk3.pct, color="tab:blue", lw=0.7, alpha=0.7)
    ax.set_ylabel(rot, fontsize=7.5)
    marcar(ax)
for t, lab, c in MARCOS:
    axs[0].annotate(lab, (pd.to_datetime(t), axs[0].get_ylim()[1]),
                    rotation=90, fontsize=7, color=c, va="top", ha="right")
axs[-1].set_xlim(pd.to_datetime(INI), pd.to_datetime(FIM))
axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
axs[0].set_title("A coluna do Jz EXPANDIDA — vento solar, magnetosfera, "
                 "ionosfera e chão — 01/04 a 16/05/2024")
plt.tight_layout()
plt.savefig(OUT / "coluna_jz_expandida_desde0104.png", dpi=150)
plt.close()

# CSVs das camadas novas (formato tempo,valor — consumível pelo 09)
ey.rename(columns={"v": "ey_mVm"}).to_csv(OUT / "ey_omni.csv", index=False)
ae.rename(columns={"v": "ae_nT"}).to_csv(OUT / "ae_kyoto.csv", index=False)

print(f"\nFiguras salvas em {OUT}:")
for f in sorted(OUT.glob("*.png")):
    print("  ", f.name)
