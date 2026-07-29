# -*- coding: utf-8 -*-
"""
viz_helpers.py — apoio compartilhado dos notebooks de visualização do evento RS 2024.
   Navegação GOES-16 ABI, tabela dos 16 canais, downloader com cache, leitores GLM e séries.
   Roda na SUA máquina (precisa de internet p/ o bucket público noaa-goes16).

Pré-req:  pip install s3fs xarray netCDF4 h5netcdf numpy pandas matplotlib ipywidgets scipy
"""
import os, glob, tempfile, datetime as dt, numpy as np, pandas as pd
try:
    from ondas_config import ONDAS, CAIXA, CIDADES
except Exception:
    ONDAS={"O0_precond_27-30abr":("2024-04-27","2024-04-30"),
           "O1_toros_01-04mai":("2024-05-01","2024-05-04"),
           "O2_surto_06-08mai":("2024-05-06","2024-05-08"),
           "O3_cheia_10-13mai":("2024-05-10","2024-05-13")}
    CAIXA=dict(latmin=-36.0,latmax=-25.0,lonmin=-60.0,lonmax=-47.0)
    CIDADES={"Porto Alegre":(-30.03,-51.23),"Florianópolis":(-27.60,-48.55),"Montevidéu":(-34.90,-56.16)}

import cartopy.crs as ccrs
import cartopy.feature as cft
from cartopy.mpl.geoaxes import GeoAxes

PC = ccrs.PlateCarree()

def eh_geoaxes(ax):
    return isinstance(ax, GeoAxes)

def extensao(ax, cx=CAIXA):
    """Fixa a janela do mapa em coordenadas geograficas (substitui set_xlim/set_ylim)."""
    ax.set_extent([cx["lonmin"], cx["lonmax"], cx["latmin"], cx["latmax"]], crs=PC)
    return ax

def novo_mapa(cx=CAIXA, figsize=(8.5, 8.0), fig=None, subplot=(1, 1, 1), proj=None,
              ref=True, rotulos=True):
    """Cria um eixo cartografico (GeoAxes) pronto: extensao + costa/fronteiras/estados + cidades + grade.
       Retorna (fig, ax). SEMPRE plote nele com transform=ccrs.PlateCarree().
       Painel dentro de figura existente: novo_mapa(cx, fig=fig, subplot=(1,3,1))."""
    import matplotlib.pyplot as plt
    if fig is None:
        fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(*subplot, projection=(proj or PC))
    extensao(ax, cx)
    if ref:
        mapa_ref(ax, cx, rotulos=rotulos)
    return fig, ax

def mapa_ref(ax, cx=CAIXA, rotulos=True, cor="#2c7fb8", z=6):
    """Referencia geografica num GeoAxes. Levanta TypeError se o eixo nao for cartografico
       (era esse o bug antigo: add_feature falhava calado num eixo comum)."""
    if not eh_geoaxes(ax):
        raise TypeError(
            "mapa_ref precisa de um GeoAxes. Crie o eixo com vh.novo_mapa(...) "
            "ou plt.axes(projection=ccrs.PlateCarree()), e plote com transform=ccrs.PlateCarree()."
        )
    ax.add_feature(cft.COASTLINE.with_scale("50m"), lw=0.8, edgecolor=cor, zorder=z)
    ax.add_feature(cft.BORDERS.with_scale("50m"), lw=0.7, edgecolor=cor, zorder=z)
    ax.add_feature(cft.STATES.with_scale("50m"), lw=0.4, edgecolor=cor, alpha=0.6, zorder=z)
    for nome, (la, lo) in CIDADES.items():
        if cx["latmin"] <= la <= cx["latmax"] and cx["lonmin"] <= lo <= cx["lonmax"]:
            ax.plot(lo, la, "^", ms=6, color=cor, mec="white", mew=0.6, transform=PC, zorder=z + 1)
            ax.text(lo + 0.12, la + 0.10, nome, fontsize=7, color="#08519c", transform=PC, zorder=z + 1)
    gl = ax.gridlines(crs=PC, draw_labels=rotulos, lw=0.3, alpha=0.4, color="gray", linestyle="--")
    try:
        gl.top_labels = False
        gl.right_labels = False
    except AttributeError:
        gl.xlabels_top = False
        gl.ylabels_right = False
    gl.xlabel_style = {"size": 8}
    gl.ylabel_style = {"size": 8}
    return ax

