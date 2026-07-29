#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10 — Exporta as trajetórias (traj_*.csv) para .KMZ (Google Earth): fronteiras, relevo e costa
   vêm de graça no Google Earth. As linhas saem em 3D (altitude = pressão convertida), e a
   fumaça de abril entra como sobreposição no chão (GroundOverlay). Sem dependências extras.

Uso:  python 10_trajetorias_kmz.py                 # lê resultados/traj_*.csv
Saída: resultados/trajetorias.kmz
"""
import os, glob, zipfile, numpy as np, pandas as pd

OUT=os.environ.get("OUTDIR","resultados")
def alt_m(p_hpa):  # pressão -> altitude aproximada (m), atmosfera padrão
    return 44330.0*(1.0-(np.asarray(p_hpa)/1013.25)**0.1903)

def overlay_aod(outdir):
    """Renderiza a fumaça média de abril como PNG com transparência; retorna (png, N,S,W,E) ou None."""
    cam=f"{outdir}/_cams_brasil_rs.nc"
    if not os.path.exists(cam): return None
    try:
        import xarray as xr, matplotlib.cm as cm, matplotlib.colors as mcolors
        ds=xr.open_dataset(cam); td='valid_time' if 'valid_time' in ds.dims else 'time'
        fum=(ds["omaod550"]+ds["bcaod550"]).sel({td:slice("2024-04-15","2024-05-05")}).mean(td)
        latn='latitude' if 'latitude' in ds else 'lat'; lonn='longitude' if 'longitude' in ds else 'lon'
        lat=ds[latn].values; lon=ds[lonn].values; A=fum.values
        if lat[0]<lat[-1]: A=A[::-1,:]; lat=lat[::-1]     # norte no topo
        norm=mcolors.Normalize(0,0.5); rgba=cm.inferno(norm(A))
        rgba[...,3]=np.clip((A-0.03)/0.12,0,1)             # alfa: transparente onde limpo
        png=f"{outdir}/aod_abril.png"
        import matplotlib.pyplot as plt; plt.imsave(png,rgba)
        return png, float(max(lat)), float(min(lat)), float(min(lon)), float(max(lon))
    except Exception as e:
        print("overlay AOD pulado:",str(e)[:80]); return None

def kml_line(nome, coords, cor):
    c="".join(f"{x:.3f},{y:.3f},{a:.0f} " for (x,y,a) in coords)
    return (f'<Placemark><name>{nome}</name><styleUrl>#{cor}</styleUrl>'
            f'<LineString><extrude>1</extrude><tessellate>1</tessellate>'
            f'<altitudeMode>absolute</altitudeMode><coordinates>{c}</coordinates></LineString></Placemark>')

def main():
    os.makedirs(OUT,exist_ok=True)
    csvs=sorted(glob.glob(f"{OUT}/traj_*.csv"))+sorted(glob.glob(f"{OUT}/trajetorias_rs.csv"))
    if not csvs: raise SystemExit("Nenhum traj_*.csv em "+OUT)
    estilos={"1o":"ff00e5ff","2o":"ffff50ff","default":"ffffffff"}  # aabbggrr
    styles="".join(f'<Style id="{k}"><LineStyle><color>{v}</color><width>2</width></LineStyle>'
                   f'<PolyStyle><color>30{v[2:]}</color></PolyStyle></Style>' for k,v in estilos.items())
    folders=[]
    for csv in csvs:
        df=pd.read_csv(csv,parse_dates=["t"])
        pcol="p_hPa" if "p_hPa" in df else None
        pk=[]
        for tid,g in df.groupby("traj"):
            g=g.sort_values("t")
            alt=alt_m(g[pcol]) if pcol else np.full(len(g),1500.0)
            coords=list(zip(g["lon"],g["lat"],alt))
            cor="1o" if "1o" in str(tid) else ("2o" if "2o" in str(tid) else "default")
            pk.append(kml_line(tid,coords,cor))
        folders.append(f'<Folder><name>{os.path.basename(csv)}</name>{"".join(pk)}</Folder>')
    # sobreposição de fumaça
    ov=overlay_aod(OUT); ground=""; extra_files=[]
    if ov:
        png,N,S,W,E=ov; extra_files.append(png)
        ground=(f'<GroundOverlay><name>Fumaça abril (CAMS)</name><color>b0ffffff</color>'
                f'<Icon><href>{os.path.basename(png)}</href></Icon>'
                f'<LatLonBox><north>{N}</north><south>{S}</south><west>{W}</west><east>{E}</east></LatLonBox></GroundOverlay>')
    marks=('<Placemark><name>Roraima</name><Point><coordinates>-61,2.5,0</coordinates></Point></Placemark>'
           '<Placemark><name>RS (caixa)</name><Polygon><outerBoundaryIs><LinearRing><coordinates>'
           '-58,-34,0 -49,-34,0 -49,-27,0 -58,-27,0 -58,-34,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>')
    kml=('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
         '<name>Trajetórias RS maio/2024</name>'+styles+ground+marks+"".join(folders)+'</Document></kml>')
    doc=f"{OUT}/doc.kml"; open(doc,"w",encoding="utf-8").write(kml)
    kmz=f"{OUT}/trajetorias.kmz"
    with zipfile.ZipFile(kmz,"w",zipfile.ZIP_DEFLATED) as z:
        z.write(doc,"doc.kml")
        for f in extra_files: z.write(f,os.path.basename(f))
    os.remove(doc)
    print(f"-> {kmz}  ({sum(1 for _ in csvs)} arquivos de trajetória)")

if __name__=="__main__":
    main()
