#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05_serie_alvo.py
================
SÉRIE TEMPORAL sobre o alvo: acha QUANDO a tempestade esteve de fato em cima.

Varre as cenas GOES-16 de --ini a --fim (passo em horas) e, numa caixa de
--raio km em torno do alvo, registra:
  - T_min do topo (C13, funciona dia E noite — é o "sinal ótimo" p/ achar
    convecção; a reflectância visível zera à noite)
  - fração de pixels com topo < -20 C e < -35 C
  - (opcional --com-visivel) reflectância média/máx da C02 (só útil de dia)

Saída: serie_<nome>.csv + serie_<nome>.png com as horas mais frias marcadas,
e UM MAPA IR POR CENA (ir_<data>_<hora>UT.png), georreferenciado em lat/lon
com as divisas municipais do IBGE (via geobr; use --sem-mapas p/ desligar).
Use as horas frias no 04 (--goes-horas) para o Rosenfeld/BTD do momento certo.

Dependências extras p/ os mapas municipais: pip install geopandas geobr

ATENÇÃO ao volume: C13 Full Disk ~60-120 MB/cena. 5 dias de hora em hora
~ 120 cenas. O cache dados_goes/ evita rebaixar. Comece com --passo 3 se
quiser triagem rápida, depois refine com --passo 1 só no dia que importa.

Uso (caso default: 28/fev-04/mar, alvo -29.5 -51.2):
  python 05_serie_alvo.py
  python 05_serie_alvo.py --passo 3                  # triagem rápida
  python 05_serie_alvo.py --com-visivel              # inclui C02 (pesado)