BUCKET="noaa-goes16"; CMIP=f"{BUCKET}/ABI-L2-CMIPF"; GLM=f"{BUCKET}/GLM-L2-LCFA"
CACHE=os.environ.get("ABI_CACHE","dados/cache_abi")

# ---- os 16 canais do ABI: (nome, µm, tipo, colormap sugerido) ----
# tipo "refl" => CMI é fator de reflectância (0-1, de dia); "emis" => CMI é temperatura de brilho (K)
BANDAS={
 1:("Azul (aerossol)",0.47,"refl","Greys_r"),
 2:("Vermelho (visível)",0.64,"refl","Greys_r"),
 3:("Veggie (NIR)",0.86,"refl","Greys_r"),
 4:("Cirrus",1.37,"refl","Greys_r"),
 5:("Neve/gelo",1.6,"refl","Greys_r"),
 6:("Tam. partícula nuvem",2.2,"refl","Greys_r"),
 7:("Janela curta 3,9µm",3.9,"emis","inferno"),
 8:("Vapor alto 6,2µm",6.2,"emis","BrBG"),
 9:("Vapor médio 6,9µm",6.9,"emis","BrBG"),
 10:("Vapor baixo 7,3µm",7.3,"emis","BrBG"),
 11:("Fase topo 8,4µm",8.4,"emis","inferno"),
 12:("Ozônio 9,6µm",9.6,"emis","inferno"),
 13:("Janela limpa 10,3µm",10.3,"emis","Greys"),
 14:("Janela 11,2µm",11.2,"emis","Greys"),
 15:("Janela suja 12,3µm",12.3,"emis","Greys"),
 16:("CO2 13,3µm",13.3,"emis","Greys"),
}
def lista_bandas():
    return pd.DataFrame([(k,v[0],v[1],v[2]) for k,v in BANDAS.items()],
                        columns=["banda","nome","µm","tipo"]).set_index("banda")

# ---------- navegação ABI (grade fixa -> lat/lon) ----------
def _proj(ds):
    g=ds["goes_imager_projection"]
    return (float(g.attrs["perspective_point_height"])+float(g.attrs["semi_major_axis"]),
            float(g.attrs["semi_major_axis"]), float(g.attrs["semi_minor_axis"]),
            np.radians(float(g.attrs["longitude_of_projection_origin"])))
def _xy2ll(x,y,prm):
    H,r_eq,r_pol,lam0=prm; cx,cy=np.cos(x),np.cos(y); sx,sy=np.sin(x),np.sin(y)
    a=sx**2+cx**2*(cy**2+(r_eq**2/r_pol**2)*sy**2); b=-2*H*cx*cy; c=H**2-r_eq**2; disc=b**2-4*a*c
    with np.errstate(invalid="ignore"):
        rs=(-b-np.sqrt(disc))/(2*a); Sx=rs*cx*cy; Sy=-rs*sx; Sz=rs*cx*sy
        lat=np.degrees(np.arctan((r_eq**2/r_pol**2)*Sz/np.sqrt((H-Sx)**2+Sy**2)))
        lon=np.degrees(lam0-np.arctan(Sy/(H-Sx)))
    bad=disc<0; return np.where(bad,np.nan,lat),np.where(bad,np.nan,lon)
def _janela(x1d,y1d,prm,cx):
    s=8; Xc,Yc=np.meshgrid(x1d[::s],y1d[::s]); la,lo=_xy2ll(Xc,Yc,prm)
    m=(la>=cx["latmin"]-1)&(la<=cx["latmax"]+1)&(lo>=cx["lonmin"]-1)&(lo<=cx["lonmax"]+1)
    if not m.any(): return None
    jj,ii=np.where(m)
    return (max(0,(jj.min()-1)*s),min(len(y1d),(jj.max()+2)*s),
            max(0,(ii.min()-1)*s),min(len(x1d),(ii.max()+2)*s))

