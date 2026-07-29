#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
15 — INVENTÁRIO dos dados: varre uma ou mais pastas e monta UMA TABELA com, por variável:
        arquivo, variável, unidades, dimensões, período (data ini/fim), nº de tempos,
        níveis (se houver), e a grade lat/long (min, max, passo).
     Cobre .nc (ERA5/CAMS/MERRA-2 via xarray) e .csv (tabelas diárias/horárias via pandas).

Uso (aponte para os dois diretórios; no Windows use aspas ou barras normais):
   python 15_inventario_dados.py .  ../Eventos_toro
   python 15_inventario_dados.py "C:/Users/haas/github/clima_espacial_amas" "C:/Users/haas/github/Eventos_toro"
Saída: inventario_dados.csv  (uma linha por variável)  +  resumo na tela.
"""
import sys, os, glob, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")

def _rng_eixo(vals):
    v=np.asarray(vals,dtype=float)
    if v.size<2: return (float(v.min()) if v.size else np.nan, float(v.max()) if v.size else np.nan, np.nan, v.size)
    d=np.diff(np.sort(v)); return float(v.min()), float(v.max()), float(np.median(np.abs(d))), int(v.size)

def _nome(ds, *cands):
    for c in cands:
        if c in ds.variables or c in getattr(ds,'dims',{}): return c
    return None

def inv_nc(path, dire):
    import xarray as xr, zipfile
    linhas=[]
    try:
        if zipfile.is_zipfile(path):
            z=zipfile.ZipFile(path); ncs=[n for n in z.namelist() if n.endswith('.nc')]
            d=path+"_inv"; os.makedirs(d,exist_ok=True); z.extract(ncs[0],d)
            ds=xr.open_dataset(os.path.join(d,ncs[0]))
        else:
            ds=xr.open_dataset(path)
    except Exception as e:
        return [dict(diretorio=dire,arquivo=os.path.basename(path),tipo="nc",variavel="(erro ao abrir)",
                     unidades=str(e)[:60])]
    latn=_nome(ds,'latitude','lat'); lonn=_nome(ds,'longitude','lon')
    tdn=_nome(ds,'valid_time','time','t'); lvn=_nome(ds,'pressure_level','level','lev','isobaricInhPa')
    # tempo
    d_ini=d_fim=""; nt=0
    if tdn and tdn in ds.variables:
        try:
            tt=pd.to_datetime(ds[tdn].values); d_ini=str(pd.Series(tt).min())[:16]; d_fim=str(pd.Series(tt).max())[:16]; nt=len(tt)
        except Exception: pass
    # níveis
    niv=""
    if lvn and lvn in ds.variables:
        try: niv=",".join(str(int(x)) for x in np.atleast_1d(ds[lvn].values))
        except Exception: niv=str(np.atleast_1d(ds[lvn].values))
    # grade
    la=_rng_eixo(ds[latn].values) if latn else (np.nan,)*4
    lo=_rng_eixo(ds[lonn].values) if lonn else (np.nan,)*4
    if lonn and la and float(np.nanmax(ds[lonn].values))>180:  # normaliza p/ -180..180 na exibição
        lv_=((np.asarray(ds[lonn].values)+180)%360)-180; lo=_rng_eixo(lv_)
    for v in ds.data_vars:
        dims="×".join(map(str,ds[v].dims))
        linhas.append(dict(diretorio=dire,arquivo=os.path.basename(path),tipo="nc",variavel=str(v),
            unidades=str(ds[v].attrs.get("units",""))[:20],long_name=str(ds[v].attrs.get("long_name",""))[:40],
            dims=dims,data_ini=d_ini,data_fim=d_fim,n_tempos=nt,niveis=niv,
            lat_min=round(la[0],3),lat_max=round(la[1],3),dlat=round(la[2],4),nlat=la[3],
            lon_min=round(lo[0],3),lon_max=round(lo[1],3),dlon=round(lo[2],4),nlon=lo[3]))
    ds.close()
    return linhas

def inv_csv(path, dire):
    try: df=pd.read_csv(path, nrows=200000)
    except Exception as e:
        return [dict(diretorio=dire,arquivo=os.path.basename(path),tipo="csv",variavel="(erro)",unidades=str(e)[:60])]
    dcol=None
    for c in df.columns:
        if c.lower() in ("data","datetime","date","time","quando","t"):
            dcol=c; break
    d_ini=d_fim=""; nt=len(df)
    if dcol:
        try: dd=pd.to_datetime(df[dcol],errors="coerce"); d_ini=str(dd.min())[:16]; d_fim=str(dd.max())[:16]
        except Exception: pass
    linhas=[]
    for v in df.columns:
        if v==dcol: continue
        linhas.append(dict(diretorio=dire,arquivo=os.path.basename(path),tipo="csv",variavel=str(v),
            unidades="",long_name="",dims=f"{nt} linhas",data_ini=d_ini,data_fim=d_fim,n_tempos=nt,
            niveis="",lat_min=np.nan,lat_max=np.nan,dlat=np.nan,nlat=np.nan,
            lon_min=np.nan,lon_max=np.nan,dlon=np.nan,nlon=np.nan))
    return linhas

def main():
    dirs=sys.argv[1:] or ["."]
    linhas=[]
    for dire in dirs:
        ncs=glob.glob(os.path.join(dire,"**","*.nc"),recursive=True)
        csvs=glob.glob(os.path.join(dire,"**","*.csv"),recursive=True)
        print(f"[{dire}] {len(ncs)} .nc, {len(csvs)} .csv")
        for p in sorted(ncs):  linhas+=inv_nc(p,dire)
        for p in sorted(csvs): linhas+=inv_csv(p,dire)
    if not linhas: raise SystemExit("nada encontrado nas pastas: "+", ".join(dirs))
    df=pd.DataFrame(linhas)
    cols=["diretorio","arquivo","tipo","variavel","unidades","long_name","dims","data_ini","data_fim",
          "n_tempos","niveis","lat_min","lat_max","dlat","nlat","lon_min","lon_max","dlon","nlon"]
    df=df[[c for c in cols if c in df.columns]]
    out="inventario_dados.csv"; df.to_csv(out,index=False)
    print(f"\n-> {out}  ({len(df)} variáveis em {df.arquivo.nunique()} arquivos)")
    # resumo por arquivo (período/grade)
    print("\n=== resumo por arquivo (.nc) ===")
    nc=df[df.tipo=="nc"].drop_duplicates("arquivo")
    for _,r in nc.iterrows():
        print(f"  {r.arquivo:42s} {r.data_ini}..{r.data_fim} | niv[{r.niveis[:30]}] | "
              f"lat {r.lat_min}..{r.lat_max} lon {r.lon_min}..{r.lon_max}")

if __name__=="__main__":
    main()
