#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02 — CAMS EAC4 (ADS): baixa UMA vez a caixa ampla do Brasil e processa subdomínios
     (rio_invisivel / corredor / rs / brasil), gerando AOD 550 total e de fumaça (org+BC).

Reaproveita o _cams_brasil_<modo>.nc já baixado; não rebaixa.

ADS (não CDS!): ~/.adsapirc com url https://ads.atmosphere.copernicus.eu/api e sua key;
   aceite a licença do 'CAMS global reanalysis (EAC4)' no site.  (ou use 02b_ MERRA-2)

Uso: python 02_baixar_cams_aod.py --modo rs   (depois --modo ano)
"""
import argparse, os
import numpy as np, pandas as pd, xarray as xr
try:
    import cdsapi
except ImportError:
    raise SystemExit("pip install 'cdsapi>=0.7.2' xarray netCDF4")

DOWNLOAD_AREA=[6,-74,-34,-34]
SUBDOMINIOS={"brasil":(6,-74,-34,-34),"fogo":(2,-70,-20,-50),
             "rio_invisivel":(-8,-63,-22,-50),
             "corredor":(-22,-60,-30,-50),"rs":(-27,-58,-34,-49)}
VARS=["total_aerosol_optical_depth_550nm",
      "organic_matter_aerosol_optical_depth_550nm",
      "black_carbon_aerosol_optical_depth_550nm"]
ADS_URL_DEFAULT="https://ads.atmosphere.copernicus.eu/api"

def periodo(modo):
    return {"rs":"2024-04-15/2024-05-25","seca":"2024-08-01/2024-10-31"}.get(modo,"2024-01-01/2024-12-31")

def ads_client():
    url=os.environ.get("ADS_URL"); key=os.environ.get("ADS_KEY")
    if not key:
        rc=os.path.expanduser("~/.adsapirc")
        if os.path.exists(rc):
            for ln in open(rc):
                if ":" in ln:
                    k,v=ln.split(":",1)
                    if k.strip()=="url": url=v.strip()
                    if k.strip()=="key": key=v.strip()
    if not key:
        raise SystemExit("Falta ~/.adsapirc (url do ADS + key). Veja cabeçalho do script.")
    return cdsapi.Client(url=url or ADS_URL_DEFAULT,key=key)

def baixar(modo,out_nc):
    if os.path.exists(out_nc): return
    c=ads_client(); base={"variable":VARS,"date":periodo(modo),
        "time":["00:00","06:00","12:00","18:00"],"area":DOWNLOAD_AREA}
    errs=[]
    for extra in [{"data_format":"netcdf","download_format":"unarchived"},
                  {"data_format":"netcdf"},{"format":"netcdf"}]:
        try: c.retrieve("cams-global-reanalysis-eac4",{**base,**extra},out_nc); return
        except Exception as e: errs.append(f"  {extra}: {str(e)[:150]}")
    raise SystemExit("[ERRO] CAMS EAC4:\n"+"\n".join(errs))

def _open(path):
    import zipfile
    if zipfile.is_zipfile(path):
        z=zipfile.ZipFile(path); ncs=[n for n in z.namelist() if n.endswith('.nc')]
        d=path+"_x"; os.makedirs(d,exist_ok=True); z.extract(ncs[0],d)
        return xr.open_dataset(os.path.join(d,ncs[0]))
    return xr.open_dataset(path)

def subset(ds,box):
    N,W,S,E=box
    latn='latitude' if 'latitude' in ds else 'lat'; lonn='longitude' if 'longitude' in ds else 'lon'
    if float(ds[lonn].max())>180:
        ds=ds.assign_coords({lonn:(((ds[lonn]+180)%360)-180)}).sortby(lonn)
    la=ds[latn].values; lat_slice=slice(N,S) if la[0]>la[-1] else slice(S,N)
    return ds.sel({latn:lat_slice,lonn:slice(W,E)})

def processar(dom,box,ds):
    sub=subset(ds,box)
    latn='latitude' if 'latitude' in sub else 'lat'; lonn='longitude' if 'longitude' in sub else 'lon'
    tdim='valid_time' if 'valid_time' in sub.dims else 'time'
    short={"aod550_total":"aod550","aod550_org":"omaod550","aod550_bc":"bcaod550"}
    out={}
    for w,s in short.items():
        if s in sub: out[w]=sub[s].mean(dim=[latn,lonn]).values
    df=pd.DataFrame(out,index=pd.to_datetime(sub[tdim].values))
    df["aod550_fumaca"]=df.get("aod550_org",0)+df.get("aod550_bc",0)
    d=df.resample("1D").mean(); d.index.name="data"; d["dominio"]=dom
    return d

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--modo",choices=["rs","seca","ano"],default="rs")
    ap.add_argument("--outdir",default="resultados"); ap.add_argument("--datadir",default="dados"); a=ap.parse_args(); os.makedirs(a.outdir,exist_ok=True)
    nc=f"{a.datadir}/cams/_cams_brasil_{a.modo}.nc"
    print(f"baixando/lendo CAMS caixa ampla ({a.modo})..."); baixar(a.modo,nc)
    ds=_open(nc)
    for dom,box in SUBDOMINIOS.items():
        d=processar(dom,box,ds); out=f"{a.outdir}/cams_aod_diario_{dom}_{a.modo}.csv"
        d.to_csv(out); print(f"[{dom}] -> {out} ({len(d)} dias)")

if __name__=="__main__":
    main()