"""

import argparse
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parents[1]

def _carregar(nome_arquivo, alias):
    spec = importlib.util.spec_from_file_location(alias, AQUI / nome_arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def medir_cena(m2, quando, lat, lon, raio, com_visivel):
    """Métricas da caixa em torno do alvo numa cena. Retorna (métricas, ds)."""
    from goes2go import GOES
    out = dict(tempo=quando, tmin=np.nan, frac20=np.nan, frac35=np.nan,
               vis_med=np.nan, vis_max=np.nan)
    g13 = GOES(satellite=16, product="ABI-L2-CMIPF", channel=[13])
    ds = g13.nearesttime(quando.strftime("%Y-%m-%d %H:%M"),
                         save_dir=str(m2.CACHE_GOES), overwrite=False)
    rec = m2.recortar(ds, lat, lon, raio)
    T = rec["CMI"].values - 273.15
    out["tmin"] = float(np.nanmin(T))
    n = np.isfinite(T).sum()
    out["frac20"] = float((T < -20).sum()) / n
    out["frac35"] = float((T < -35).sum()) / n
    if com_visivel:
        g02 = GOES(satellite=16, product="ABI-L2-CMIPF", channel=[2])
        ds2 = g02.nearesttime(quando.strftime("%Y-%m-%d %H:%M"),
                              save_dir=str(m2.CACHE_GOES), overwrite=False)
        rec2 = m2.recortar(ds2, lat, lon, raio)
        v = rec2["CMI"].values
        out["vis_med"] = float(np.nanmean(v))
        out["vis_max"] = float(np.nanmax(v))
    return out, ds

# ----------------------------------------------------------------------
# MAPA IR GEORREFERENCIADO COM MUNICÍPIOS (IBGE via geobr, cache local)
# ----------------------------------------------------------------------
CACHE_GEO = AQUI / "dados/geo"

def carregar_municipios(uf="RS"):
    """Divisas municipais do IBGE. Baixa 1x (geobr) e guarda em cache.
    Se geobr/geopandas não estiverem instalados, retorna None (mapa sai
    sem divisas). pip install geopandas geobr"""
    try:
        import geopandas as gpd
        CACHE_GEO.mkdir(exist_ok=True)
        f = CACHE_GEO / f"municipios_{uf}.gpkg"
        if f.exists():
            return gpd.read_file(f)
        import geobr
        mun = geobr.read_municipality(code_muni=uf, year=2020, simplified=True)
        mun.to_file(f, driver="GPKG")
        return mun
    except Exception as e:
        print(f"  (sem municípios no mapa: {e} — pip install geopandas geobr)")
        return None

def mapa_ir(m2, ds, quando, lat, lon, raio, saida, municipios=None):
    """Mapa IR (C13) georreferenciado em lat/lon com divisas municipais.
    Área do mapa = 2.5x o raio da caixa de medição, p/ dar contexto."""
    import matplotlib.pyplot as plt
    import pyproj
    raio_mapa = max(150.0, raio * 2.5)
    rec = m2.recortar(ds, lat, lon, raio_mapa)
    h = rec.goes_imager_projection.perspective_point_height
    lon0 = rec.goes_imager_projection.longitude_of_projection_origin
    p = pyproj.Proj(proj="geos", h=h, lon_0=lon0, sweep="x")
    X, Y = np.meshgrid(rec.x.values * h, rec.y.values * h)
    LON, LAT = p(X, Y, inverse=True)
    T = rec["CMI"].values - 273.15

    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    ax.set_facecolor("0.85")                      # chão cinza
    Tn = np.ma.masked_where(T > 5, T)
    pm = ax.pcolormesh(LON, LAT, Tn, cmap="turbo_r", vmin=-75, vmax=5,
                       shading="auto")
    plt.colorbar(pm, ax=ax, label="T do topo da nuvem (C)")
    if municipios is not None:
        municipios.boundary.plot(ax=ax, color="dimgray", lw=0.4, alpha=0.8)
    try:
        _carregar("toro_00_caso.py", "caso00").plotar_rio(ax, cor="royalblue", lw=1.2)
    except Exception:
        pass
    # caixa de medição + alvo
    dr = raio / 111.0
    ax.plot(lon, lat, "k+", ms=16, mew=2.5)
    ax.plot([lon - dr, lon + dr, lon + dr, lon - dr, lon - dr],
            [lat - dr, lat - dr, lat + dr, lat + dr, lat - dr],
            "k--", lw=1)
    dm = raio_mapa / 111.0
    ax.set_xlim(lon - dm, lon + dm)
    ax.set_ylim(lat - dm, lat + dm)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    ax.set_title(f"IR C13 — {quando:%Y-%m-%d %H:%M} UT\n"
                 "cinza=sem nuvem | + alvo | tracejado=caixa de medição")
    plt.tight_layout(); plt.savefig(saida, dpi=140); plt.close(fig)

def plotar(df, nome, saida):
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    ax[0].plot(df.tempo, df.tmin, "k-", lw=1.5)
    ax[0].axhline(-20, color="purple", ls="--", lw=1, label="-20 C")
    ax[0].axhline(-35, color="red", ls="--", lw=1, label="-35 C")
    ax[0].invert_yaxis()
    ax[0].set_ylabel("T mínima do topo na caixa (C)")
    # marca as 5 horas mais frias
    top = df.nsmallest(5, "tmin")
    for _, r in top.iterrows():
        ax[0].annotate(f"{r.tempo:%d/%m %H}UT\n{r.tmin:.0f}C",
                       (r.tempo, r.tmin), fontsize=8, color="crimson",
                       ha="center", va="top")
    ax[0].legend(fontsize=8)
    ax[0].set_title(f"Série sobre o alvo — {nome} (horas mais frias anotadas)")
    ax[1].plot(df.tempo, 100 * df.frac20, color="teal", label="% pixels < -20 C")
    ax[1].plot(df.tempo, 100 * df.frac35, color="crimson", label="% pixels < -35 C")
    if df.vis_med.notna().any():
        ax2 = ax[1].twinx()
        ax2.plot(df.tempo, df.vis_med, color="orange", alpha=0.6,
                 label="reflectância média C02")
        ax2.set_ylabel("reflectância C02")
    ax[1].set_ylabel("cobertura fria na caixa (%)")
    ax[1].legend(fontsize=8)
    ax[1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %Hh"))
    plt.tight_layout(); plt.savefig(saida, dpi=150); plt.close(fig)
    print("Figura salva:", saida)

def main():
    import pandas as pd
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("--ini", default="2024-04-27 00:00")
    ap.add_argument("--fim", default="2024-05-04 00:00")
    ap.add_argument("--passo", type=int, default=1, help="horas entre cenas")
    ap.add_argument("--lat", type=float, default=-29.5)
    ap.add_argument("--lon", type=float, default=-51.2)
    ap.add_argument("--raio", type=float, default=60,
                    help="km em torno do alvo (60 = escala da tempestade)")
    ap.add_argument("--nome", default="Toro_01-02mai")
    ap.add_argument("--com-visivel", action="store_true",
                    help="também baixa C02 (dobra o volume; só útil de dia)")
    ap.add_argument("--sem-mapas", action="store_true",
                    help="não gera o mapa IR municipal de cada cena")
    ap.add_argument("--uf", default="RS", help="UF das divisas municipais")
    a = ap.parse_args()

    m2 = _carregar("toro_02_rosenfeld_goes16.py", "rosenfeld02")
    pasta = AQUI / f"saida_{a.nome}"
    pasta.mkdir(exist_ok=True)
    municipios = None if a.sem_mapas else carregar_municipios(a.uf)

    t0 = datetime.strptime(a.ini, "%Y-%m-%d %H:%M")
    t1 = datetime.strptime(a.fim, "%Y-%m-%d %H:%M")
    linhas = []
    t = t0
    while t <= t1:
        try:
            r, ds = medir_cena(m2, t, a.lat, a.lon, a.raio, a.com_visivel)
            print(f"{t:%d/%m %H}UT  Tmin={r['tmin']:6.1f}C  "
                  f"<-20C:{100*r['frac20']:5.1f}%  <-35C:{100*r['frac35']:5.1f}%")
            if not a.sem_mapas:
                png = pasta / f"ir_{t:%Y-%m-%d_%H%M}UT.png"
                mapa_ir(m2, ds, t, a.lat, a.lon, a.raio, str(png), municipios)
        except Exception as e:
            r = dict(tempo=t, tmin=np.nan, frac20=np.nan, frac35=np.nan,
                     vis_med=np.nan, vis_max=np.nan)
            print(f"{t:%d/%m %H}UT  !! falhou: {e}")
        linhas.append(r)
        t += timedelta(hours=a.passo)

    df = pd.DataFrame(linhas)
    csv = pasta / f"serie_{a.nome}.csv"
    df.to_csv(csv, index=False)
    print("\nCSV salvo:", csv)
    ok = df.dropna(subset=["tmin"])
    if len(ok):
        top = ok.nsmallest(8, "tmin")
        print("\n=== HORAS MAIS FRIAS SOBRE O ALVO (candidatas a 'hora ótima') ===")
        for _, r in top.iterrows():
            print(f"  {r.tempo:%Y-%m-%d %H:%M} UT  Tmin={r.tmin:.1f}C  "
                  f"<-20C:{100*r.frac20:.1f}%")
        print("\nUse-as no 04:  --goes-horas " +
              " ".join(f"{r.tempo:%H:%M}" for _, r in top.head(4).iterrows()))
        plotar(df, a.nome, pasta / f"serie_{a.nome}.png")
    else:
        print("Nenhuma cena medida com sucesso.")

if __name__ == "__main__":
    main()
