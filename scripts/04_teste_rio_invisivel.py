#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04 — Teste do 'rio invisível': o mecanismo se FORMA a montante e ADVECTA VPI+vapor ao RS.
   Usa os CSVs por subdomínio gerados por 01 e 02 (--modo rs):
     era5_diario_{rio_invisivel,corredor,rs}_rs.csv   (VPI por nível, SLW, IVT, dipolo)
     cams_aod_diario_{rio_invisivel,corredor,rs}_rs.csv

   Faz:
   (A) Estrutura VERTICAL da VPI a montante (dipolo diabático: ciclônica embaixo).
   (B) Formação a montante: AOD -> SLW -> VPI_baixo (defasagem, e parcial | IVT).
   (C) Advecção: VPI_baixo e IVT de montante -> RS, estimando o tempo de trânsito (lag).
   Figuras em resultados/.
"""
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy import stats

OUT="resultados"; NIVEIS=[925,850,700,600,500,400,300]
def L(dom): return pd.read_csv(f"{OUT}/era5_diario_{dom}_rs.csv",parse_dates=["data"]).set_index("data")
def A(dom): return pd.read_csv(f"{OUT}/cams_aod_diario_{dom}_rs.csv",parse_dates=["data"]).set_index("data")

up=L("rio_invisivel"); rs=L("rs")
aup=A("rio_invisivel"); ars=A("rs")
W=slice("2024-04-15","2024-05-20")

def lead_lag(x,y,maxlag=7):
    best=(0,0.0)
    for l in range(0,maxlag+1):           # só x LIDERA y (l>=0)
        c=x.corr(y.shift(-l))
        if pd.notna(c) and abs(c)>abs(best[1]): best=(l,c)
    return best

# ---- (A) estrutura vertical média da VPI a montante e no RS ----
prof_up=[up.loc[W,f"VPI_{n}"].mean() for n in NIVEIS]
prof_rs=[rs.loc[W,f"VPI_{n}"].mean() for n in NIVEIS]
plt.figure(figsize=(5,6))
plt.plot(prof_up,NIVEIS,"-o",color="#e6550d",label="rio invisível (montante)")
plt.plot(prof_rs,NIVEIS,"-o",color="#3182bd",label="RS (destino)")
plt.axvline(0,color="k",lw=.8); plt.gca().invert_yaxis()
plt.xlabel("VPI média (PVU)  — HS: ciclônico < 0"); plt.ylabel("nível (hPa)")
plt.title("(A) Estrutura vertical da VPI\n(dipolo diabático: ciclônica em baixos níveis)")
plt.legend(); plt.tight_layout(); plt.savefig(f"{OUT}/fig_vpi_perfil.png",dpi=150); plt.close()

# ---- (B) formação a montante ----
up["VPIcic"]=-up["VPI_baixo"]
B=pd.concat([aup["aod550_fumaca"].rename("AOD"),up["SLW_kg_m2"].rename("SLW"),
             up["VPIcic"].rename("VPIcic"),up["IVT_kg_m_s"].rename("IVT"),
             up["VPI_dipolo"].rename("DIP")],axis=1).loc[W]
print("== (B) Formação a montante (rio invisível) ==")
for x,y in [("AOD","SLW"),("SLW","VPIcic"),("AOD","VPIcic"),("AOD","DIP")]:
    l,c=lead_lag(B[x],B[y]); print(f"  {x}->{y}: lidera +{l}d, r={c:+.2f}")
# parcial controlando IVT
def pcorr(x,y,c,lag):
    d=pd.concat([x.rename('x'),y.shift(-lag).rename('y'),c.rename('c')],axis=1).dropna()
    rx=d.x-np.polyval(np.polyfit(d.c,d.x,1),d.c); ry=d.y-np.polyval(np.polyfit(d.c,d.y,1),d.c)
    return rx.corr(ry)
l,_=lead_lag(B.AOD,B.SLW); print(f"  AOD->SLW parcial|IVT (L={l}): r={pcorr(B.AOD,B.SLW,B.IVT,l):+.2f}")

# ---- (C) advecção montante -> RS ----
C=pd.concat([up["VPIcic"].rename("VPIcic_up"),up["IVT_kg_m_s"].rename("IVT_up"),
             (-rs["VPI_baixo"]).rename("VPIcic_rs"),rs["IVT_kg_m_s"].rename("IVT_rs")],axis=1).loc[W]
print("== (C) Advecção montante -> RS (tempo de trânsito) ==")
for x,y in [("VPIcic_up","VPIcic_rs"),("IVT_up","IVT_rs")]:
    l,c=lead_lag(C[x],C[y]); print(f"  {x}->{y}: montante lidera RS em +{l}d, r={c:+.2f}")

# figura da sequência montante->RS
z=lambda s:(s-s.mean())/s.std()
plt.figure(figsize=(12,5))
for col,cor,lab in [(B.AOD,"#e6550d","AOD fumaça (montante)"),(B.SLW,"#fdae6b","SLW (montante)"),
                    (B.VPIcic,"#31a354","VPIcic baixo (montante)"),(C.IVT_rs,"#3182bd","IVT (RS)"),
                    ((-rs['VPI_baixo']).loc[W],"#08519c","VPIcic (RS)")]:
    plt.plot(col.index,z(col),label=lab)
plt.axvspan(pd.Timestamp("2024-05-02"),pd.Timestamp("2024-05-06"),color="b",alpha=.08)
plt.axvspan(pd.Timestamp("2024-05-11"),pd.Timestamp("2024-05-13"),color="r",alpha=.08)
plt.legend(fontsize=8,ncol=3); plt.title("(C) Formação a montante -> advecção de VPI+vapor -> RS (normalizado)")
plt.tight_layout(); plt.savefig(f"{OUT}/fig_montante_para_rs.png",dpi=150); plt.close()
print("Figuras: fig_vpi_perfil.png, fig_montante_para_rs.png")
