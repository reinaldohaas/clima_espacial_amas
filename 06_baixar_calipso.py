#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06 — CALIPSO/CALIOP: estrutura VERTICAL da fumaça (onde o Jz cruza a camada).
   Produto: CAL_LID_L2_05kmALay (Aerosol Layer, 5 km, V4) — dá topo/base das camadas de
   aerossol, o subtipo (fumaça/'elevated smoke') e a profundidade óptica da camada.

   Saída diária por caixa: altitude de topo e base da fumaça, AOD de fumaça, nº de perfis.
   Isso responde: em que altura está a fumaça — a camada que a corrente Jz atravessa.

Pré-req:
   pip install earthaccess numpy pandas
   conda install -c conda-forge pyhdf      # leitura de HDF4 (no miniforge)
   # conta Earthdata (mesma do 02b). No 1o uso earthaccess pede login e grava ~/.netrc.

Uso:
   python 06_baixar_calipso.py --ini 2024-09-01 --fim 2024-09-30 --caixa fogo
   python 06_baixar_calipso.py --ini 2024-05-01 --fim 2024-05-15 --caixa rs
Saída: resultados/calipso_fumaca_<caixa>_<ini>_<fim>.csv
"""
import argparse, os, numpy as np, pandas as pd
try:
    import earthaccess
except ImportError:
    raise SystemExit("pip install earthaccess")
try:
    from pyhdf.SD import SD, SDC
except ImportError:
    raise SystemExit("conda install -c conda-forge pyhdf  (leitura de HDF4 do CALIPSO)")

CAIXAS = {  # (W, S, E, N) para o bounding_box do earthaccess
    "brasil":(-74,-34,-34,6), "fogo":(-70,-20,-50,2),
    "rio_invisivel":(-63,-22,-50,-8), "rs":(-58,-34,-49,-27),
}
SHORT = "CAL_LID_L2_05kmALay-Standard-V4-51"

def subtipo_aerossol(fcf):
    """Decodifica Feature_Classification_Flags: tipo (bits 1-3) e subtipo de aerossol (bits 10-12)."""
    ftype = fcf & 0x7                 # 3 = aerossol
    asub  = (fcf >> 9) & 0x7          # subtipo (V4: 6=elevated smoke, 3=polluted continental/smoke)
    return ftype, asub

def processa_granulo(path, box):
    W,S,E,N = box
    hdf = SD(path, SDC.READ)
    lat = hdf.select("Latitude")[:].ravel()
    lon = hdf.select("Longitude")[:].ravel()
    top = hdf.select("Layer_Top_Altitude")[:]      # km, (nprof, nlayers)
    base= hdf.select("Layer_Base_Altitude")[:]
    fcf = hdf.select("Feature_Classification_Flags")[:]
    try:  od = hdf.select("Column_Optical_Depth_Aerosols_532")[:].ravel()
    except: od = np.full(lat.shape, np.nan)
    inbox = (lat>=S)&(lat<=N)&(lon>=W)&(lon<=E)
    tops=[]; bases=[]; ods=[]
    idx=np.where(inbox)[0]
    for i in idx:
        for L in range(top.shape[1]):
            if top[i,L] <= -999 or base[i,L] <= -999: continue
            ftype, asub = subtipo_aerossol(int(fcf[i,L]))
            if ftype==3 and asub in (3,6):          # aerossol classificado como fumaça
                tops.append(top[i,L]); bases.append(base[i,L])
        if not np.isnan(od[i]): ods.append(od[i])
    hdf.end()
    if not tops: return None
    return dict(topo_km=np.mean(tops), base_km=np.mean(bases),
                aod_col=np.nanmean(ods) if ods else np.nan, n=len(tops))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ini",required=True); ap.add_argument("--fim",required=True)
    ap.add_argument("--caixa",choices=list(CAIXAS),default="fogo")
    ap.add_argument("--outdir",default="resultados"); a=ap.parse_args()
    os.makedirs(a.outdir,exist_ok=True); box=CAIXAS[a.caixa]
    earthaccess.login(persist=True)
    res=earthaccess.search_data(short_name=SHORT, temporal=(a.ini,a.fim),
                                bounding_box=box)
    if not res: raise SystemExit("Nenhum grânulo CALIPSO — verifique acesso e datas.")
    print(f"{len(res)} grânulos; baixando/lendo...")
    files=earthaccess.download(res, f"{a.outdir}/_calipso_tmp")
    linhas=[]
    for f in files:
        if not str(f).endswith(".hdf"): continue
        try: r=processa_granulo(str(f), box)
        except Exception as e: print("  falhou",os.path.basename(str(f)),str(e)[:80]); continue
        if r is None: continue
        # data do grânulo pelo nome (…V4-51.YYYY-MM-DDThh-mm-ss…)
        base=os.path.basename(str(f))
        try: dia=pd.to_datetime(base.split(".")[1][:10],format="%Y-%m-%d")
        except: dia=pd.NaT
        r["data"]=dia; linhas.append(r)
    df=pd.DataFrame(linhas).dropna(subset=["data"])
    diario=df.groupby("data").agg(topo_km=("topo_km","mean"),base_km=("base_km","mean"),
                                  aod_col=("aod_col","mean"),n_perfis=("n","sum"))
    out=f"{a.outdir}/calipso_fumaca_{a.caixa}_{a.ini}_{a.fim}.csv"
    diario.to_csv(out); print(f"-> {out} ({len(diario)} dias)")
    print("Colunas: topo_km/base_km = altitude da camada de fumaça; aod_col = AOD 532 da coluna.")

if __name__=="__main__":
    main()
