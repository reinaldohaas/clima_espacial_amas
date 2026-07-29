#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
11 — Taxa de RELÂMPAGOS (GOES-16 GLM) sobre o RS — o medidor direto do regime de graupel.
   Previsão a testar: muitos flashes no PULSO 1 (2–4/mai, trovoadas) e quase nada no PULSO 2
   (11–13/mai, só chuva). É a testemunha independente da nuvem eletrificada (graupel) e o
   normalizador de R que faltava.

   Dado público (sem login) no AWS: bucket noaa-goes16, produto GLM-L2-LCFA (arquivos de 20 s).
   Como são ~4320 arquivos/dia, o script SUBAMOSTRA (1 a cada --passo) e conta os flashes na caixa;
   a taxa é escalada pelo fator de subamostragem (bom para comparar dias entre si).

Pré-req:  pip install s3fs xarray netCDF4 numpy pandas
Uso:
   python 11_glm_relampagos.py --ini 2024-05-01 --fim 2024-05-15 --caixa rs --passo 15
Saída: resultados/glm_flashes_<caixa>_<ini>_<fim>.csv  (data, n_flashes_estimado, arquivos_lidos)
"""
import argparse, os, datetime as dt, numpy as np, pandas as pd
try:
    import s3fs, xarray as xr
except ImportError:
    raise SystemExit("pip install s3fs xarray netCDF4")

CAIXAS={"brasil":(-34,6,-74,-34),"rs":(-34,-27,-58,-49),"corredor":(-30,-22,-60,-50)}  # (latmin,latmax,lonmin,lonmax)
BUCKET="noaa-goes16"; PROD="GLM-L2-LCFA"

def conta_dia(fs, day, box, passo):
    la0,la1,lo0,lo1=box
    doy=day.timetuple().tm_yday; total=0; lidos=0
    for hh in range(24):
        pref=f"{BUCKET}/{PROD}/{day.year}/{doy:03d}/{hh:02d}/"
        try: arqs=fs.ls(pref)
        except Exception: continue
        for i,a in enumerate(arqs):
            if i % passo: continue                      # subamostra
            try:
                with fs.open(a) as f:
                    ds=xr.open_dataset(f,engine="h5netcdf")
                    la=ds["flash_lat"].values; lo=ds["flash_lon"].values
                    total+=int(((la>=la0)&(la<=la1)&(lo>=lo0)&(lo<=lo1)).sum()); lidos+=1
            except Exception: continue
    return total, lidos

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ini",required=True); ap.add_argument("--fim",required=True)
    ap.add_argument("--caixa",choices=list(CAIXAS),default="rs")
    ap.add_argument("--passo",type=int,default=15)   # 1 a cada 15 arquivos (~5 min)
    ap.add_argument("--outdir",default="resultados"); a=ap.parse_args(); os.makedirs(a.outdir,exist_ok=True)
    fs=s3fs.S3FileSystem(anon=True); box=CAIXAS[a.caixa]
    dias=pd.date_range(a.ini,a.fim,freq="D"); linhas=[]
    for d in dias:
        n,li=conta_dia(fs,d.to_pydatetime(),box,a.passo)
        est=n*a.passo                                   # escala pela subamostragem
        linhas.append({"data":d.normalize(),"n_flashes_estimado":est,"arquivos_lidos":li})
        print(f"  {d.date()}: ~{est} flashes (contados {n} em {li} arquivos)")
    df=pd.DataFrame(linhas).set_index("data")
    out=f"{a.outdir}/glm_flashes_{a.caixa}_{a.ini}_{a.fim}.csv"; df.to_csv(out)
    print(f"-> {out}")
    p1=df.loc["2024-05-02":"2024-05-04","n_flashes_estimado"].sum()
    p2=df.loc["2024-05-11":"2024-05-13","n_flashes_estimado"].sum()
    print(f"PULSO 1 (2-4/mai): ~{p1} flashes | PULSO 2 (11-13/mai): ~{p2} flashes | razão P1/P2 = {p1/max(p2,1):.1f}x")

if __name__=="__main__":
    main()