def zenital(lat,lon,when):
    d=when.timetuple().tm_yday; frac=when.hour+when.minute/60.0
    decl=np.radians(-23.44)*np.cos(np.radians(360.0/365.0*(d+10)))
    LST=frac+lon/15.0; H=np.radians(15.0*(LST-12.0)); la=np.radians(lat)
    cz=np.sin(la)*np.sin(decl)+np.cos(la)*np.cos(decl)*np.cos(H)
    return np.degrees(np.arccos(np.clip(cz,-1,1)))

# ---------- downloader com cache ----------
def _fs():
    import s3fs; return s3fs.S3FileSystem(anon=True)

def horarios(onda, passo_h=1, h0=0, h1=24):
    d0,d1=ONDAS[onda]; out=[]
    for dia in pd.date_range(d0,d1,freq="D"):
        for hh in range(h0,h1,passo_h):
            out.append(dt.datetime(dia.year,dia.month,dia.day,hh,0))
    return out

def baixa_abi(banda, whens, fs=None, cache=CACHE, verbose=True):
    """Baixa (com cache) o CMIPF da banda nos horários pedidos. Retorna [(when, path_local)]."""
    os.makedirs(cache,exist_ok=True); fs=fs or _fs(); saida=[]
    for w in whens:
        doy=w.timetuple().tm_yday
        loc=os.path.join(cache,f"C{banda:02d}_{w:%Y%m%d_%H%M}.nc")
        if not os.path.exists(loc):
            pref=f"{CMIP}/{w.year}/{doy:03d}/{w.hour:02d}/"
            try: arqs=fs.ls(pref)
            except Exception: arqs=[]
            cand=sorted([a for a in arqs if f"-M6C{banda:02d}_" in a or f"-M3C{banda:02d}_" in a])
            if not cand:
                if verbose: print(f"  (sem arquivo) C{banda:02d} {w:%m-%d %HZ}"); continue
            try: fs.get(cand[0],loc)
            except Exception as e:
                if verbose: print(f"  ! download C{banda:02d} {w:%m-%d %HZ}: {str(e)[:50]}"); continue
        saida.append((w,loc))
        if verbose: print(f"  ok C{banda:02d} {w:%m-%d %HZ}")
    return saida

def le_abi(path, banda, caixa=CAIXA):
    """Lê o CMIPF recortado na caixa. Retorna dict(cmi,lat,lon,tipo,when)."""
    import xarray as xr
    ds=xr.open_dataset(path,engine="h5netcdf"); prm=_proj(ds)
    x1d=ds["x"].values; y1d=ds["y"].values; win=_janela(x1d,y1d,prm,caixa)
    if win is None: ds.close(); return None
    j0,j1,i0,i1=win; cmi=ds["CMI"].values[j0:j1,i0:i1].astype("float32")
    X,Y=np.meshgrid(x1d[i0:i1],y1d[j0:j1]); lat,lon=_xy2ll(X,Y,prm)
    when=pd.to_datetime(ds["t"].values).to_pydatetime() if "t" in ds else None
    ds.close()
    return dict(cmi=cmi,lat=lat,lon=lon,tipo=BANDAS[banda][2],when=when)

def carrega_glm(when, caixa=CAIXA, jan_min=5, fs=None):
    """Flashes GLM em +/- jan_min minutos ao redor de 'when', na caixa."""
    import xarray as xr
    fs=fs or _fs(); las=[]; los=[]
    for off in range(-jan_min,jan_min+1):
        t=when+dt.timedelta(minutes=off); doy=t.timetuple().tm_yday
        pref=f"{GLM}/{t.year}/{doy:03d}/{t.hour:02d}/"
        try: arqs=fs.ls(pref)
        except Exception: continue
        alvo=[a for a in arqs if f"_s{t.year}{doy:03d}{t.hour:02d}{t.minute:02d}" in a]
        for a in alvo:
            try:
                with fs.open(a) as f:
                    g=xr.open_dataset(f,engine="h5netcdf")
                    la=g["flash_lat"].values; lo=g["flash_lon"].values
                    m=(la>=caixa["latmin"])&(la<=caixa["latmax"])&(lo>=caixa["lonmin"])&(lo<=caixa["lonmax"])
                    las.append(la[m]); los.append(lo[m])
            except Exception: continue
    if las: return np.concatenate(las),np.concatenate(los)
    return np.array([]),np.array([])

