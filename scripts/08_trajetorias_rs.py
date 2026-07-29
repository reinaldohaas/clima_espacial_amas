#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
08 — Retro-trajetórias (Lagrangiano) das massas de ar que caíram no RS em maio/2024.
   Segue a massa de ar (não a caixa): lança parcelas a partir dos PULSOS de chuva do RS
   e integra para trás ~14 dias (para dentro de ABRIL = perna 1, pré-condicionamento),
   amostrando o AOD de fumaça ao longo do caminho — para ver se a parcela passou pela
   PLUMA DO NORTE (Roraima/Venezuela) antes de descarregar (perna 2).

   Trajetória cinemática 2D em superfície isobárica (850 e 700 hPa; w desprezado — 1a ordem).

Pré-req:  pip install "cdsapi>=0.7.2" xarray netCDF4 numpy pandas matplotlib
Uso:
   python 08_trajetorias_rs.py --teste          # 1 pulso, poucos seeds (validar rápido)
   python 08_trajetorias_rs.py                  # os dois pulsos, malha de seeds
Saída: resultados/trajetorias_rs.csv  +  resultados/fig_trajetorias.png
   (usa resultados/_cams_brasil_rs.nc para amostrar o AOD; se faltar, só desenha as trajetórias)
"""
import argparse, os, numpy as np, pandas as pd, xarray as xr
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

AREA=[10,-80,-38,-34]           # N,W,S,E — cobre do RS até Roraima/Venezuela
NIVEIS=[850,700]
# dias de release (perna 2) e seeds sobre o RS/Serra Gaúcha
PULSOS={"1o_pulso_02-06mai":["2024-05-03","2024-05-05"],
        "2o_pulso_11-13mai":["2024-05-12","2024-05-13"]}
SEEDS=[(-29.5,-52.0),(-30.5,-53.5),(-28.5,-51.0),(-31.0,-54.5),(-29.0,-50.0)]  # lat,lon no RS
DIAS_ATRAS=14; DT_H=6

def _retrieve(c,base,out):
    if os.path.exists(out): return
    for extra in [{"data_format":"netcdf","download_format":"unarchived"},{"format":"netcdf"}]:
        try: c.retrieve("reanalysis-era5-pressure-levels",{**base,**extra},out); return
        except Exception as e: last=e
    raise SystemExit(f"[ERRO] ventos ERA5: {last}")

def baixa_ventos(out):
    import cdsapi
    dias=pd.date_range("2024-04-01","2024-05-20",freq="D")
    _retrieve(cdsapi.Client(),{
        "product_type":"reanalysis","variable":["u_component_of_wind","v_component_of_wind"],
        "pressure_level":[str(x) for x in NIVEIS],
        "year":["2024"],"month":["04","05"],
        "day":[f"{d:02d}" for d in range(1,32)],
        "time":[f"{h:02d}:00" for h in range(0,24,DT_H)],"area":AREA},out)

def _open(p):
    import zipfile
    if zipfile.is_zipfile(p):
        z=zipfile.ZipFile(p); ncs=[n for n in z.namelist() if n.endswith(".nc")]
        d=p+"_x"; os.makedirs(d,exist_ok=True)
        for n in ncs: z.extract(n,d)
        return xr.open_mfdataset([os.path.join(d,n) for n in ncs]) if len(ncs)>1 else xr.open_dataset(os.path.join(d,ncs[0]))
    return xr.open_dataset(p)

def integra(ds, lat0, lon0, lev, t0, ndias, dth):
    latn='latitude' if 'latitude' in ds else 'lat'; lonn='longitude' if 'longitude' in ds else 'lon'
    levn='pressure_level' if 'pressure_level' in ds.dims else 'level'
    tn='valid_time' if 'valid_time' in ds.dims else 'time'
    def wind(t,la,lo):
        s=ds.interp({tn:np.datetime64(t),levn:lev,latn:la,lonn:lo},method="linear")
        return float(s["u"]), float(s["v"])
    lat,lon=lat0,lon0; t=pd.Timestamp(t0); dt=dth*3600.0
    traj=[(t,lat,lon)]
    for _ in range(int(ndias*24/dth)):
        try:
            u1,v1=wind(t,lat,lon)
            latm=lat-(v1*dt/2)/111320.0; lonm=lon-(u1*dt/2)/(111320.0*np.cos(np.radians(lat)))
            u2,v2=wind(t-pd.Timedelta(hours=dth/2),latm,lonm)
            lat=lat-(v2*dt)/111320.0; lon=lon-(u2*dt)/(111320.0*np.cos(np.radians(lat)))
            t=t-pd.Timedelta(hours=dth)
            if not (AREA[2]<lat<AREA[0] and AREA[1]<lon<AREA[3]): break
            traj.append((t,lat,lon))
        except Exception: break
    return traj

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--teste",action="store_true"); ap.add_argument("--outdir",default="resultados"); ap.add_argument("--datadir",default="dados")
    a=ap.parse_args(); os.makedirs(a.outdir,exist_ok=True)
    wind_nc=f"{a.datadir}/era5/_era5_ventos_abrmai.nc"
    print("baixando/lendo ventos ERA5..."); baixa_ventos(wind_nc); ds=_open(wind_nc)
    # AOD para amostrar (opcional)
    aod=None
    cam=f"{a.datadir}/cams/_cams_brasil_rs.nc"
    if os.path.exists(cam):
        c=_open(cam); aod=(c["omaod550"]+c["bcaod550"]); aod.name="AOD"
    pulsos=PULSOS if not a.teste else {"1o_pulso_02-06mai":["2024-05-03"]}
    seeds=SEEDS if not a.teste else SEEDS[:2]
    linhas=[]; trajs=[]
    for nome,dias in pulsos.items():
        for d in dias:
            for (la,lo) in seeds:
                for lev in (NIVEIS if not a.teste else [850]):
                    tr=integra(ds,la,lo,lev,f"{d}T12:00",DIAS_ATRAS,DT_H)
                    tid=f"{nome}_{d}_{la}_{lo}_{lev}"
                    for (t,y,x) in tr:
                        av=np.nan
                        if aod is not None:
                            try:
                                tn='valid_time' if 'valid_time' in aod.dims else 'time'
                                av=float(aod.interp({tn:np.datetime64(t),
                                        ('latitude' if 'latitude' in aod.dims else 'lat'):y,
                                        ('longitude' if 'longitude' in aod.dims else 'lon'):x},method="linear"))
                            except Exception: pass
                        linhas.append({"traj":tid,"pulso":nome,"nivel":lev,"t":t,"lat":y,"lon":x,"AOD":av})
                    trajs.append((tid,lev,tr))
    df=pd.DataFrame(linhas); df.to_csv(f"{a.outdir}/trajetorias_rs.csv",index=False)
    # figura sobre o AOD médio de abril
    fig,ax=plt.subplots(figsize=(8,9))
    if aod is not None:
        tn='valid_time' if 'valid_time' in aod.dims else 'time'
        m=aod.sel({tn:slice("2024-04-15","2024-05-05")}).mean(tn)
        la_=aod['latitude' if 'latitude' in aod.dims else 'lat'].values; lo_=aod['longitude' if 'longitude' in aod.dims else 'lon'].values
        ax.pcolormesh(lo_,la_,m.values,cmap="inferno",vmin=0,vmax=0.5,shading="auto")
    for tid,lev,tr in trajs:
        arr=np.array([(x,y) for (_,y,x) in tr])
        if len(arr)>1: ax.plot(arr[:,0],arr[:,1],lw=0.8,color=("cyan" if lev==850 else "yellow"),alpha=0.7)
    ax.plot(-61,2.5,"r*",ms=13); ax.text(-61,3.3,"Roraima",color="r",ha="center",fontsize=9)
    ax.plot([-58,-49,-49,-58,-58],[-34,-34,-27,-27,-34],"m-",lw=1.5)
    ax.set_xlim(-80,-34); ax.set_ylim(-38,10); ax.set_xlabel("lon"); ax.set_ylabel("lat")
    ax.set_title("Retro-trajetórias do RS (ciano=850, amarelo=700 hPa) sobre a fumaça de abril")
    plt.savefig(f"{a.outdir}/fig_trajetorias.png",dpi=150,bbox_inches="tight")
    print(f"-> trajetorias_rs.csv ({df.traj.nunique()} trajetórias) e fig_trajetorias.png")
    if aod is not None:
        # fração de trajetórias que cruzaram fumaça relevante (AOD>0.15) na perna 1 (abril)
        abril=df[df.t< '2024-05-01']
        cruz=abril.groupby("traj").AOD.max()
        print("Trajetórias que cruzaram AOD>0.15 em abril: %.0f%%"%(100*(cruz>0.15).mean()))

if __name__=="__main__":
    main()
