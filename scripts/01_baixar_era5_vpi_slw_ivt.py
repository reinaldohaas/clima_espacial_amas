#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01 — ERA5: baixa UMA vez a caixa ampla do Brasil e PROCESSA subdomínios, com VPI
     resolvida em VÁRIOS NÍVEIS (dipolo diabático), água supercongelada (SLW) e IVT.

   Correção conceitual: o mecanismo se FORMA a montante, sobre o "rio invisível"
   (corredor aéreo Amazônia/Pantanal -> sul). No RS só CHEGAM VPI e vapor advectados.
   Por isso processamos três recortes da MESMA caixa ampla:
      - rio_invisivel : onde a VPI é gerada (fumaça + calor latente)
      - corredor      : trecho intermediário de advecção
      - rs            : onde VPI+vapor chegam

Reaproveita os .nc já baixados (_era5_pl_brasil_<modo>.nc / _era5_sl_...); não rebaixa.

Pré-req:  pip install "cdsapi>=0.7.2" xarray netCDF4 numpy pandas
Uso:      python 01_baixar_era5_vpi_slw_ivt.py --modo rs   (depois --modo ano)
Saída:    resultados/era5_diario_<dominio>_<modo>.csv  (colunas VPI_<nivel> por nível)
"""
import argparse, os
import numpy as np, pandas as pd, xarray as xr
try:
    import cdsapi
except ImportError:
    raise SystemExit("pip install 'cdsapi>=0.7.2' xarray netCDF4")

G = 9.80665
DOWNLOAD_AREA = [6, -74, -34, -34]          # N,W,S,E — caixa ampla (baixa 1x)
SUBDOMINIOS = {                              # (N, W, S, E)
    "brasil":        ( 6, -74, -34, -34),
    "fogo":          (  2, -70, -20, -50),    # região de queimadas (Amazônia/Pantanal) p/ seca 2o sem.
    "rio_invisivel": (-8, -63, -22, -50),    # corredor-fonte (Amazônia SW/Pantanal/Bolívia)
    "corredor":      (-22,-60, -30, -50),     # trecho intermediário (Paraguai/Paraná)
    "rs":            (-27,-58, -34, -49),      # destino
}
NIVEIS_ALL  = [925,850,700,600,500,400,300]
NIVEIS_LOW  = [850,700]     # ciclônica de baixos níveis
NIVEIS_HIGH = [400,300]     # topo (anticiclônica no dipolo diabático)

def periodo(modo):
    if modo == "rs":   return pd.date_range("2024-04-15","2024-05-25",freq="D")
    if modo == "seca": return pd.date_range("2024-08-01","2024-10-31",freq="D")  # ago-out (leve)
    return pd.date_range("2024-01-01","2024-12-31",freq="D")

def _retrieve(c, dataset, base, out_nc):
    if os.path.exists(out_nc): return
    errs=[]
    for extra in [{"data_format":"netcdf","download_format":"unarchived"},
                  {"data_format":"netcdf"},{"format":"netcdf"}]:
        try: c.retrieve(dataset,{**base,**extra},out_nc); return
        except Exception as e: errs.append(f"  {extra}: {str(e)[:150]}")
    raise SystemExit(f"[ERRO] {dataset}:\n"+"\n".join(errs))

def baixar(modo, out_pl, out_sl):
    dias=periodo(modo)
    anos=sorted({d.strftime('%Y') for d in dias}); meses=sorted({d.strftime('%m') for d in dias})
    ndias=sorted({d.strftime('%d') for d in dias}); horas=["00:00","06:00","12:00","18:00"]
    c=cdsapi.Client()
    _retrieve(c,"reanalysis-era5-pressure-levels",{
        "product_type":"reanalysis",
        "variable":["potential_vorticity","specific_cloud_liquid_water_content","temperature"],
        "pressure_level":[str(x) for x in NIVEIS_ALL],
        "year":anos,"month":meses,"day":ndias,"time":horas,"area":DOWNLOAD_AREA},out_pl)
    _retrieve(c,"reanalysis-era5-single-levels",{
        "product_type":"reanalysis",
        "variable":["vertical_integral_of_eastward_water_vapour_flux",
                    "vertical_integral_of_northward_water_vapour_flux",
                    "total_column_cloud_liquid_water",
                    "mean_total_precipitation_rate"],
        "year":anos,"month":meses,"day":ndias,"time":horas,"area":DOWNLOAD_AREA},out_sl)

def _open(path):
    import zipfile
    if zipfile.is_zipfile(path):
        z=zipfile.ZipFile(path); ncs=[n for n in z.namelist() if n.endswith('.nc')]
        d=path+"_x"; os.makedirs(d,exist_ok=True)
        for n in ncs: z.extract(n,d)
        return xr.open_mfdataset([os.path.join(d,n) for n in ncs]) if len(ncs)>1 else xr.open_dataset(os.path.join(d,ncs[0]))
    return xr.open_dataset(path)

def _names(ds):
    latn='latitude' if 'latitude' in ds else 'lat'
    lonn='longitude' if 'longitude' in ds else 'lon'
    tdim='valid_time' if 'valid_time' in ds.dims else ('time' if 'time' in ds.dims else None)
    return latn,lonn,tdim

def subset(ds, box):
    """box = (N,W,S,E). Trata lon 0..360 e lat decrescente."""
    N,W,S,E=box; latn,lonn,_=_names(ds)
    if float(ds[lonn].max())>180:
        ds=ds.assign_coords({lonn:(((ds[lonn]+180)%360)-180)}).sortby(lonn)
    la=ds[latn].values
    lat_slice=slice(N,S) if la[0]>la[-1] else slice(S,N)
    return ds.sel({latn:lat_slice, lonn:slice(W,E)})

def processar(dom, box, pl_ds, sl_ds):
    pl=subset(pl_ds,box); sl=subset(sl_ds,box)
    lev='pressure_level' if 'pressure_level' in pl.dims else 'level'
    latn,lonn,tdim=_names(pl); sp=[latn,lonn]
    pv=(pl['pv'].mean(dim=sp))*1e6            # PVU, dims (tdim, lev)
    out={}
    lv=[int(x) for x in pl[lev].values]
    for L in NIVEIS_ALL:
        if L in lv: out[f"VPI_{L}"]=pv.sel({lev:L}).values
    # dipolo diabático: baixo - alto (HS: baixo mais ciclônico = mais negativo)
    low=pv.sel({lev:[l for l in NIVEIS_LOW if l in lv]}).mean(dim=lev)
    high=pv.sel({lev:[l for l in NIVEIS_HIGH if l in lv]}).mean(dim=lev)
    out["VPI_baixo"]=low.values; out["VPI_alto"]=high.values
    out["VPI_dipolo"]=(low-high).values
    # água supercongelada integrada (235<T<273 K)
    lvs=np.array(sorted(lv)); dp=np.gradient(lvs)*100.0
    slw=None
    for i,L in enumerate(lvs):
        cl=pl['clwc'].sel({lev:int(L)}); tt=pl['t'].sel({lev:int(L)})
        col=((cl.where((tt>235.15)&(tt<273.15),0.0))*dp[i]/G).mean(dim=sp)
        slw=col if slw is None else slw+col
    out["SLW_kg_m2"]=slw.values
    # IVT + TCLW da caixa recortada
    ee=[v for v in sl if v in ("p71.162","viwve") or "eastward" in v.lower()]
    nn=[v for v in sl if v in ("p72.162","viwvn") or "northward" in v.lower()]
    e=sl[ee[0]].mean(dim=sp); n=sl[nn[0]].mean(dim=sp)
    out["IVT_kg_m_s"]=np.sqrt(e**2+n**2).values
    if "tclw" in sl: out["TCLW_kg_m2"]=sl["tclw"].mean(dim=sp).values
    prc=[v for v in sl.data_vars if v in ("mtpr","avg_tprate") or "tprate" in v.lower() or "precip" in v.lower()]
    if prc:                                                                # nome do var de chuva varia no novo CDS
        pr=sl[prc[0]].mean(dim=sp); out["PRECIP_rate"]=pr.values
        if "tclw" in sl:
            cw=sl["tclw"].mean(dim=sp); out["EFIC_PRECIP"]=(pr/(cw+1e-9)).values
    idxt=pd.to_datetime(pl[tdim].values)
    df=pd.DataFrame(out,index=idxt).resample("1D").mean()
    df.index.name="data"; df["dominio"]=dom
    return df

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--modo",choices=["rs","seca","ano"],default="rs")
    ap.add_argument("--outdir",default="resultados"); ap.add_argument("--datadir",default="dados"); a=ap.parse_args(); os.makedirs(a.outdir,exist_ok=True)
    pl=f"{a.datadir}/era5/_era5_pl_brasil_{a.modo}.nc"; sl=f"{a.datadir}/era5/_era5_sl_brasil_{a.modo}.nc"
    print(f"baixando/lendo ERA5 caixa ampla ({a.modo})..."); baixar(a.modo,pl,sl)
    plds=_open(pl); slds=_open(sl)
    for dom,box in SUBDOMINIOS.items():
        d=processar(dom,box,plds,slds); out=f"{a.outdir}/era5_diario_{dom}_{a.modo}.csv"
        d.to_csv(out); print(f"[{dom}] -> {out} ({len(d)} dias, VPI em {len(NIVEIS_ALL)} níveis)")

if __name__=="__main__":
    main()
