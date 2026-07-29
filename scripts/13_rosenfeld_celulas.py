#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
13 (v2) — Rosenfeld POR CÉLULA (GOES-16), por ONDA — células ancoradas nas descargas (GLM),
     separadas em FRENTE x TRASEIRA pelo movimento, r_e(T) via reflectância de 3,9 µm, + figura
     das imagens de satélite com cada célula CONTORNADA e NOMEADA (C1, C2, ...).

   MUDANÇAS DA v2 (corrigem o que a v1 mostrou):
     • BLOB: o núcleo agora é detectado em Tb < T_NUCLEO (−55 °C) -> separa supercélulas individuais,
       em vez de fundir todo o escudo do MCS num objeto só (o "C2 gigante" da v1).
     • r_e TRUNCADO: o r_e é amostrado num ENTORNO CRESCIDO de cada núcleo (dilatação geodésica até
       Tb < T_SAIA = −10 °C) -> recupera o ramo QUENTE de crescimento da gota, onde a diferença
       frente×traseira de fato aparece (a v1 só via a calota glaciada).
     • DIA/NOITE por PIXEL: o r_e é calculado onde sza_pixel < SZA_MAX (não pela média da caixa),
       aproveitando a parte ensolarada mesmo em quadros de fim de tarde.
     • ONDAS: lê ondas_config.py (--onda O1/O2/...); nada de janela chumbada.

   r_e HONESTO: a grandeza rigorosa é a reflectância de 3,9 µm (no CSV). O r_e em µm é PROXY
   qualitativo rotulado (sem LUT escondida). Só vale de dia.

Pré-req:  pip install s3fs xarray netCDF4 h5netcdf numpy pandas matplotlib scipy
Uso:
   python 13_rosenfeld_celulas.py --onda O1_toros_01-04mai --passo 1
   python 13_rosenfeld_celulas.py --onda O2_surto_06-08mai --passo 1
   python 13_rosenfeld_celulas.py --onda O1_toros_01-04mai --sem-frente-traseira
