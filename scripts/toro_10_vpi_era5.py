#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10_vpi_era5.py
==============
VPI (VORTICIDADE POTENCIAL ISENTRÓPICA) do ERA5 — dia 02 vs. dia 12/mai.

PERGUNTA: houve intrusão estratosférica / dobra de tropopausa sobre o RS
nos dias de toró? A VPI mostra: no HS, ar estratosférico tem PV < -2 PVU;
uma "língua" de PV negativo descendo em 330/315 K + tropopausa dinâmica
baixa (pressão alta na superfície de -2 PVU) = intrusão. Isso conecta a
dinâmica de altos níveis à sua cadeia elétrica: a intrusão muda a coluna
condutiva E o forçamento sinótico ao mesmo tempo.

O QUE FAZ (por data/hora):
  1) Baixa ERA5 (T, u, v em níveis de pressão) via CDS — precisa da sua
     chave em ~/.cdsapirc. Cache em dados_era5/.
  2) Calcula theta e PV baroclínica; interpola PV para 330 K e 315 K.
  3) Mapa da PV nas duas isentrópicas + mapa da PRESSÃO da tropopausa
     dinâmica (superfície de -2 PVU): quanto maior a pressão, mais funda
     a intrusão.
  4) Resume: pressão máxima da tropopausa dinâmica na caixa do evento.

Uso:
  pip install cdsapi metpy xarray netcdf4
  python 10_vpi_era5.py                                   # 02 e 12/mai
  python 10_vpi_era5.py --datas 2024-05-02 2024-05-12 --horas 00 12 18
