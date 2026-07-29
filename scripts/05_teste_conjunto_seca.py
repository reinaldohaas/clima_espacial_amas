#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05 — Seca do 2o semestre como ESTADO (não evento): eletricidade + fumaça tratadas JUNTAS.
   A seca é o Estado A mantido: água retida na nuvem (SLW/água de nuvem alta) com
   precipitação SUPRIMIDA. Testamos se a RETENÇÃO cresce com a INTERAÇÃO AOD×Jz
   (a carga agindo sobre o aerossol), nos dias calmos, sobre a região de queimadas.

   Requer rodar antes (modo ano):
     python 01_baixar_era5_vpi_slw_ivt.py --modo ano     # inclui PRECIP_rate e a caixa 'fogo'
     python 02_baixar_cams_aod.py          --modo ano
   Insumos:
     resultados/era5_diario_fogo_ano.csv     (SLW, PRECIP_rate, EFIC_PRECIP, VPI_baixo, IVT)
     resultados/cams_aod_diario_fogo_ano.csv (aod550_fumaca)
     rede_completa_14_estacoes_currents_2024.csv ; kp_dst_2024.csv
"""
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

OUT="resultados"; DOM="fogo"
def has_era(s): return os.path.exists(f"{OUT}/era5_diario_{DOM}_{s}.csv")
def has_aod(s): return os.path.exists(f"{OUT}/cams_aod_diario_{DOM}_{s}.csv")
SUF=next((s for s in ["seca","ano"] if has_era(s) and has_aod(s)),None)
if SUF is None:
    falta_era=[s for s in ["seca","ano"] if not has_era(s)]
    tem_era  =[s for s in ["seca","ano"] if has_era(s)]
    msg="\n[FALTA DADO] "
    if tem_era and not any(has_aod(s) for s in tem_era):
        s=tem_era[0]
        msg+=(f"O ERA5 de '{DOM}' ({s}) existe, mas falta o AOD. Rode:\n"
              f"  python 02_baixar_cams_aod.py --modo {s}\n")
    else:
        msg+=("Rode os downloads da região de fogo (ago-out, leve):\n"
              "  python 01_baixar_era5_vpi_slw_ivt.py --modo seca\n"
              "  python 02_baixar_cams_aod.py          --modo seca\n")
    raise SystemExit(msg+"e então rode este script de novo.\n")
print(f"usando período: {SUF}")
era=pd.read_csv(f"{OUT}/era5_diario_{DOM}_{SUF}.csv",parse_dates=["data"]).set_index("data")
aod=pd.read_csv(f"{OUT}/cams_aod_diario_{DOM}_{SUF}.csv",parse_dates=["data"]).set_index("data")
jz=pd.read_csv("dados/jz/rede_completa_14_estacoes_currents_2024.csv",parse_dates=["datetime"]).set_index("datetime").sort_index()
jz=jz.loc[~((jz.index.hour==0)&(jz.index.minute==0))]
jzd=jz.resample("1D").agg(Jz=("Jz_pA_m2",lambda s:np.sqrt((s**2).mean())))
kpp="dados/indices/kp_dst_2024.csv"
kp=pd.read_csv(kpp,parse_dates=["datetime_utc"]).set_index("datetime_utc").sort_index().resample("1D").agg(Kp=("Kp","max"))

D=pd.concat([aod.aod550_fumaca.rename("AOD"),era.SLW_kg_m2.rename("SLW"),
             era.get("PRECIP_rate").rename("PR") if "PRECIP_rate" in era else None,
             era.get("EFIC_PRECIP").rename("EFIC") if "EFIC_PRECIP" in era else None,
             (-era.VPI_baixo).rename("VPIcic") if "VPI_baixo" in era else None,
             jzd.Jz,kp.Kp],axis=1)
D=D.dropna(axis=1,how="all")

def reg(df,y,Xc):
    d=df[[y]+Xc].dropna(); z=(d-d.mean())/d.std()
    X=np.c_[np.ones(len(z)),*[z[c] for c in Xc]]
    b,*_=np.linalg.lstsq(X,z[y].values,rcond=None); yh=X@b
    r2=1-((z[y].values-yh)**2).sum()/((z[y].values-z[y].mean())**2).sum()
    return dict(zip(["c"]+Xc,np.round(b,2))),round(r2,2),len(z)

def bloco(df,nome):
    df=df.copy(); df["AODxJz"]=((df.AOD-df.AOD.mean())/df.AOD.std())*((df.Jz-df.Jz.mean())/df.Jz.std())
    print(f"\n===== {nome} (n={len(df)}) =====")
    for y in ["SLW","EFIC"]:
        if y not in df: continue
        print(f" {y} ~ AOD        :",reg(df,y,["AOD"]))
        print(f" {y} ~ AOD+Jz     :",reg(df,y,["AOD","Jz"]))
        print(f" {y} ~ AOD+Jz+AODxJz:",reg(df,y,["AOD","Jz","AODxJz"]))
    if "SLW" in df:
        m=df.AOD.median(); hi=df[df.AOD>=m]; lo=df[df.AOD<m]
        print(f" corr(SLW,Jz) fumaça alta={hi.SLW.corr(hi.Jz):+.2f} vs baixa={lo.SLW.corr(lo.Jz):+.2f}")

# calmo (Kp<3), ano todo e ago-out
q=D[D.Kp<3]
bloco(q,"ANO — dias calmos (Kp<3)")
bloco(q.loc["2024-08-01":"2024-10-31"],"AGO-OUT — dias calmos (a seca)")

# figura ago-out
S=D.loc["2024-08-01":"2024-10-31"]; z=lambda s:(s-s.mean())/s.std()
plt.figure(figsize=(12,5))
for c,cor,l in [("AOD","#e6550d","AOD fumaça"),("Jz","#756bb1","Jz_rms"),("SLW","#3182bd","água supercong.")]:
    if c in S: plt.plot(S.index,z(S[c]),color=cor,label=l)
if "PR" in S: plt.plot(S.index,z(S.PR),color="#31a354",label="precipitação")
plt.legend(fontsize=8,ncol=4); plt.title("Ago–Out 2024 região de fogo (normalizado): fumaça, Jz, água retida e chuva")
plt.tight_layout(); plt.savefig(f"{OUT}/fig_seca_2sem.png",dpi=150); plt.close()
print("\nFigura: fig_seca_2sem.png. Hipótese: AODxJz prediz SLW alto e EFIC (chuva/água) baixo = retenção/seca.")
