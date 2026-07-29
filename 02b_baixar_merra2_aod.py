#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02b — ALTERNATIVA sem ADS: AOD do MERRA-2 (NASA) via Earthdata.
   Produz o mesmo CSV que o 02 (colunas aod550_total / aod550_fumaca), para o 03 usar igual.

   Usa a coleção M2T1NXAER (aerossóis, horária média):
     TOTEXTTAU = AOD total (550 nm)
     BCEXTTAU  = AOD de carbono negro   } fumaça
     OCEXTTAU  = AOD de carbono orgânico}

Pré-requisitos:
   pip install earthaccess xarray netCDF4 numpy pandas
   # Conta Earthdata (https://urs.earthdata.nasa.gov/). No 1o uso, earthaccess pede login
   # e grava ~/.netrc. Aceite o acesso a GES DISC no seu perfil Earthdata.

Uso:  python 02b_baixar_merra2_aod.py --modo rs   (depois --modo ano)
Saída: resultados/cams_aod_diario_<dominio>_<modo>.csv  (mesmo nome/schema do passo 02)
"""
import argparse, os
import numpy as np, pandas as pd, xarray as xr
try:
    import earthaccess
except ImportError:
    raise SystemExit("pip install earthaccess xarray netCDF4")

DOMINIOS = {"brasil":(-34,6,-74,-34), "rs":(-34,-27,-58,-49)}  # (lat_min,lat_max,lon_min,lon_max)

def periodo(modo):
    return ("2024-04-15","2024-05-25") if modo=="rs" else ("2024-01-01","2024-12-31")

def baixar_abrir(modo):
    earthaccess.login(persist=True)
    t0,t1 = periodo(modo)
    res = earthaccess.search_data(short_name="M2T1NXAER", temporal=(t0,t1))
    if not res: raise SystemExit("Nenhum grânulo M2T1NXAER encontrado — verifique acesso GES DISC no Earthdata.")
    files = earthaccess.open(res)  # streaming via fsspec (não baixa tudo em disco)
    return xr.open_mfdataset(files, combine="by_coords")

def processar(ds, dom):
    la0,la1,lo0,lo1 = DOMINIOS[dom]
    sub = ds.sel(lat=slice(la0,la1), lon=slice(lo0,lo1))
    out = {}
    for want, var in [("aod550_total","TOTEXTTAU"),("aod550_bc","BCEXTTAU"),("aod550_org","OCEXTTAU")]:
        if var in sub:
            out[want] = sub[var].mean(dim=["lat","lon"]).to_series()
    df = pd.DataFrame(out)
    df["aod550_fumaca"] = df.get("aod550_org",0)+df.get("aod550_bc",0)
    d = df.resample("1D").mean(); d.index.name="data"; d["dominio"]=dom
    return d

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--modo",choices=["rs","ano"],default="rs")
    ap.add_argument("--outdir",default="resultados"); a=ap.parse_args()
    os.makedirs(a.outdir,exist_ok=True)
    print(f"abrindo MERRA-2 M2T1NXAER ({a.modo})..."); ds = baixar_abrir(a.modo)
    for dom in DOMINIOS:
        d = processar(ds, dom); out=f"{a.outdir}/cams_aod_diario_{dom}_{a.modo}.csv"
        d.to_csv(out); print(f"[{dom}] -> {out} ({len(d)} dias)")

if __name__=="__main__":
    main()
