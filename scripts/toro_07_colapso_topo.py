#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
07_colapso_topo.py
==================
DETECTOR DE COLAPSO DE TOPO (o candidato a "toró" pixel a pixel).

IDEIA: o desabamento de uma coluna gelada aparece no GOES como o topo
ESQUENTANDO rápido num ponto (a torre desmonta), enquanto a vizinhança
segue fria. Varre as cenas C13 de 10 em 10 minutos e marca pixels com:
    T(antes) < --tfrio   E   dT/10min > --limiar
Como o toró (hipótese) é ancorado na orografia, os eventos devem se
EMPILHAR no mesmo lugar — o mapa de frequência mostra a âncora.

TRÊS SAÍDAS por rodada (em saida_<nome>/):
  1. colapsos_<nome>.csv        — cada evento: tempo, lat, lon, T antes, dT
  2. freq_colapso_<nome>.png    — mapa de frequência + municípios + corredor
                                  Taquari-Antas (traçado APROXIMADO) + alvo
  3. recortes_sudeste/*.npz     — recorte GRANDE do sudeste da América do Sul
                                  (lat -37.85..-16.0, lon -65.95..-46.0) de
                                  cada cena, p/ análise futura da anti-varredura.
                                  ~4-6 MB/cena comprimido (T em float16).

VOLUME: 10-min por ~14 h = ~84 cenas C13 Full Disk (~6-10 GB no cache
dados_goes/; reaproveita o que já existe). Deixe rodando à noite:
  python 07_colapso_topo.py                       # noite 01-02/mai default
  python 07_colapso_topo.py --raio 60             # fechar o zoom depois
  python 07_colapso_topo.py --sem-recorte-grande  # só a detecção
"""

import argparse
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parents[1]

# Recorte grande p/ anti-varredura (canto SW e NE, pedido do Reinaldo)
BOX_GRANDE = dict(lat_min=-37.85363187582974, lat_max=-15.995074320561946,
                  lon_min=-65.94647864710005, lon_max=-46.00925976040889)

# Rio: usa o traçado REAL de dados_geo/rio_taquari_antas.geojson via 00_caso
# (com fallback aproximado embutido lá).

def _carregar(nome_arquivo, alias):
    spec = importlib.util.spec_from_file_location(alias, AQUI / nome_arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def baixar_c13(m2, quando):
    from goes2go import GOES
    g = GOES(satellite=16, product="ABI-L2-CMIPF", channel=[13])
    return g.nearesttime(quando.strftime("%Y-%m-%d %H:%M"),
                         save_dir=str(m2.CACHE_GOES), overwrite=False)

def georref(rec):
    """lat/lon 2D do recorte (grade fixa GOES)."""
    import pyproj
    h = rec.goes_imager_projection.perspective_point_height
    lon0 = rec.goes_imager_projection.longitude_of_projection_origin
    p = pyproj.Proj(proj="geos", h=h, lon_0=lon0, sweep="x")
    X, Y = np.meshgrid(rec.x.values * h, rec.y.values * h)
    return p(X, Y, inverse=True)   # LON, LAT

def recortar_box(m2, ds, box):
    """Recorte por cantos lat/lon (aprox., via projeção dos 4 cantos)."""
    import pyproj
    h = ds.goes_imager_projection.perspective_point_height
    lon0 = ds.goes_imager_projection.longitude_of_projection_origin
    p = pyproj.Proj(proj="geos", h=h, lon_0=lon0, sweep="x")
    cantos = [(box["lon_min"], box["lat_min"]), (box["lon_min"], box["lat_max"]),
              (box["lon_max"], box["lat_min"]), (box["lon_max"], box["lat_max"])]
    xs, ys = zip(*[p(lo, la) for lo, la in cantos])
    xg = ds.x.values * h; yg = ds.y.values * h
    ix = np.where((xg > min(xs)) & (xg < max(xs)))[0]
    iy = np.where((yg > min(ys)) & (yg < max(ys)))[0]
    return ds.isel(x=slice(ix.min(), ix.max() + 1), y=slice(iy.min(), iy.max() + 1))

def salvar_recorte_grande(m2, ds, quando, pasta_npz):
    """Guarda o recorte sudeste em .npz comprimido (T float16 + lat/lon)."""
    rec = recortar_box(m2, ds, BOX_GRANDE)
    f = pasta_npz / f"c13_{quando:%Y-%m-%d_%H%M}UT.npz"
    if f.exists():
        return
    LON, LAT = georref(rec)
    T = (rec["CMI"].values - 273.15).astype(np.float16)
    np.savez_compressed(f, T=T, lat=LAT.astype(np.float32),
                        lon=LON.astype(np.float32),
                        tempo=quando.strftime("%Y-%m-%d %H:%M"))

_CASO = None
def _caso():
    """Config central (00_caso.py) carregada uma vez só."""
    global _CASO
    if _CASO is None:
        _CASO = _carregar("toro_00_caso.py", "caso00")
    return _CASO

def dist_km_ao_rio(lat, lon):
    """Distância (km) ao rio REAL (geojson via 00_caso)."""
    return _caso().dist_km_ao_rio(lat, lon)

def mapa_frequencia(freq, LON, LAT, alvo, municipios, saida, titulo):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 8))
    ax.set_facecolor("0.9")
    m = np.ma.masked_where(freq == 0, freq)
    pm = ax.pcolormesh(LON, LAT, m, cmap="hot_r", shading="auto")
    plt.colorbar(pm, ax=ax, label="nº de colapsos detectados no pixel")
    if municipios is not None:
        municipios.boundary.plot(ax=ax, color="dimgray", lw=0.4, alpha=0.8)
    _caso().plotar_rio(ax, cor="blue", lw=1.5)
    ax.plot(alvo[1], alvo[0], "k+", ms=16, mew=2.5)
    ax.set_xlim(LON.min(), LON.max()); ax.set_ylim(LAT.min(), LAT.max())
    ax.set_title(titulo); ax.legend(fontsize=8)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    plt.tight_layout(); plt.savefig(saida, dpi=150); plt.close(fig)
    print("Mapa salvo:", saida)

def main():
    import pandas as pd
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("--ini", default="2024-05-01 20:00")
    ap.add_argument("--fim", default="2024-05-02 10:00")
    ap.add_argument("--passo-min", type=int, default=10)
    ap.add_argument("--lat", type=float, default=-29.5)
    ap.add_argument("--lon", type=float, default=-51.2)
    ap.add_argument("--raio", type=float, default=150,
                    help="km da área de DETECÇÃO (reduza p/ fechar o zoom)")
    ap.add_argument("--limiar", type=float, default=12,
                    help="aquecimento mínimo do topo (K) entre cenas")
    ap.add_argument("--tfrio", type=float, default=-35,
                    help="T máx (C) do pixel ANTES p/ contar como torre fria")
    ap.add_argument("--nome", default="Toro_01-02mai")
    ap.add_argument("--sem-recorte-grande", action="store_true")
    ap.add_argument("--uf", default="RS")
    a = ap.parse_args()

    m2 = _carregar("toro_02_rosenfeld_goes16.py", "rosenfeld02")
    m5 = _carregar("toro_05_serie_alvo.py", "serie05")
    pasta = AQUI / f"saida_{a.nome}"
    pasta.mkdir(exist_ok=True)
    pasta_npz = pasta / "recortes_sudeste"
    pasta_npz.mkdir(exist_ok=True)
    municipios = m5.carregar_municipios(a.uf)

    t0 = datetime.strptime(a.ini, "%Y-%m-%d %H:%M")
    t1 = datetime.strptime(a.fim, "%Y-%m-%d %H:%M")

    eventos, T_ant, LON = [], None, None
    freq = None
    t = t0
    while t <= t1:
        try:
            ds = baixar_c13(m2, t)
            if not a.sem_recorte_grande:
                salvar_recorte_grande(m2, ds, t, pasta_npz)
            rec = m2.recortar(ds, a.lat, a.lon, a.raio)
            T = rec["CMI"].values - 273.15
            if LON is None:
                LON, LAT = georref(rec)
                freq = np.zeros_like(T, dtype=int)
            if T_ant is not None and T.shape == T_ant.shape:
                dT = T - T_ant
                col = (T_ant < a.tfrio) & (dT > a.limiar)
                ny, nx = np.where(col)
                for j, i in zip(ny, nx):
                    eventos.append(dict(
                        tempo=t, lat=float(LAT[j, i]), lon=float(LON[j, i]),
                        T_antes=float(T_ant[j, i]), dT=float(dT[j, i]),
                        dist_rio_km=round(dist_km_ao_rio(LAT[j, i], LON[j, i]), 1)))
                freq[col] += 1
                print(f"{t:%d/%m %H:%M}UT  colapsos: {col.sum():3d}  "
                      f"(Tmin cena: {np.nanmin(T):.0f}C)")
            T_ant = T
        except Exception as e:
            print(f"{t:%d/%m %H:%M}UT  !! falhou: {e}")
            T_ant = None          # não compara através de buraco na série
        t += timedelta(minutes=a.passo_min)

    df = pd.DataFrame(eventos)
    csv = pasta / f"colapsos_{a.nome}.csv"
    df.to_csv(csv, index=False)
    print(f"\n{len(df)} eventos salvos em {csv}")
    if len(df):
        no_rio = df[df.dist_rio_km < 15]
        print(f"  -> {len(no_rio)} a menos de 15 km do corredor Taquari-Antas")
        print("\nTop horários (nº de colapsos):")
        print(df.groupby(df.tempo.dt.strftime("%d/%m %H:%M")).size()
                .sort_values(ascending=False).head(8).to_string())
        mapa_frequencia(freq, LON, LAT, (a.lat, a.lon), municipios,
                        pasta / f"freq_colapso_{a.nome}.png",
                        f"Frequência de colapso de topo — {a.nome}\n"
                        f"(T<{a.tfrio}C esquentando >{a.limiar}K/"
                        f"{a.passo_min}min)")

if __name__ == "__main__":
    main()
