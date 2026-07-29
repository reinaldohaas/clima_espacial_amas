#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
12 — Assinatura de TOPO DE NUVEM dia/noite-consistente (GOES-16 ABI) — P1 (SEM FD) x P2 (COM FD).

   POR QUE ESTE SCRIPT EXISTE
   O diagrama de Rosenfeld r_e(T) (script 02) usa o canal de 3,9 µm REFLETIDO — só funciona de
   DIA. O Pulso 1 (toros, 01-02/mai) foi amostrado de dia; o Pulso 2 (cheia, 12-13/mai) foi de
   NOITE. Por isso as curvas r_e(T) dos dois NÃO são comparáveis (o P2 aparece com r_e de 3-7 µm,
   que é artefato do retrieval noturno, não microfísica). Este script troca o r_e por métricas
   que valem 24 h — todas de canais EMISSIVOS (não precisam de sol):

     • Tb topo (C13, 10,3 µm janela limpa) : temperatura de topo. Convecção profunda com graupel
       gera topos MUITO frios (< -60 °C) e "overshooting"; estratiforme gera topos mais quentes e lisos.
     • BTD vapor-janela (C08 6,2 - C13 10,3) : ~0 ou POSITIVO sobre topos penetrantes (overshooting).
       Testemunha 24 h de convecção profunda glaciada — complementa os raios (GLM, script 11).
     • Split-window (C14 11,2 - C15 12,3) : tamanho/fase da partícula no topo.
     • C07-C13 (3,9 - 10,3, à noite EMISSIVO) : proxy de glaciação/tamanho no topo à noite (interpretar com cuidado).

   PREVISÃO A TESTAR (H1 x H2):
     P1 = topos muito frios + fração alta de overshooting (nuvem elétrica/graupel).
     P2 = topos mais quentes/lisos + pouco/nenhum overshooting (estratiforme, sem graupel), APESAR da chuva extrema.
   Isso é falsificável DE DIA E DE NOITE — resolve o confundimento que travou o Rosenfeld.

   Dado público (sem login) na AWS: bucket noaa-goes16, produto ABI-L2-CMIPF (uma banda por arquivo).
   Baixa 1 arquivo por (banda, hora amostrada), processa e APAGA (evita encher o disco).

Pré-req:  pip install s3fs xarray netCDF4 h5netcdf numpy pandas matplotlib
Uso:
   python 12_topo_nuvem_dia_noite.py --passo 2                 # amostra de 2 em 2 h (padrão)
   python 12_topo_nuvem_dia_noite.py --passo 1 --bandas C13,C08,C14,C15,C07
Saída:
   resultados/topo_nuvem_dia_noite.csv     (uma linha por instante, com todas as métricas + flag dia/noite)
   resultados/fig_topo_nuvem_pulsos.png    (small multiples: um painel por métrica, P1 x P2)
