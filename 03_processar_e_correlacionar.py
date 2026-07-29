#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03 — Junta tudo e testa a hipótese. Consome:
   - rede_completa_14_estacoes_currents_2024.csv         (Jz da rede)
   - resultados/kp_dst_2024.csv                          (Kp/Dst)
   - resultados/era5_diario_brasil_ano.csv               (VPI/SLW/IVT/TCLW — Brasil, ano)
   - resultados/cams_aod_diario_brasil_ano.csv           (AOD — Brasil, ano)
   - (para o caso RS) *_rs_rs.csv dos passos 01/02

Produz:
   - resultados/tabela_diaria_integrada_2024.csv
   - figuras: fig_aod_vs_jz_diasCalmos.png, fig_setembro.png, fig_rs_sequencia.png

Testes:
   (T1) Dias CALMOS (Kp<3) e BEM COBERTOS (nº est.>=10): Jz_rms ~ AOD_fumaça  (isola Tinsley)
   (T2) Setembro: Jz_rms, SLW e AOD sobem juntos, com precipitação/rain suprimida?
   (T3) RS (15/abr–25/mai): sequência pré-condicionamento(AOD)→SLW/VPI→IVT→enchente, com defasagem
"""
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy import stats

JZ="rede_completa_14_estacoes_currents_2024.csv"
KP="resultados/kp_dst_2024.csv"

def jz_diario():
    jz=pd.read_csv(JZ,parse_dates=["datetime"]).set_index("datetime").sort_index()
    jz=jz.loc[~((jz.index.hour==0)&(jz.index.minute==0))]        # remove artefato 00:00
    d=jz.resample("1D").agg(Jz_rms=("Jz_pA_m2",lambda s:np.sqrt((s**2).mean())),
                            absJz=("Jz_pA_m2",lambda s:s.abs().mean()),
                            nst=("n_stations_active","mean"))
    return d

def kp_diario():
    idx=pd.read_csv(KP,parse_dates=["datetime_utc"]).set_index("datetime_utc").sort_index()
    return idx.resample("1D").agg(Kp_max=("Kp","max"),Dst_min=("Dst_nT","min"))

def carrega(path):
    if not os.path.exists(path): print("  (faltando)",path); return None
    return pd.read_csv(path,parse_dates=["data"]).set_index("data")

def integra(dom="brasil",modo="ano"):
    D=jz_diario().join(kp_diario())
    e=carrega(f"resultados/era5_diario_{dom}_{modo}.csv")
    a=carrega(f"resultados/cams_aod_diario_{dom}_{modo}.csv")
    if e is not None: D=D.join(e.drop(columns=["dominio"],errors="ignore"))
    if a is not None: D=D.join(a.drop(columns=["dominio"],errors="ignore"))
    return D

def teste1(D):
    if "aod550_fumaca" not in D.columns:
        print("T1: pulado — falta o AOD (rode 02 ou 02b --modo ano)."); return
    sub=D[(D.Kp_max<3)&(D.nst>=10)].dropna(subset=["Jz_rms","aod550_fumaca"])
    if len(sub)<10: print("T1: dados insuficientes"); return
    r,p=stats.spearmanr(sub.Jz_rms,sub.aod550_fumaca)
    print(f"T1 (dias calmos+bem cobertos, n={len(sub)}): Spearman Jz_rms x AOD_fumaça = {r:+.3f} (p={p:.3g})")
    plt.figure(figsize=(6,5)); plt.scatter(sub.aod550_fumaca,sub.Jz_rms,s=18,c="#d95f0e",alpha=.6)
    plt.xlabel("AOD 550 fumaça (org+BC)"); plt.ylabel("Jz_rms (pA/m²)")
    plt.title(f"Isolando Tinsley: dias calmos e bem cobertos\nSpearman={r:+.2f} (p={p:.2g}, n={len(sub)})")
    plt.tight_layout(); plt.savefig("resultados/fig_aod_vs_jz_diasCalmos.png",dpi=150); plt.close()

def teste2(D):
    sep=D["2024-09-01":"2024-09-30"]
    cols=[c for c in ["Jz_rms","SLW_kg_m2","aod550_fumaca","IVT_kg_m_s"] if c in sep.columns]
    if len(cols)<2:
        print("T2: pulado — falta AOD/ERA5 de setembro (rode 01 e 02 --modo ano)."); return
    print("T2 Setembro médias:",{c:round(float(sep[c].mean()),3) for c in cols})
    if {"Jz_rms","aod550_fumaca"}<=set(sep):
        r,_=stats.spearmanr(sep.Jz_rms,sep.aod550_fumaca); print(f"   Set: Jz_rms x AOD = {r:+.2f}")
    z=(sep[cols]-sep[cols].mean())/sep[cols].std()
    z.plot(figsize=(10,4)); plt.title("Setembro 2024 (normalizado): Jz, SLW, AOD_fumaça, IVT")
    plt.tight_layout(); plt.savefig("resultados/fig_setembro.png",dpi=150); plt.close()

def teste3():
    D=integra("rs","rs")
    er=carrega("resultados/era5_diario_rs_rs.csv"); ar=carrega("resultados/cams_aod_diario_rs_rs.csv")
    if er is not None:
        for c in ["VPI_baixo_PVU","SLW_kg_m2","IVT_kg_m_s"]:
            if c in er: D[c+"_RS"]=er[c]
    if ar is not None and "aod550_fumaca" in ar: D["AOD_fumaca_RS"]=ar["aod550_fumaca"]
    W=D["2024-04-15":"2024-05-25"]
    cols=[c for c in ["AOD_fumaca_RS","SLW_kg_m2_RS","VPI_baixo_PVU_RS","IVT_kg_m_s_RS","Jz_rms","Dst_min"] if c in W.columns]
    if not any(c.endswith("_RS") for c in cols):
        print("T3: pulado — falta ERA5/AOD do domínio RS (rode 01 e 02 --modo rs)."); return
    z=(W[cols]-W[cols].mean())/W[cols].std()
    z.plot(figsize=(12,5)); plt.axvspan(pd.Timestamp("2024-05-02"),pd.Timestamp("2024-05-06"),color="b",alpha=.08)
    plt.axvspan(pd.Timestamp("2024-05-11"),pd.Timestamp("2024-05-13"),color="r",alpha=.08)
    plt.title("Sequência RS (normalizado): AOD → SLW/VPI → IVT → enchente")
    plt.tight_layout(); plt.savefig("resultados/fig_rs_sequencia.png",dpi=150); plt.close()
    # correlação defasada VPI_RS x IVT_RS e AOD->SLW
    for x,y in [("AOD_fumaca_RS","SLW_kg_m2_RS"),("SLW_kg_m2_RS","VPI_baixo_PVU_RS"),("VPI_baixo_PVU_RS","IVT_kg_m_s_RS")]:
        if x in W and y in W:
            best=max(range(-3,4),key=lambda L: abs(W[x].corr(W[y].shift(-L))))
            print(f"T3 {x}->{y}: melhor defasagem {best:+d}d, r={W[x].corr(W[y].shift(-best)):+.2f}")

if __name__=="__main__":
    os.makedirs("resultados",exist_ok=True)
    D=integra("brasil","ano"); D.to_csv("resultados/tabela_diaria_integrada_2024.csv")
    print("Tabela integrada salva. Colunas:",list(D.columns))
    teste1(D); teste2(D); teste3()
    print("Figuras em resultados/. Envie os CSVs/figuras de volta para análise conjunta.")
