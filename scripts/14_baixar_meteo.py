#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
14 — Variáveis METEOROLÓGICAS clássicas + PRECIPITAÇÃO + VAPOR, janela 27/04–15/05 (rápido).
   Só campos de SUPERFÍCIE/coluna (single-level do ERA5) => download leve. Pega tudo de uma vez,
   cobrindo a janela inteira, e resolve dois pontos que ficaram pendentes:
     • a PRECIPITAÇÃO (que não estava nas tabelas)
     • o VAPOR (TCWV) o PERÍODO TODO (antes só IVT, e só parte do tempo)

   Variáveis (as mais usadas em meteo, todas single-level = baixam rápido):
     msl (pressão nível do mar), t2m, d2m (orvalho), u10/v10 (vento 10 m),
     cape, cin, tcwv (água precipitável), mtpr (taxa de chuva), tcc (cobertura de nuvem),
     kx (índice K), totalx (Total Totals), e IVT (fluxo integrado de vapor).

Pré-req:  pip install "cdsapi>=0.7.2" xarray netCDF4 numpy pandas matplotlib
Uso:      python 14_baixar_meteo.py                 # janela padrão 27/04–15/05
          python 14_baixar_meteo.py --ini 2024-04-27 --fim 2024-05-15
Saída:    resultados/meteo_horario_<dom>.csv, meteo_diario_<dom>.csv, fig_meteo_ondas.png
"""
import argparse, os, numpy as np, pandas as pd, xarray as xr
try: import cdsapi
except ImportError: raise SystemExit("pip install 'cdsapi>=0.7.2' xarray netCDF4 matplotlib")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
try: from ondas_config import ONDAS, CAIXA
except Exception:
    ONDAS={"O0_precond_27-30abr":("2024-04-27","2024-04-30"),"O1_toros_01-04mai":("2024-05-01","2024-05-04"),
           "O2_surto_06-08mai":("2024-05-06","2024-05-08"),"O3_cheia_10-13mai":("2024-05-10","2024-05-13")}
    CAIXA=dict(latmin=-36.0,latmax=-25.0,lonmin=-60.0,lonmax=-47.0)

AREA=[CAIXA["latmax"],CAIXA["lonmin"],CAIXA["latmin"],CAIXA["lonmax"]]   # N,W,S,E
VARS=["mean_sea_level_pressure","2m_temperature","2m_dewpoint_temperature",
      "10m_u_component_of_wind","10m_v_component_of_wind",
      "convective_available_potential_energy","convective_inhibition",
      "total_column_water_vapour","mean_total_precipitation_rate","total_cloud_cover",
      "k_index","total_totals_index",
      "vertical_integral_of_eastward_water_vapour_flux","vertical_integral_of_northward_water_vapour_flux"]
# subdomínios (N,W,S,E) p/ recortar da mesma caixa
SUBDOM={"rs":(-27,-58,-34,-49),"corredor":(-25,-60,-30,-49),"caixa":(CAIXA["latmax"],CAIXA["lonmin"],CAIXA["latmin"],CAIXA["lonmax"])}

def _retrieve(c,base,out):
    if os.path.exists(out): return
    errs=[]
    for extra in [{"data_format":"netcdf","download_format":"unarchived"},{"data_format":"netcdf"},{"format":"netcdf"}]:
        try: c.retrieve("reanalysis-era5-single-levels",{**base,**extra},out); return
        except Exception as e: errs.append(str(e)[:120])
    raise SystemExit("[ERRO] ERA5 single-levels:\n"+"\n".join(errs))

def baixar(ini,fim,out):
    dias=pd.date_range(ini,fim,freq="D")
    _retrieve(cdsapi.Client(),{
        "product_type":"reanalysis","variable":VARS,
        "year":sorted({d.strftime('%Y') for d in dias}),
        "month":sorted({d.strftime('%m') for d in dias}),
        "day":sorted({d.strftime('%d') for d in dias}),
        "time":[f"{h:02d}:00" for h in range(24)],"area":AREA},out)

def _open(p):
    import zipfile
    if zipfile.is_zipfile(p):
        z=zipfile.ZipFile(p); ncs=[n for n in z.namelist() if n.endswith('.nc')]; d=p+"_x"; os.makedirs(d,exist_ok=True)
        for n in ncs: z.extract(n,d)
        return xr.open_mfdataset([os.path.join(d,n) for n in ncs]) if len(ncs)>1 else xr.open_dataset(os.path.join(d,ncs[0]))
    return xr.open_dataset(p)

def _nome(ds,*cand):
    for c in cand:
        if c in ds: return c
    return None

def subset(ds,box):
    N,W,S,E=box; latn=_nome(ds,'latitude','lat'); lonn=_nome(ds,'longitude','lon')
    if float(ds[lonn].max())>180: ds=ds.assign_coords({lonn:(((ds[lonn]+180)%360)-180)}).sortby(lonn)
    la=ds[latn].values; sl=slice(N,S) if la[0]>la[-1] else slice(S,N)
    return ds.sel({latn:sl,lonn:slice(W,E)})

def processar(dom,box,ds):
    d=subset(ds,box); latn=_nome(d,'latitude','lat'); lonn=_nome(d,'longitude','lon'); sp=[latn,lonn]
    tdim=_nome(d,'valid_time','time')
    g=lambda *c:(d[_nome(d,*c)].mean(dim=sp).values if _nome(d,*c) else np.nan)
    out={}
    out["MSLP_hPa"]=g('msl')/100.0
    out["T2m_C"]=g('t2m')-273.15; out["Td2m_C"]=g('d2m')-273.15
    u=g('u10'); v=g('v10'); out["vento_ms"]=np.sqrt(u**2+v**2); out["vento_dir"]=(270-np.degrees(np.arctan2(v,u)))%360
    out["CAPE_Jkg"]=g('cape'); out["CIN_Jkg"]=g('cin')
    out["TCWV_mm"]=g('tcwv','tcw'); out["TCC"]=g('tcc')
    out["Kindex"]=g('kx','k_index'); out["TotalTotals"]=g('totalx','total_totals_index')
    mtpr=_nome(d,'mtpr','avg_tprate');
    if mtpr: out["PRECIP_mm_h"]=d[mtpr].mean(dim=sp).values*3600.0   # kg/m2/s -> mm/h
    e=_nome(d,'p71.162','viwve'); n=_nome(d,'p72.162','viwvn')
    if e and n: out["IVT_kg_m_s"]=np.sqrt(d[e].mean(dim=sp).values**2+d[n].mean(dim=sp).values**2)
    idx=pd.to_datetime(d[tdim].values)
    hor=pd.DataFrame(out,index=idx); hor.index.name="datetime"; hor["dominio"]=dom
    dia=hor.drop(columns="dominio").resample("1D").mean()
    if "PRECIP_mm_h" in dia: dia["PRECIP_mm_dia"]=hor["PRECIP_mm_h"].resample("1D").mean()*24.0
    dia.index.name="data"; dia["dominio"]=dom
    return hor,dia

def figura(diarios,outdir):
    d=diarios["rs"]
    paineis=[("PRECIP_mm_dia","Chuva (mm/dia)"),("TCWV_mm","Água precipitável TCWV (mm)"),
             ("CAPE_Jkg","CAPE (J/kg)"),("MSLP_hPa","Pressão nível do mar (hPa)"),
             ("IVT_kg_m_s","IVT (kg m⁻¹ s⁻¹)"),("vento_ms","Vento 10 m (m/s)")]
    paineis=[(c,t) for c,t in paineis if c in d.columns]
    cores=["#999999","#D55E00","#CC79A7","#0072B2","#E69F00"]
    fig,ax=plt.subplots(len(paineis),1,figsize=(11,2.3*len(paineis)),sharex=True); ax=np.atleast_1d(ax)
    for i,(c,t) in enumerate(paineis):
        for j,(nome,(i0,i1)) in enumerate(ONDAS.items()):
            ax[i].axvspan(pd.Timestamp(i0),pd.Timestamp(i1)+pd.Timedelta(hours=23),color=cores[j%len(cores)],alpha=0.13)
        ax[i].plot(d.index,d[c],marker="o",ms=4,lw=1.5,color="#111"); ax[i].set_title(t,loc="left",fontsize=11); ax[i].grid(alpha=.3)
    for j,(nome,(i0,i1)) in enumerate(ONDAS.items()):
        xm=pd.Timestamp(i0)+(pd.Timestamp(i1)-pd.Timestamp(i0))/2
        ax[0].text(xm,ax[0].get_ylim()[1],nome.split('_')[0],ha="center",va="bottom",fontsize=9,fontweight="bold",color=cores[j%len(cores)])
    fig.suptitle("Meteorologia do evento por onda (RS) — ERA5",fontsize=13); fig.tight_layout(rect=(0,0,1,0.98))
    p=f"{outdir}/fig_meteo_ondas.png"; fig.savefig(p,dpi=150,bbox_inches="tight"); print("->",p)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ini",default="2024-04-27"); ap.add_argument("--fim",default="2024-05-15")
    ap.add_argument("--outdir",default="resultados"); ap.add_argument("--datadir",default="dados"); a=ap.parse_args(); os.makedirs(a.outdir,exist_ok=True)
    nc=f"{a.datadir}/era5/_era5_meteo_{a.ini}_{a.fim}.nc"
    print(f"baixando ERA5 single-level {a.ini}..{a.fim} (janela leve)..."); baixar(a.ini,a.fim,nc)
    ds=_open(nc); diarios={}
    for dom,box in SUBDOM.items():
        hor,dia=processar(dom,box,ds); diarios[dom]=dia
        hor.to_csv(f"{a.outdir}/meteo_horario_{dom}.csv"); dia.to_csv(f"{a.outdir}/meteo_diario_{dom}.csv")
        print(f"[{dom}] -> meteo_horario/diario ({len(hor)} h, {len(dia)} dias)")
    figura(diarios,a.outdir)

if __name__=="__main__":
    main()
