#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
09 — Retro-trajetórias 3D CINEMÁTICAS e ISENTRÓPICAS das massas de ar do RS (maio→abril).
   Corrige a limitação do 08 (isobárico): agora a parcela sobe/desce.
     --modo 3d          : integra (lat, lon, p) com u, v e w(=omega) do ERA5  [lida com a perna 2 diabática]
     --modo isentropico : parcela conserva θ (adiabático); a pressão é diagnosticada da θ  [ideal p/ perna 1]
   Registra ao longo do caminho: lat, lon, pressão, θ e o AOD de fumaça amostrado.

Pré-req:  pip install "cdsapi>=0.7.2" xarray netCDF4 numpy pandas matplotlib
Uso:
   python 09_trajetorias_3d_isentropico.py --modo 3d --teste
   python 09_trajetorias_3d_isentropico.py --modo 3d
   python 09_trajetorias_3d_isentropico.py --modo isentropico
Saída: resultados/traj_<modo>.csv  +  resultados/fig_traj_<modo>.png
"""
import argparse, os, numpy as np, pandas as pd, xarray as xr
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

AREA=[10,-80,-38,-34]                 # N,W,S,E
LEVS=[1000,925,850,700,600,500,400,300]
PULSOS={"1o_02-06mai":["2024-05-03","2024-05-05"],"2o_11-13mai":["2024-05-12","2024-05-13"]}
SEEDS=[(-29.5,-52.0),(-30.5,-53.5),(-28.5,-51.0),(-31.0,-54.5),(-29.0,-50.0)]
P0=850.0; DTH_DL=6; KAPPA=0.2854
CFG={"3d":dict(dias=7,dth=1),          # 3D: janela curta + passo horário (dominar o w ruidoso)
     "isentropico":dict(dias=14,dth=6)}  # isentrópico: estável, janela longa p/ perna 1

def _retrieve(c,base,out):
    if os.path.exists(out): return
    last=None
    for extra in [{"data_format":"netcdf","download_format":"unarchived"},{"format":"netcdf"}]:
        try: c.retrieve("reanalysis-era5-pressure-levels",{**base,**extra},out); return
        except Exception as e: last=e
    raise SystemExit(f"[ERRO] ERA5 winds/T: {last}")

def baixa(out):
    import cdsapi
    _retrieve(cdsapi.Client(),{
        "product_type":"reanalysis",
        "variable":["u_component_of_wind","v_component_of_wind","vertical_velocity","temperature"],
        "pressure_level":[str(x) for x in LEVS],
        "year":["2024"],"month":["04","05"],"day":[f"{d:02d}" for d in range(1,32)],
        "time":[f"{h:02d}:00" for h in range(0,24,DTH_DL)],"area":AREA},out)

def _open(p):
    import zipfile
    if zipfile.is_zipfile(p):
        z=zipfile.ZipFile(p); ncs=[n for n in z.namelist() if n.endswith(".nc")]; d=p+"_x"; os.makedirs(d,exist_ok=True)
        for n in ncs: z.extract(n,d)
        return xr.open_mfdataset([os.path.join(d,n) for n in ncs]) if len(ncs)>1 else xr.open_dataset(os.path.join(d,ncs[0]))
    return xr.open_dataset(p)

def dims(ds):
    return ('latitude' if 'latitude' in ds else 'lat',
            'longitude' if 'longitude' in ds else 'lon',
            'pressure_level' if 'pressure_level' in ds.dims else 'level',
            'valid_time' if 'valid_time' in ds.dims else 'time')

def coluna(ds, t, la, lo, latn,lonn,levn,tn):
    s=ds.interp({tn:np.datetime64(t),latn:la,lonn:lo},method="linear")
    lev=s[levn].values.astype(float)
    u=s["u"].values; v=s["v"].values; w=s["w"].values; T=s["t"].values
    o=np.argsort(lev)                      # pressão crescente
    return lev[o],u[o],v[o],w[o],T[o]

def vento_3d(ds,t,la,lo,p,dd):
    lev,u,v,w,T=coluna(ds,t,la,lo,*dd)
    return (np.interp(p,lev,u), np.interp(p,lev,v), np.interp(p,lev,w),
            np.interp(p,lev,T)*(1000.0/p)**KAPPA)

def vento_iso(ds,t,la,lo,th0,dd):
    lev,u,v,w,T=coluna(ds,t,la,lo,*dd)
    th=T*(1000.0/lev)**KAPPA
    oo=np.argsort(th)                       # θ crescente
    p=np.interp(th0,th[oo],lev[oo])         # pressão da superfície isentrópica θ0
    return np.interp(p,lev,u), np.interp(p,lev,v), p

def integra(ds,la0,lo0,t0,modo,dd,dias,dth):
    dt=dth*3600.0; la,lo,t=la0,lo0,pd.Timestamp(t0)
    if modo=="3d":
        _,_,_,th=vento_3d(ds,t,la,lo,P0,dd); p=P0
    else:
        lev,u,v,w,T=coluna(ds,t,la,lo,*dd); th=float(np.interp(P0,lev,T)*(1000.0/P0)**KAPPA); p=P0
    tr=[(t,la,lo,p,th)]
    for _ in range(int(dias*24/dth)):
        try:
            if modo=="3d":
                u1,v1,w1,_=vento_3d(ds,t,la,lo,p,dd)
                lam=la-(v1*dt/2)/111320.0; lom=lo-(u1*dt/2)/(111320.0*np.cos(np.radians(la)))
                pm=min(1000.0,max(150.0, p-(w1*dt/2)/100.0))          # w em Pa/s -> hPa: /100
                u2,v2,w2,thn=vento_3d(ds,t-pd.Timedelta(hours=dth/2),lam,lom,pm,dd)
                la-=v2*dt/111320.0; lo-=u2*dt/(111320.0*np.cos(np.radians(la)))
                dp=max(-60.0,min(60.0,(w2*dt)/100.0))                 # trava anti-blowup (hPa/passo)
                p=min(1000.0,max(150.0,p-dp)); th=thn
            else:
                u1,v1,p1=vento_iso(ds,t,la,lo,th,dd)
                lam=la-(v1*dt/2)/111320.0; lom=lo-(u1*dt/2)/(111320.0*np.cos(np.radians(la)))
                u2,v2,p2=vento_iso(ds,t-pd.Timedelta(hours=dth/2),lam,lom,th,dd)
                la-=v2*dt/111320.0; lo-=u2*dt/(111320.0*np.cos(np.radians(la))); p=p2
            t-=pd.Timedelta(hours=dth)
            if not (AREA[2]<la<AREA[0] and AREA[1]<lo<AREA[3]): break
            tr.append((t,la,lo,p,th))
        except Exception: break
    return tr

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--modo",choices=["3d","isentropico"],required=True)
    ap.add_argument("--teste",action="store_true"); ap.add_argument("--outdir",default="resultados")
    a=ap.parse_args(); os.makedirs(a.outdir,exist_ok=True)
    nc=f"{a.outdir}/_era5_uvwt_abrmai.nc"; print("baixando/lendo ERA5 (u,v,w,T)..."); baixa(nc); ds=_open(nc); dd=dims(ds)
    cfg=CFG[a.modo]
    if a.modo=="3d":
        ds=ds.assign(w=ds["w"].rolling({dd[3]:3},center=True,min_periods=1).mean())  # suaviza o w ruidoso no tempo
    print(f"modo {a.modo}: janela {cfg['dias']} dias, passo {cfg['dth']} h")
    aod=None; cam=f"{a.outdir}/_cams_brasil_rs.nc"
    if os.path.exists(cam):
        c=_open(cam); aod=(c["omaod550"]+c["bcaod550"]); aod.name="AOD"
    pulsos=PULSOS if not a.teste else {"1o_02-06mai":["2024-05-03"]}; seeds=SEEDS if not a.teste else SEEDS[:2]
    linhas=[]; trajs=[]
    for nome,dd_ in pulsos.items():
        for d in dd_:
            for (la,lo) in seeds:
                tr=integra(ds,la,lo,f"{d}T12:00",a.modo,dd,cfg["dias"],cfg["dth"]); tid=f"{nome}_{d}_{la}_{lo}"
                for (t,y,x,p,th) in tr:
                    av=np.nan
                    if aod is not None:
                        try:
                            tn='valid_time' if 'valid_time' in aod.dims else 'time'
                            av=float(aod.interp({tn:np.datetime64(t),
                                ('latitude' if 'latitude' in aod.dims else 'lat'):y,
                                ('longitude' if 'longitude' in aod.dims else 'lon'):x},method="linear"))
                        except Exception: pass
                    linhas.append({"traj":tid,"pulso":nome,"t":t,"lat":y,"lon":x,"p_hPa":p,"theta_K":th,"AOD":av})
                trajs.append((tid,tr))
    df=pd.DataFrame(linhas); df.to_csv(f"{a.outdir}/traj_{a.modo}.csv",index=False)
    fig,(ax,ax2)=plt.subplots(1,2,figsize=(15,8),gridspec_kw={"width_ratios":[1.4,1]})
    if aod is not None:
        tn='valid_time' if 'valid_time' in aod.dims else 'time'
        m=aod.sel({tn:slice("2024-04-15","2024-05-05")}).mean(tn)
        la_=aod['latitude' if 'latitude' in aod.dims else 'lat'].values; lo_=aod['longitude' if 'longitude' in aod.dims else 'lon'].values
        ax.pcolormesh(lo_,la_,m.values,cmap="inferno",vmin=0,vmax=0.5,shading="auto")
    for tid,tr in trajs:
        arr=np.array([(x,y,p) for (_,y,x,p,_) in tr])
        if len(arr)>1:
            sc=ax.scatter(arr[:,0],arr[:,1],c=arr[:,2],cmap="viridis_r",s=4,vmin=300,vmax=1000)
            ax2.plot([tt for (tt,_,_,_,_) in tr],arr[:,2],lw=0.7,alpha=0.6)
    ax.plot(-61,2.5,"r*",ms=13); ax.text(-61,3.4,"Roraima",color="r",ha="center",fontsize=9)
    ax.plot([-58,-49,-49,-58,-58],[-34,-34,-27,-27,-34],"m-",lw=1.5)
    ax.set_xlim(-80,-34); ax.set_ylim(-38,10); ax.set_xlabel("lon"); ax.set_ylabel("lat")
    cb=fig.colorbar(sc,ax=ax,fraction=0.03); cb.set_label("pressão (hPa)")
    ax.set_title(f"Trajetórias {a.modo} do RS (cor = pressão)")
    ax2.invert_yaxis(); ax2.set_ylabel("pressão (hPa)"); ax2.set_xlabel("data"); ax2.set_title("Excursão vertical (perna 1 → perna 2)")
    plt.savefig(f"{a.outdir}/fig_traj_{a.modo}.png",dpi=150,bbox_inches="tight")
    print(f"-> traj_{a.modo}.csv ({df.traj.nunique()} trajetórias), fig_traj_{a.modo}.png")
    if aod is not None:
        ab=df[df.t<'2024-05-01']; print("Cruzaram AOD>0.15 em abril: %.0f%%"%(100*(ab.groupby('traj').AOD.max()>0.15).mean()))
        print("Pressão média na chegada ao RS: %.0f hPa ; a 10+ dias atrás: %.0f hPa"%(
            df[df.t>'2024-05-10'].p_hPa.mean() if (df.t>'2024-05-10').any() else P0,
            df[df.t<'2024-04-25'].p_hPa.mean() if (df.t<'2024-04-25').any() else P0))

if __name__=="__main__":
    main()
