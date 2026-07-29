#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06 — Altura da camada de FUMAÇA (substituto do CALIPSO, sem dados em 2024).
   MERRA-2 3D de aerossol M2I3NVAER. Baixa UM arquivo por dia, processa e APAGA
   (disco fica baixo; não depende de OPeNDAP/cookie). Fumaça = BC + OC.

   Saída diária por caixa:
     h_media_km = altura média (massa) da fumaça ; h_topo_km = topo (95% da massa) ;
     col_fumaca = coluna de fumaça (kg/m2)

Pré-req:  pip install earthaccess xarray netCDF4 numpy pandas   (+ conta Earthdata ~/.netrc)
Uso:      python 06_altura_fumaca_merra2.py --ini 2024-09-01 --fim 2024-09-30 --caixa fogo
Obs: baixa ~1 arquivo grande por dia e apaga em seguida — deixe rodando.
"""
import argparse, os, numpy as np, pandas as pd, xarray as xr
try:
    import earthaccess
except ImportError:
    raise SystemExit("pip install earthaccess xarray netCDF4")

G=9.80665
CAIXAS={"brasil":(-34,6,-74,-34),"fogo":(-20,2,-70,-50),
        "rio_invisivel":(-22,-8,-63,-50),"sudeste":(-25,-14,-55,-43),"rs":(-34,-27,-58,-49)}
VARS=["BCPHILIC","BCPHOBIC","OCPHILIC","OCPHOBIC","DELP","AIRDENS"]

def altura_dia(ds, box):
    la0,la1,lo0,lo1=box
    have=[v for v in VARS if v in ds]
    sub=ds[have].sel(lat=slice(la0,la1),lon=slice(lo0,lo1))
    smoke=sub["BCPHILIC"]+sub["BCPHOBIC"]+sub["OCPHILIC"]+sub["OCPHOBIC"]
    dp=sub["DELP"]; lev="lev"
    if "AIRDENS" in sub: dz=dp/(sub["AIRDENS"]*G)
    else:  # fallback: altura por pressão (escala 8 km) usando pressão do nível
        pedge=dp.cumsum(lev); dz=(np.log(pedge+dp/2)*0+1)  # placeholder; AIRDENS deve existir
    dz_rev=dz.isel({lev:slice(None,None,-1)})
    z_mid=((dz_rev.cumsum(lev)-dz_rev/2).isel({lev:slice(None,None,-1)}))/1000.0
    w=smoke*dp
    h_media=(w*z_mid).sum(lev)/(w.sum(lev)+1e-30)
    order=w.isel({lev:slice(None,None,-1)}); cum=order.cumsum(lev)/(order.sum(lev)+1e-30)
    ztop=z_mid.isel({lev:slice(None,None,-1)}).where(cum>=0.95).min(lev)
    col=(smoke*dp/G).sum(lev)
    sp=[d for d in h_media.dims if d in ("lat","lon","time")]
    return float(h_media.mean(dim=sp)), float(ztop.mean(dim=sp)), float(col.mean(dim=sp))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ini",required=True); ap.add_argument("--fim",required=True)
    ap.add_argument("--caixa",choices=list(CAIXAS),default="fogo"); ap.add_argument("--outdir",default="resultados")
    a=ap.parse_args(); os.makedirs(a.outdir,exist_ok=True); box=CAIXAS[a.caixa]
    tmp=f"{a.outdir}/_merra2_tmp"; os.makedirs(tmp,exist_ok=True)
    earthaccess.login(persist=True)
    res=earthaccess.search_data(short_name="M2I3NVAER",temporal=(a.ini,a.fim))
    if not res: raise SystemExit("Nenhum grânulo M2I3NVAER — verifique acesso GES DISC.")
    print(f"{len(res)} dias; baixando 1 por vez (e apagando após processar)...")
    linhas=[]
    for i,g in enumerate(res):
        fp=None
        try:
            paths=earthaccess.download([g], tmp)
            fp=str(paths[0])
            ds=xr.open_dataset(fp)
            dia=pd.to_datetime(str(ds["time"].values[0])).normalize()
            hm,ht,col=altura_dia(ds,box); ds.close()
            linhas.append({"data":dia,"h_media_km":hm,"h_topo_km":ht,"col_fumaca":col})
            print(f"  {i+1}/{len(res)} {dia.date()}  h_media={hm:.2f} km  topo={ht:.2f} km")
        except Exception as e:
            print(f"  {i+1}/{len(res)} falhou: {str(e)[:100]}")
        finally:
            if fp and os.path.exists(fp):
                try: os.remove(fp)
                except: pass
    df=pd.DataFrame(linhas).set_index("data").sort_index()
    out=f"{a.outdir}/altura_fumaca_{a.caixa}_{a.ini}_{a.fim}.csv"; df.to_csv(out)
    print(f"-> {out} ({len(df)} dias)")

if __name__=="__main__":
    main()