# ---------- realces/escala por tipo de banda ----------
def escala(campo):
    """Retorna (dado_para_plot, vmin, vmax, cmap, rotulo) conforme o tipo da banda."""
    tipo=campo["tipo"]
    if tipo=="refl":
        return campo["cmi"], 0.0, 1.0, "Greys_r", "reflectância"
    tb=campo["cmi"]-273.15
    return tb, -80.0, 20.0, "Greys", "Tb (°C)"

# ---------- séries integradas ----------
def abre_nc(path, forcar=False):
    """Abre um .nc (ou zip do CDS com varios .nc dentro).
       O zip e extraido UMA vez em <path>_x/ e depois reaproveitado: no Windows, re-extrair
       por cima de um arquivo ja aberto por outro handle (dataset de uma execucao anterior
       da celula) levanta PermissionError. forcar=True re-extrai de qualquer jeito."""
    import xarray as xr, zipfile
    if zipfile.is_zipfile(path):
        d = path + "_x"
        os.makedirs(d, exist_ok=True)
        with zipfile.ZipFile(path) as z:
            ncs = [n for n in z.namelist() if n.endswith('.nc')]
            for n in ncs:
                alvo = os.path.join(d, n)
                ja = os.path.exists(alvo) and os.path.getsize(alvo) == z.getinfo(n).file_size
                if ja and not forcar:
                    continue
                try:
                    z.extract(n, d)
                except PermissionError:
                    if not os.path.exists(alvo):
                        raise PermissionError(
                            f"nao consegui extrair {n} em {d}. Se o arquivo ja existe e esta aberto "
                            "por outro processo/kernel, feche-o (ds.close()) ou reinicie o kernel."
                        )
                    print(f"  (aviso) {n} em uso; reaproveitando o ja extraido em {d}")
        caminhos = [os.path.join(d, n) for n in ncs]
        if len(caminhos) == 1:
            return xr.open_dataset(caminhos[0])
        try:
            return xr.open_mfdataset(caminhos)
        except ImportError:
            return xr.merge([xr.open_dataset(c) for c in caminhos], compat="override")
    return xr.open_dataset(path)

def coords_nc(ds):
    """Retorna (latn, lonn, tdim, levn) detectando os nomes das coordenadas."""
    latn='latitude' if 'latitude' in ds else ('lat' if 'lat' in ds else None)
    lonn='longitude' if 'longitude' in ds else ('lon' if 'lon' in ds else None)
    tdn='valid_time' if 'valid_time' in ds.dims else ('time' if 'time' in ds.dims else None)
    lvn=next((c for c in ('pressure_level','level','lev','isobaricInhPa','plev') if c in ds.dims), None)
    return latn,lonn,tdn,lvn

def carrega_series(resdir="resultados"):
    """Junta a tabela diária integrada (Jz/AOD), ERA5 RS (IVT/VPI) e GLM diário, se existirem."""
    out=None
    ti=os.path.join(resdir,"tabela_diaria_integrada_2024.csv")
    if os.path.exists(ti):
        out=pd.read_csv(ti); out["datetime"]=pd.to_datetime(out["datetime"])
    ers=os.path.join(resdir,"era5_diario_rs_rs.csv")
    if out is not None and os.path.exists(ers):
        e=pd.read_csv(ers)
        dcol="data" if "data" in e.columns else ("datetime" if "datetime" in e.columns else e.columns[0])
        e[dcol]=pd.to_datetime(e[dcol])
        # pega só as colunas que existirem (o nome da VPI varia entre versões)
        cand=[c for c in ["IVT_kg_m_s","VPI_baixo_PVU","VPI_925_PVU","VPI_baixo","SLW_kg_m2","TCLW_kg_m2"] if c in e.columns]
        out=out.merge(e[[dcol]+cand],left_on="datetime",right_on=dcol,how="left")
        if dcol!="datetime" and dcol in out.columns: out=out.drop(columns=[dcol])
    gl=sorted(glob.glob(os.path.join(resdir,"glm_flashes_rs_*.csv")))
    if out is not None and gl:
        g=pd.read_csv(gl[-1]); g["data"]=pd.to_datetime(g["data"])
        out=out.merge(g.rename(columns={"data":"datetime","n_flashes_estimado":"flashes"})[["datetime","flashes"]],
                      on="datetime",how="left")
    return out