"""
import argparse, os, tempfile, datetime as dt, numpy as np, pandas as pd
try:
    import s3fs, xarray as xr
except ImportError:
    raise SystemExit("pip install s3fs xarray netCDF4 h5netcdf")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

BUCKET="noaa-goes16"; PROD="ABI-L2-CMIPF"
try:
    from ondas_config import ONDAS, CAIXA
except Exception:
    ONDAS={"O1_toros_01-04mai":("2024-05-01","2024-05-04"),"O2_surto_06-08mai":("2024-05-06","2024-05-08"),
           "O3_cheia_10-13mai":("2024-05-10","2024-05-13")}
    CAIXA=dict(latmin=-34.0, latmax=-26.0, lonmin=-58.0, lonmax=-48.0)
BANDAS_PADRAO=["C13","C08","C14","C15"]     # C07 opcional (mais pesado de interpretar à noite)
# limiares (°C) e do overshooting
T_FRIO=-55.0                                 # "pixel de topo frio" para estatística de overshoot/split
BTD_OVS=-2.0                                 # C08-C13 >= -2 K sobre pixel frio => candidato a overshooting

# ---------- navegação ABI (grade fixa -> lat/lon) ----------
def _proj_params(ds):
    g=ds["goes_imager_projection"]
    return (float(g.attrs["perspective_point_height"])+float(g.attrs["semi_major_axis"]),
            float(g.attrs["semi_major_axis"]), float(g.attrs["semi_minor_axis"]),
            np.radians(float(g.attrs["longitude_of_projection_origin"])))

def _xy_para_latlon(x, y, prm):
    """x,y = ângulos de varredura (rad), malhas 2D. Retorna lat,lon (graus)."""
    H, r_eq, r_pol, lam0 = prm
    cx, cy = np.cos(x), np.cos(y); sx, sy = np.sin(x), np.sin(y)
    a = sx**2 + cx**2*(cy**2 + (r_eq**2/r_pol**2)*sy**2)
    b = -2.0*H*cx*cy
    c = H**2 - r_eq**2
    disc = b**2 - 4*a*c
    with np.errstate(invalid="ignore"):
        rs = (-b - np.sqrt(disc))/(2*a)
        Sx = rs*cx*cy; Sy = -rs*sx; Sz = rs*cx*sy
        lat = np.degrees(np.arctan((r_eq**2/r_pol**2)*Sz/np.sqrt((H-Sx)**2 + Sy**2)))
        lon = np.degrees(lam0 - np.arctan(Sy/(H-Sx)))
    bad = disc < 0
    lat=np.where(bad,np.nan,lat); lon=np.where(bad,np.nan,lon)
    return lat, lon

def _janela_caixa(x1d, y1d, prm, cx):
    """Acha os índices (fatia) que cobrem a CAIXA: grade grosseira -> refina."""
    s=8
    xc, yc = x1d[::s], y1d[::s]
    Xc, Yc = np.meshgrid(xc, yc)
    latc, lonc = _xy_para_latlon(Xc, Yc, prm)
    m=(latc>=cx["latmin"]-1)&(latc<=cx["latmax"]+1)&(lonc>=cx["lonmin"]-1)&(lonc<=cx["lonmax"]+1)
    if not m.any(): return None
    jj, ii = np.where(m)                      # linha (y), coluna (x)
    i0=max(0,(ii.min()-1)*s); i1=min(len(x1d),(ii.max()+2)*s)
    j0=max(0,(jj.min()-1)*s); j1=min(len(y1d),(jj.max()+2)*s)
    return j0,j1,i0,i1

# ---------- ângulo zenital solar (flag dia/noite) ----------
def _zenital(lat, lon, when):
    d=when.timetuple().tm_yday
    frac=when.hour+when.minute/60.0
    decl=np.radians(-23.44)*np.cos(np.radians(360.0/365.0*(d+10)))
    LST=frac + lon/15.0                        # hora solar local (lon oeste negativo)
    H=np.radians(15.0*(LST-12.0))             # ângulo horário
    la=np.radians(lat)
    cosz=np.sin(la)*np.sin(decl)+np.cos(la)*np.cos(decl)*np.cos(H)
    return np.degrees(np.arccos(np.clip(cosz,-1,1)))

# ---------- leitura de uma banda num instante ----------
def _primeiro_arquivo(fs, banda, when):
    bb=int(banda[1:]); doy=when.timetuple().tm_yday
    pref=f"{BUCKET}/{PROD}/{when.year}/{doy:03d}/{when.hour:02d}/"
    try: arqs=fs.ls(pref)
    except Exception: return None
    cand=[a for a in arqs if f"-M6C{bb:02d}_" in a or f"-M3C{bb:02d}_" in a]
    return sorted(cand)[0] if cand else None

def _le_banda(fs, banda, when, cx, win_cache):
    a=_primeiro_arquivo(fs, banda, when)
    if a is None: return None
    tmp=tempfile.NamedTemporaryFile(suffix=".nc", delete=False).name
    try:
        fs.get(a, tmp)
        ds=xr.open_dataset(tmp, engine="h5netcdf")
        prm=_proj_params(ds)
        x1d=ds["x"].values; y1d=ds["y"].values
        key=(len(x1d),len(y1d))
        if key not in win_cache:
            win_cache[key]=_janela_caixa(x1d,y1d,prm,cx)
        win=win_cache[key]
        if win is None: ds.close(); return None
        j0,j1,i0,i1=win
        cmi=ds["CMI"].values[j0:j1,i0:i1].astype("float32")
        X,Y=np.meshgrid(x1d[i0:i1], y1d[j0:j1])
        lat,lon=_xy_para_latlon(X,Y,prm)
        ds.close()
        mask=(lat>=cx["latmin"])&(lat<=cx["latmax"])&(lon>=cx["lonmin"])&(lon<=cx["lonmax"])
        return dict(cmi=cmi, lat=lat, lon=lon, mask=mask)
    except Exception as e:
        print(f"    ! {banda} {when:%Y-%m-%d %HZ}: {str(e)[:60]}"); return None
    finally:
        try: os.remove(tmp)
        except OSError: pass

# ---------- métricas de um instante ----------
def _metricas(campos, lat, lon, mask, when):
    c13=campos.get("C13")
    if c13 is None: return None
    tb=c13["cmi"][mask]-273.15                # °C
    tb=tb[np.isfinite(tb)]
    if tb.size<50: return None
    r=dict(quando=when, n_pixels=int(tb.size),
            Tb_min=float(np.nanmin(tb)), Tb_p01=float(np.nanpercentile(tb,1)),
            frac_lt40=float((tb<-40).mean()), frac_lt50=float((tb<-50).mean()),
            frac_lt60=float((tb<-60).mean()))
    frio = (c13["cmi"]-273.15 < T_FRIO) & mask
    nfrio=int(frio.sum()); r["n_frio"]=nfrio
    # overshooting: C08-C13 >= BTD_OVS sobre pixels frios
    if "C08" in campos and nfrio>20:
        btd=campos["C08"]["cmi"]-c13["cmi"]
        r["BTD_WVIR_med_frio"]=float(np.nanmedian(btd[frio]))
        r["frac_overshoot"]=float(np.nanmean(btd[frio]>=BTD_OVS))
    else:
        r["BTD_WVIR_med_frio"]=np.nan; r["frac_overshoot"]=np.nan
    # split-window sobre pixels frios
    if "C14" in campos and "C15" in campos and nfrio>20:
        sw=campos["C14"]["cmi"]-campos["C15"]["cmi"]
        r["BTD_split_med_frio"]=float(np.nanmedian(sw[frio]))
    else:
        r["BTD_split_med_frio"]=np.nan
    if "C07" in campos and nfrio>20:
        b7=campos["C07"]["cmi"]-c13["cmi"]
        r["BTD_37_10_med_frio"]=float(np.nanmedian(b7[frio]))
    else:
        r["BTD_37_10_med_frio"]=np.nan
    sza=float(np.nanmean(_zenital(lat[mask], lon[mask], when)))
    r["sza"]=sza; r["is_dia"]=int(sza<80.0)
    return r

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ondas",default="",help="ondas separadas por vírgula (padrão: todas do ondas_config)")
    ap.add_argument("--passo",type=int,default=2,help="amostra de N em N horas (padrão 2)")
    ap.add_argument("--bandas",default=",".join(BANDAS_PADRAO))
    ap.add_argument("--outdir",default="resultados")
    a=ap.parse_args(); os.makedirs(a.outdir,exist_ok=True)
    bandas=[b.strip() for b in a.bandas.split(",") if b.strip()]
    if "C13" not in bandas: bandas=["C13"]+bandas
    sel=[o.strip() for o in a.ondas.split(",") if o.strip()] or list(ONDAS)
    janelas={k:ONDAS[k] for k in sel if k in ONDAS}
    fs=s3fs.S3FileSystem(anon=True); win_cache={}
    linhas=[]
    for nome,(d0,d1) in janelas.items():
        print(f"\n== {nome} ({d0}..{d1}) — bandas {bandas} passo {a.passo}h ==")
        for dia in pd.date_range(d0,d1,freq="D"):
            for hh in range(0,24,a.passo):
                when=dt.datetime(dia.year,dia.month,dia.day,hh,0)
                campos={}
                for b in bandas:
                    r=_le_banda(fs,b,when,CAIXA,win_cache)
                    if r is not None: campos[b]=r
                if "C13" not in campos: continue
                base=campos["C13"]
                m=_metricas(campos, base["lat"], base["lon"], base["mask"], when)
                if m is None: continue
                m["onda"]=nome
                linhas.append(m)
                print(f"  {when:%m-%d %HZ} {'DIA' if m['is_dia'] else 'NOITE'}: "
                      f"Tb_min={m['Tb_min']:.0f} %<-60={100*m['frac_lt60']:.0f}% "
                      f"overshoot={100*m['frac_overshoot']:.0f}%" if np.isfinite(m['frac_overshoot'])
                      else f"  {when:%m-%d %HZ}: Tb_min={m['Tb_min']:.0f}")
    if not linhas:
        raise SystemExit("Nada lido — confira acesso ao bucket noaa-goes16 (rede/allowlist).")
    df=pd.DataFrame(linhas)
    out=f"{a.outdir}/topo_nuvem_dia_noite.csv"; df.to_csv(out,index=False)
    print(f"\n-> {out} ({len(df)} instantes)")

    # ---- comparação entre ondas (métricas 24h, independentes de dia/noite) ----
    print("\n=== COMPARAÇÃO ENTRE ONDAS (métricas 24 h, não confundidas por dia/noite) ===")
    met=[("Tb_min","min Tb (°C, menor=mais frio)"),("frac_lt60","fração Tb<-60°C"),
         ("frac_overshoot","fração overshooting (C08-C13)"),("BTD_split_med_frio","split-window médio (K)")]
    for col,rot in met:
        g=df.groupby("onda")[col].mean()
        print(f"  {rot:42s}: " + " | ".join(f"{k.split('_')[0]}={v:.3f}" for k,v in g.items()))

    # ---- small multiples: um painel por métrica, uma linha por onda (acessível) ----
    paineis=[("Tb_min","min Tb topo (°C)  — menor = mais frio/vigoroso"),
             ("frac_lt60","fração de topo Tb < -60 °C"),
             ("frac_overshoot","fração de overshooting (BTD vapor-janela)"),
             ("BTD_split_med_frio","split-window C14-C15 nos topos frios (K)")]
    cores=["#0072B2","#D55E00","#CC79A7","#009E73","#E69F00","#999999"]
    marc=["o","s","^","D","v","P"]; lss=["-","--","-.",":","-","--"]
    ordem=[k for k in janelas]
    estilo={o:dict(color=cores[i%len(cores)],marker=marc[i%len(marc)],ls=lss[i%len(lss)],lab=o)
            for i,o in enumerate(ordem)}
    fig,axes=plt.subplots(len(paineis),1,figsize=(9,3.0*len(paineis)),sharex=False)
    for ax,(col,tit) in zip(axes,paineis):
        for o,st in estilo.items():
            d=df[df.onda==o].copy()
            if col not in d or d[col].isna().all() or d.empty: continue
            hrs=(pd.to_datetime(d.quando)-pd.to_datetime(d.quando).iloc[0]).dt.total_seconds()/3600.0
            ax.plot(hrs,d[col],color=st["color"],marker=st["marker"],ls=st["ls"],ms=5,lw=1.6,label=st["lab"])
        ax.set_title(tit,fontsize=10,loc="left"); ax.grid(alpha=0.3)
        ax.set_xlabel("horas desde o início da janela da onda")
    axes[0].legend(loc="best",fontsize=8)
    fig.suptitle("Topo de nuvem por ONDA (GOES-16, métricas 24 h) — cada janela alinhada em t=0",fontsize=11)
    fig.tight_layout(rect=(0,0,1,0.98))
    figout=f"{a.outdir}/fig_topo_nuvem_ondas.png"; fig.savefig(figout,dpi=150,bbox_inches="tight")
    print(f"-> {figout}")
    ndia=df.groupby("onda").is_dia.sum(); print("\nInstantes de DIA por onda (onde r_e ainda valeria):"); print(ndia.to_string())

if __name__=="__main__":
    main()