"""

import argparse
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parents[1]
CACHE = AQUI / "dados/era5"

# área CDS: [N, W, S, E] — sudeste da América do Sul com folga
AREA = [-10, -80, -45, -30]
NIVEIS = ["150", "200", "250", "300", "350", "400", "450", "500", "600", "700"]
ALVO_BOX = dict(lat_min=-32, lat_max=-27, lon_min=-56, lon_max=-49)

def baixar_era5(data):
    """Um NetCDF por data (4 horários sinóticos). Cache local."""
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"era5_pv_{data}.nc"
    if f.exists():
        return f
    import cdsapi
    c = cdsapi.Client()
    print(f"  CDS: pedindo {data} (pode levar minutos na fila)...")
    c.retrieve("reanalysis-era5-pressure-levels",
               dict(product_type="reanalysis", format="netcdf",
                    variable=["temperature", "u_component_of_wind",
                              "v_component_of_wind"],
                    pressure_level=NIVEIS, year=data[:4], month=data[5:7],
                    day=data[8:10], time=["00:00", "06:00", "12:00", "18:00"],
                    area=AREA), str(f))
    return f

def calcular_vpi(f, hora):
    """PV baroclínica no grid isobárico -> interpola p/ 330/315 K e
    acha a pressão da tropopausa dinâmica (-2 PVU)."""
    import metpy.calc as mpcalc
    import xarray as xr
    from metpy.interpolate import interpolate_to_isosurface
    from metpy.units import units

    ds = xr.open_dataset(f)
    # nomes variam entre versões do CDS (time/valid_time, level/pressure_level)
    tdim = "valid_time" if "valid_time" in ds.dims else "time"
    ldim = "pressure_level" if "pressure_level" in ds.dims else "level"
    ds = ds.sel({tdim: f"{str(f).split('_')[-1][:10]} {hora}:00"}, method="nearest")
    ds = ds.sortby(ldim, ascending=False)          # 700 -> 150 (p decrescente)
    lat = ds.latitude.values
    lon = ds.longitude.values
    p = ds[ldim].values.astype(float) * units.hPa
    T = ds["t"].values * units.kelvin
    u = ds["u"].values * (units.meter / units.second)
    v = ds["v"].values * (units.meter / units.second)

    p3 = p[:, None, None] * np.ones_like(T.m) if T.ndim == 3 else p
    theta = mpcalc.potential_temperature(p3, T)
    dx, dy = mpcalc.lat_lon_grid_deltas(lon, lat)
    pv = mpcalc.potential_vorticity_baroclinic(
        theta, p3, u, v, dx[None, :, :], dy[None, :, :],
        np.deg2rad(lat)[None, :, None] * units.radian)

    pvu = pv.to("K * m**2 / (kg * s)").m * 1e6     # em PVU
    th = theta.m
    pv330 = interpolate_to_isosurface(th, pvu, 330.0)
    pv315 = interpolate_to_isosurface(th, pvu, 315.0)
    # tropopausa dinâmica HS: superfície PV = -2 PVU (usa -PV crescente)
    p_trop = interpolate_to_isosurface(-pvu, p3.m if hasattr(p3, "m") else
                                       np.array(p3), 2.0)
    return lat, lon, pv330, pv315, p_trop

def plotar(lat, lon, pv330, pv315, p_trop, titulo, saida):
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(17, 5.5), sharey=True)
    for ax, campo, t, vmin, vmax, cm in [
            (axs[0], pv330, "PV @ 330 K (PVU)", -8, 2, "RdBu_r"),
            (axs[1], pv315, "PV @ 315 K (PVU)", -8, 2, "RdBu_r"),
            (axs[2], p_trop, "pressão da tropopausa dinâmica (hPa)",
             100, 500, "viridis")]:
        pm = ax.pcolormesh(lon, lat, campo, cmap=cm, vmin=vmin, vmax=vmax,
                           shading="auto")
        plt.colorbar(pm, ax=ax, shrink=0.85)
        if "PV" in t:
            ax.contour(lon, lat, campo, levels=[-2], colors="k", linewidths=1.5)
        ax.plot(-51.2, -29.5, "r+", ms=14, mew=2.5)
        b = ALVO_BOX
        ax.plot([b["lon_min"], b["lon_max"], b["lon_max"], b["lon_min"], b["lon_min"]],
                [b["lat_min"], b["lat_min"], b["lat_max"], b["lat_max"], b["lat_min"]],
                "r--", lw=1)
        ax.set_title(t, fontsize=10)
    fig.suptitle(titulo)
    plt.tight_layout(); plt.savefig(saida, dpi=140); plt.close(fig)
    print("  Figura salva:", saida)

def main():
    import pandas as pd
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("--datas", nargs="+",
                    default=["2024-05-02", "2024-05-12"])
    ap.add_argument("--horas", nargs="+", default=["00", "06", "12", "18"])
    ap.add_argument("--nome", default="VPI_02x12mai")
    a = ap.parse_args()

    pasta = AQUI / f"saida_{a.nome}"
    pasta.mkdir(exist_ok=True)
    resumo = []
    for data in a.datas:
        try:
            f = baixar_era5(data)
        except Exception as e:
            print(f"!! CDS falhou p/ {data}: {e}")
            continue
        for hora in a.horas:
            try:
                lat, lon, pv330, pv315, p_trop = calcular_vpi(f, hora)
                png = pasta / f"vpi_{data}_{hora}UT.png"
                plotar(lat, lon, pv330, pv315, p_trop,
                       f"VPI ERA5 — {data} {hora} UT", png)
                b = ALVO_BOX
                mla = (lat >= b["lat_min"]) & (lat <= b["lat_max"])
                mlo = (lon >= b["lon_min"]) & (lon <= b["lon_max"])
                pt = p_trop[np.ix_(mla, mlo)]
                resumo.append(dict(quando=f"{data} {hora}UT",
                                   p_trop_max=float(np.nanmax(pt)),
                                   pv330_min=float(np.nanmin(
                                       pv330[np.ix_(mla, mlo)]))))
                print(f"  {data} {hora}UT: tropopausa dinâmica desce até "
                      f"{np.nanmax(pt):.0f} hPa na caixa; PV330 mín "
                      f"{np.nanmin(pv330[np.ix_(mla, mlo)]):.1f} PVU")
            except Exception as e:
                print(f"!! {data} {hora}UT falhou: {e}")
    if resumo:
        pd.DataFrame(resumo).to_csv(pasta / "resumo_vpi.csv", index=False)
        print("\nResumo salvo em", pasta / "resumo_vpi.csv")
        print("Leitura: tropopausa dinâmica > ~350 hPa na caixa = intrusão "
              "funda; compare dia 02 vs dia 12 vs um dia calmo de controle.")

if __name__ == "__main__":
    main()