Saída (em resultados/rosenfeld_celulas/<onda>/): curva_reT, celulas_tabela, fig_reT, fig_celulas_*
"""
import argparse, os, tempfile, datetime as dt, numpy as np, pandas as pd
try:
    import s3fs, xarray as xr
    from scipy import ndimage
except ImportError:
    raise SystemExit("pip install s3fs xarray netCDF4 h5netcdf scipy")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
try:
    from ondas_config import ONDAS, CAIXA, CIDADES
except Exception:
    ONDAS={"O1_toros_01-04mai":("2024-05-01","2024-05-04"),"O2_surto_06-08mai":("2024-05-06","2024-05-08"),
           "O3_cheia_10-13mai":("2024-05-10","2024-05-13")}
    CAIXA=dict(latmin=-36.0,latmax=-25.0,lonmin=-60.0,lonmax=-47.0)
    CIDADES={"Porto Alegre":(-30.03,-51.23),"Florianópolis":(-27.60,-48.55),"Montevidéu":(-34.90,-56.16)}

BUCKET="noaa-goes16"; CMIP=f"{BUCKET}/ABI-L2-CMIPF"; GLM=f"{BUCKET}/GLM-L2-LCFA"
HORAS_UT=list(range(11,24))
T_NUCLEO=-55.0        # °C: núcleo da célula (detecção) — separa supercélulas
T_SAIA=-10.0          # °C: até onde o entorno cresce (recupera o ramo quente do r_e)
DILATA_PIX=15         # crescimento máx do entorno (px ~2km): ~30 km de saia ao redor do núcleo
AREA_MIN_PIX=150      # núcleo mínimo GRANDE (~600 km²) — descarta celulazinhas (pedido do usuário)
TOPN=8                # mantém no máx N maiores núcleos por quadro
FLASH_MIN=5; SZA_MAX=78.0; FLASH_JANELA_MIN=5
E0_39=None

# ---------- navegação ABI ----------
def _proj_params(ds):
    g=ds["goes_imager_projection"]
    return (float(g.attrs["perspective_point_height"])+float(g.attrs["semi_major_axis"]),
            float(g.attrs["semi_major_axis"]), float(g.attrs["semi_minor_axis"]),
            np.radians(float(g.attrs["longitude_of_projection_origin"])))

def _xy_para_latlon(x, y, prm):
    H, r_eq, r_pol, lam0 = prm
    cx, cy = np.cos(x), np.cos(y); sx, sy = np.sin(x), np.sin(y)
    a = sx**2 + cx**2*(cy**2 + (r_eq**2/r_pol**2)*sy**2)
    b = -2.0*H*cx*cy; c = H**2 - r_eq**2; disc = b**2 - 4*a*c
    with np.errstate(invalid="ignore"):
        rs = (-b - np.sqrt(disc))/(2*a)
        Sx = rs*cx*cy; Sy = -rs*sx; Sz = rs*cx*sy
        lat = np.degrees(np.arctan((r_eq**2/r_pol**2)*Sz/np.sqrt((H-Sx)**2 + Sy**2)))
        lon = np.degrees(lam0 - np.arctan(Sy/(H-Sx)))
    bad = disc < 0
    return np.where(bad,np.nan,lat), np.where(bad,np.nan,lon)

def _janela_caixa(x1d, y1d, prm, cx):
    s=8; Xc,Yc=np.meshgrid(x1d[::s],y1d[::s]); latc,lonc=_xy_para_latlon(Xc,Yc,prm)
    m=(latc>=cx["latmin"]-1)&(latc<=cx["latmax"]+1)&(lonc>=cx["lonmin"]-1)&(lonc<=cx["lonmax"]+1)
    if not m.any(): return None
    jj,ii=np.where(m)
    return (max(0,(jj.min()-1)*s),min(len(y1d),(jj.max()+2)*s),
            max(0,(ii.min()-1)*s),min(len(x1d),(ii.max()+2)*s))

def _zenital(lat, lon, when):
    d=when.timetuple().tm_yday; frac=when.hour+when.minute/60.0
    decl=np.radians(-23.44)*np.cos(np.radians(360.0/365.0*(d+10)))
    LST=frac+lon/15.0; H=np.radians(15.0*(LST-12.0)); la=np.radians(lat)
    cosz=np.sin(la)*np.sin(decl)+np.cos(la)*np.cos(decl)*np.cos(H)
    return np.degrees(np.arccos(np.clip(cosz,-1,1)))

# ---------- Planck / reflectância 3,9 µm ----------
def _planck_L(Tb, lam_um):
    h=6.62607e-34; c=2.99792e8; k=1.38065e-23; lam=lam_um*1e-6
    return (2*h*c**2/lam**5) / (np.exp(h*c/(lam*k*Tb))-1) * 1e-6

def _reflectancia_39(Tb7, Tb14, sza_deg):
    global E0_39; lam=3.9
    L_tot=_planck_L(Tb7, lam); L_ter=_planck_L(Tb14, lam)
    if E0_39 is None: E0_39=_planck_L(5772.0, lam)*np.pi*(6.957e8/1.496e11)**2
    mu=np.cos(np.radians(np.clip(sza_deg,0,89)))
    refl=np.pi*(L_tot-L_ter)/(E0_39*np.maximum(mu,0.02))
    return np.clip(refl, 0, 1.0)

def _refl_para_re(refl):
    """PROXY qualitativo reflectância->r_e (µm). refl alta => gota pequena. Faixa ~5..35µm."""
    return np.clip(5.0 + 30.0*np.exp(-refl/0.012), 5.0, 40.0)

# ---------- leitura CMIP / GLM ----------
def _primeiro(fs, banda, when):
    bb=int(banda[1:]); doy=when.timetuple().tm_yday
    pref=f"{CMIP}/{when.year}/{doy:03d}/{when.hour:02d}/"
    try: arqs=fs.ls(pref)
    except Exception: return None
    cand=[a for a in arqs if f"-M6C{bb:02d}_" in a or f"-M3C{bb:02d}_" in a]
    return sorted(cand)[0] if cand else None

def _le_cmip(fs, banda, when, win_cache):
    a=_primeiro(fs, banda, when)
    if a is None: return None
    tmp=tempfile.NamedTemporaryFile(suffix=".nc", delete=False).name
    try:
        fs.get(a, tmp); ds=xr.open_dataset(tmp, engine="h5netcdf")
        prm=_proj_params(ds); x1d=ds["x"].values; y1d=ds["y"].values; key=(len(x1d),len(y1d))
        if key not in win_cache: win_cache[key]=_janela_caixa(x1d,y1d,prm,CAIXA)
        win=win_cache[key]
        if win is None: ds.close(); return None
        j0,j1,i0,i1=win; cmi=ds["CMI"].values[j0:j1,i0:i1].astype("float32")
        X,Y=np.meshgrid(x1d[i0:i1],y1d[j0:j1]); lat,lon=_xy_para_latlon(X,Y,prm); ds.close()
        return dict(cmi=cmi, lat=lat, lon=lon)
    except Exception as e:
        print(f"    ! {banda} {when:%m-%d %HZ}: {str(e)[:60]}"); return None
    finally:
        try: os.remove(tmp)
        except OSError: pass

def _le_glm(fs, when, cx, jan_min):
    las=[]; los=[]
    for off in range(-jan_min, jan_min+1):
        t=when+dt.timedelta(minutes=off); doy=t.timetuple().tm_yday
        pref=f"{GLM}/{t.year}/{doy:03d}/{t.hour:02d}/"
        try: arqs=fs.ls(pref)
        except Exception: continue
        alvo=[a for a in arqs if f"_s{t.year}{doy:03d}{t.hour:02d}{t.minute:02d}" in a]
        for a in alvo:
            try:
                with fs.open(a) as f:
                    g=xr.open_dataset(f, engine="h5netcdf")
                    la=g["flash_lat"].values; lo=g["flash_lon"].values
                    m=(la>=cx["latmin"])&(la<=cx["latmax"])&(lo>=cx["lonmin"])&(lo<=cx["lonmax"])
                    las.append(la[m]); los.append(lo[m])
            except Exception: continue
    if las: return np.concatenate(las), np.concatenate(los)
    return np.array([]), np.array([])

# ---------- detecção v2: núcleo -55 + entorno crescido até -10 ----------
def detecta_celulas(tb_c, lat, lon, area_min=AREA_MIN_PIX):
    """Núcleos = componentes conexas de Tb<T_NUCLEO. Entorno de cada núcleo = dilatação geodésica
       dentro de (Tb<T_SAIA), sem invadir outro núcleo -> recupera o ramo quente do r_e."""
    nuc = tb_c < T_NUCLEO
    lab, n = ndimage.label(nuc)
    # descarta núcleos pequenos
    for k in range(1, n+1):
        if (lab==k).sum() < area_min: lab[lab==k]=0
    # renumera
    labs=[k for k in range(1,n+1) if (lab==k).any()]
    remap={k:i+1 for i,k in enumerate(labs)}; lab2=np.zeros_like(lab)
    for k,i in remap.items(): lab2[lab==k]=i
    lab=lab2; n=len(labs)
    if n==0: return lab, [], np.zeros_like(lab)
    # crescimento: dilata os rótulos dentro da saia (Tb<T_SAIA), cada pixel fica com o núcleo mais perto
    saia=(tb_c < T_SAIA)
    footprint=lab.copy()
    for _ in range(DILATA_PIX):
        cresc=ndimage.grey_dilation(footprint, size=3)
        add=(footprint==0)&saia&(cresc>0)
        footprint[add]=cresc[add]
    cels=[]
    for k in range(1, n+1):
        mnuc=lab==k
        if not mnuc.any(): continue
        cy=float(np.nanmean(lat[mnuc])); cx_=float(np.nanmean(lon[mnuc]))
        cels.append(dict(k=k, nuc=mnuc, foot=(footprint==k),
                         clat=cy, clon=cx_, tbmin=float(np.nanmin(tb_c[mnuc])), area=int(mnuc.sum())))
    return lab, cels, footprint

class Rastreador:
    def __init__(self, dmax_graus=1.5):
        self.prev=[]; self.dmax=dmax_graus; self.next_id=1
    def passo(self, cels, when):
        atrib=[]; usados=set()
        for c in cels:
            best=None; bd=1e9
            for p in self.prev:
                if p["nome"] in usados: continue
                d=np.hypot(c["clat"]-p["clat"], c["clon"]-p["clon"])
                if d<bd: bd=d; best=p
            if best is not None and bd<=self.dmax:
                c["nome"]=best["nome"]; usados.add(best["nome"])
                c["dir"]=(c["clat"]-best["clat"], c["clon"]-best["clon"])
            else:
                c["nome"]=f"C{self.next_id}"; self.next_id+=1; c["dir"]=None
            atrib.append(c)
        self.prev=[dict(nome=c["nome"], clat=c["clat"], clon=c["clon"]) for c in atrib]
        return atrib

def separa_frente_traseira(cel, lat, lon):
    m=cel["foot"]
    if cel.get("dir") is None: return {"inteira": m}
    dlat,dlon=cel["dir"]; nrm=np.hypot(dlat,dlon)
    if nrm<1e-4: return {"inteira": m}
    ux,uy=dlon/nrm, dlat/nrm
    proj=(lon-cel["clon"])*ux + (lat-cel["clat"])*uy
    return {"frente": m & (proj>=0), "traseira": m & (proj<0)}

BINS_T=np.arange(-70, 6, 5.0)
def curva_reT(tb_c, refl, re_px, sub_mask):
    tb=tb_c[sub_mask]; rf=refl[sub_mask]; rp=re_px[sub_mask]
    ok=np.isfinite(tb)&np.isfinite(rf); tb,rf,rp=tb[ok],rf[ok],rp[ok]
    out=[]
    for tlo in BINS_T:
        sel=(tb>=tlo)&(tb<tlo+5)
        if sel.sum()<5: continue
        out.append((tlo, float(np.median(rf[sel])), float(np.median(rp[sel])), int(sel.sum())))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--onda",choices=list(ONDAS),default=[k for k in ONDAS if k.startswith("O1")][0])
    ap.add_argument("--passo",type=int,default=1)
    ap.add_argument("--sem-frente-traseira",action="store_true")
    ap.add_argument("--incluir-noite",action="store_true",help="processa também quadros de noite (r_e não vale; mais lento)")
    ap.add_argument("--area-min",type=int,default=AREA_MIN_PIX,help="área mínima do núcleo (px)")
    ap.add_argument("--topn",type=int,default=TOPN,help="mantém só os N maiores núcleos por quadro")
    ap.add_argument("--outdir",default="resultados")
    a=ap.parse_args()
    outd=os.path.join(a.outdir,"rosenfeld_celulas",a.onda); os.makedirs(outd,exist_ok=True)
    d0,d1=ONDAS[a.onda]
    clat=(CAIXA["latmin"]+CAIXA["latmax"])/2; clon=(CAIXA["lonmin"]+CAIXA["lonmax"])/2
    fs=s3fs.S3FileSystem(anon=True); win_cache={}; rastr=Rastreador()
    curvas=[]; tabela=[]
    for dia in pd.date_range(d0,d1,freq="D"):
        for hh in range(HORAS_UT[0],HORAS_UT[-1]+1,a.passo):
            when=dt.datetime(dia.year,dia.month,dia.day,hh,0)
            # GATE dia/noite barato (centro da caixa) ANTES de baixar — grande ganho de tempo
            sza_c=float(_zenital(np.array([clat]),np.array([clon]),when)[0])
            if (not a.incluir_noite) and sza_c>SZA_MAX+8:
                continue                                   # noite: r_e não vale -> pula sem baixar nada
            c13=_le_cmip(fs,"C13",when,win_cache)
            if c13 is None: continue
            lat,lon=c13["lat"],c13["lon"]; tb13=c13["cmi"]-273.15
            sza=_zenital(lat,lon,when); sol=sza<SZA_MAX
            # detecta núcleos ANTES de baixar C07/C14; se não houver grande, pula (economiza download)
            lab,cels,foot=detecta_celulas(tb13,lat,lon,area_min=a.area_min)
            cels=sorted(cels,key=lambda c:c["area"],reverse=True)[:a.topn]   # só os maiores
            if not cels: print(f"  {when:%m-%d %HZ}: sem núcleo grande"); continue
            if sol.any():
                c07=_le_cmip(fs,"C07",when,win_cache); c14=_le_cmip(fs,"C14",when,win_cache)
            else: c07=c14=None
            if c07 is not None and c14 is not None:
                refl=_reflectancia_39(c07["cmi"], c14["cmi"], sza); refl[~sol]=np.nan
                re_px=_refl_para_re(refl)
            else:
                refl=np.full_like(tb13,np.nan); re_px=np.full_like(tb13,np.nan)
            fla,flo=_le_glm(fs,when,CAIXA,FLASH_JANELA_MIN)
            for c in cels:
                if fla.size:
                    d=np.hypot(fla-c["clat"], flo-c["clon"]); c["nflash"]=int((d<0.6).sum())
                else: c["nflash"]=0
                c["elet"]=c["nflash"]>=FLASH_MIN
            cels=rastr.passo(cels, when)
            frac_sol=float(sol.mean())
            for c in cels:
                tabela.append(dict(onda=a.onda,quando=f"{when:%Y-%m-%d %H%M}UT",celula=c["nome"],
                    clat=round(c["clat"],3),clon=round(c["clon"],3),area_nuc=c["area"],
                    tbmin=round(c["tbmin"],1),nflash=c["nflash"],eletrificada=int(c["elet"]),
                    dir=None if c.get("dir") is None else f"{c['dir'][0]:+.2f},{c['dir'][1]:+.2f}",
                    frac_sol=round(frac_sol,2)))
                metades={"inteira":c["foot"]} if a.sem_frente_traseira else separa_frente_traseira(c,lat,lon)
                for lado,mm in metades.items():
                    for (tlo,rfm,rpm,nn) in curva_reT(tb13,refl,re_px,mm):
                        curvas.append(dict(T_bin=tlo,refl39_med=rfm,re_proxy_med=rpm,celula=c["nome"],
                            metade=lado,quando=f"{when:%Y-%m-%d %H%M}UT",n=nn,
                            valido_re=int(np.isfinite(rfm)),onda=a.onda))
            _fig_celulas(outd,when,lon,lat,tb13,cels,fla,flo,frac_sol)
            print(f"  {when:%m-%d %HZ} sol={100*frac_sol:.0f}%: {len(cels)} núcleos "
                  f"({sum(c['elet'] for c in cels)} eletrif.), {fla.size} flashes")
    if not tabela: raise SystemExit("Nada lido — confira acesso ao bucket noaa-goes16 (rede/allowlist).")
    dfc=pd.DataFrame(curvas); dft=pd.DataFrame(tabela)
    dfc.to_csv(f"{outd}/curva_reT_{a.onda}.csv",index=False)
    dft.to_csv(f"{outd}/celulas_tabela_{a.onda}.csv",index=False)
    print(f"\n-> {outd}/curva_reT_{a.onda}.csv ({len(dfc)} linhas)")
    print(f"-> {outd}/celulas_tabela_{a.onda}.csv ({dft.celula.nunique()} células)")
    _fig_reT(outd,a.onda,dfc)

from viz_helpers import novo_mapa, mapa_ref, extensao, PC

def _fig_celulas(outd,when,lon,lat,tb,cels,fla,flo,frac_sol):
    fig,ax=novo_mapa(CAIXA, figsize=(8.5,8.5))
    tr=PC._as_mpl_transform(ax)
    ax.pcolormesh(lon,lat,tb,cmap="Greys",vmin=-80,vmax=20,shading="auto",transform=PC,zorder=1)
    for c in cels:
        col="#D55E00" if c["elet"] else "#0072B2"
        ax.contour(lon,lat,c["foot"].astype(float),levels=[0.5],colors=[col],linewidths=1.0,alpha=0.6,transform=PC,zorder=3)
        ax.contour(lon,lat,c["nuc"].astype(float),levels=[0.5],colors=[col],linewidths=2.0,transform=PC,zorder=3)
        ax.text(c["clon"],c["clat"],c["nome"],color=col,fontsize=11,fontweight="bold",
                ha="center",va="center",bbox=dict(fc="white",ec=col,alpha=0.7,pad=1),transform=PC,zorder=8)
        if c.get("dir") is not None:
            dlat,dlon=c["dir"]; nrm=np.hypot(dlat,dlon)
            if nrm>1e-3:
                ax.annotate("",xy=(c["clon"]+dlon/nrm*0.4,c["clat"]+dlat/nrm*0.4),
                    xytext=(c["clon"],c["clat"]),xycoords=tr,textcoords=tr,
                    arrowprops=dict(arrowstyle="->",color=col,lw=1.5),zorder=8)
    if fla.size: ax.scatter(flo,fla,s=3,c="#E69F00",alpha=0.5,label=f"{fla.size} flashes",transform=PC,zorder=5)
    ax.plot([-58,-49,-49,-58,-58],[-34,-34,-27,-27,-34],"g-",lw=1,alpha=0.6,transform=PC,zorder=7)
    extensao(ax,CAIXA)
    ax.set_title(f"Núcleos {when:%Y-%m-%d %H%MUT} (sol {100*frac_sol:.0f}%) — "
                 f"laranja=eletrif., azul=passivo; linha grossa=núcleo, fina=entorno; seta=movimento")
    if fla.size: ax.legend(loc="upper right",fontsize=8)
    fig.savefig(f"{outd}/fig_celulas_{when:%Y-%m-%d_%H%M}UT.png",dpi=140,bbox_inches="tight"); plt.close(fig)

def _fig_reT(outd,onda,dfc):
    if dfc.empty or (dfc.valido_re==0).all():
        print("  (r_e inválido em todos os quadros — provável noite; sem diagrama r_e(T))"); return
    d=dfc[dfc.valido_re==1]
    celulas=sorted(d.celula.unique(), key=lambda x:int(x[1:]))
    if not celulas: print("  (sem células com r_e válido)"); return
    ncol=min(3,len(celulas)); nrow=int(np.ceil(len(celulas)/ncol))
    fig,axes=plt.subplots(nrow,ncol,figsize=(5*ncol,4*nrow),squeeze=False)
    est={"frente":dict(c="#0072B2",m="o",ls="-",lab="frente (jusante)"),
         "traseira":dict(c="#D55E00",m="s",ls="--",lab="traseira (montante)"),
         "inteira":dict(c="#009E73",m="^",ls="-",lab="célula inteira")}
    for idx,cel in enumerate(celulas):
        ax=axes[idx//ncol][idx%ncol]
        for lado,st in est.items():
            g=d[(d.celula==cel)&(d.metade==lado)]
            if g.empty: continue
            gg=g.groupby("T_bin").re_proxy_med.median().reset_index()
            ax.plot(gg.re_proxy_med,gg.T_bin,color=st["c"],marker=st["m"],ls=st["ls"],ms=5,label=st["lab"])
        ax.set_title(cel,fontsize=10); ax.invert_yaxis(); ax.grid(alpha=0.3)
        ax.set_xlabel("r_e proxy (µm) [3,9µm]"); ax.set_ylabel("Tb topo (°C)"); ax.legend(fontsize=8)
    for j in range(len(celulas),nrow*ncol): axes[j//ncol][j%ncol].axis("off")
    fig.suptitle(f"Rosenfeld r_e(T) por célula — {onda} (frente x traseira) [r_e é PROXY de 3,9µm]",fontsize=12)
    fig.tight_layout(rect=(0,0,1,0.97))
    fig.savefig(f"{outd}/fig_reT_{onda}.png",dpi=150,bbox_inches="tight"); plt.close(fig)
    print(f"-> {outd}/fig_reT_{onda}.png")

if __name__=="__main__":
    main()
