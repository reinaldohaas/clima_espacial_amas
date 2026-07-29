#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
08_cicatrizes_sentinel2.py
==========================
CICATRIZES (deslizamentos/erosão) no Sentinel-2: ANTES vs. DEPOIS do evento.

MÉTODO: composito de NDVI antes e depois; cicatriz = pixel que ERA vegetado
(NDVI_antes > 0.5) e perdeu vegetação (dNDVI < -0.25). Nuvem/sombra/água
mascaradas pela banda SCL do L2A.

DADOS: Sentinel-2 L2A via Earth Search (AWS, STAC) — público, SEM chave.
  pip install pystac-client odc-stac rioxarray

⚠️ LIMITE DE DATAÇÃO (leia!): o S2 revisita a cada ~5 dias e maio/2024 foi
nublado no RS. Dá para dizer "cicatriz surgiu entre a última cena limpa
ANTES e a primeira DEPOIS" — não "no dia 12". Para separar cicatrizes do
toró de 01-02/mai das do 10-12/mai, tente uma janela intermediária limpa
(03-09/mai) com --antes-ini/--antes-fim; se não houver cena limpa, o
resultado vale para o evento de abril-maio como um todo. Além disso, no
FUNDO DE VALE a perda de NDVI é ALAGAMENTO/lama, não deslizamento — cruze
com a declividade (cicatriz de escorregamento vive na encosta).

Uso:
  python 08_cicatrizes_sentinel2.py                       # Vale do Taquari
  python 08_cicatrizes_sentinel2.py --bbox -52.2 -29.9 -51.2 -28.9
  python 08_cicatrizes_sentinel2.py --antes-ini 2024-05-03 --antes-fim 2024-05-09
"""

import argparse
import importlib.util
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parents[1]

def _caso():
    spec = importlib.util.spec_from_file_location("caso00", AQUI / "toro_00_caso.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
STAC_URL = "https://earth-search.aws.element84.com/v1"
COLECAO = "sentinel-2-l2a"
SCL_RUIM = [0, 1, 3, 8, 9, 10, 11]   # nodata, defeito, sombra, nuvens, cirrus, neve
SCL_AGUA = 6

def buscar_cenas(bbox, ini, fim, max_nuvem=60, por_tile=3):
    """Busca cenas e seleciona as MENOS NUBLADAS DE CADA TILE (granulo MGRS).
    Sem isso, as 'melhores' cenas podem ser todas do mesmo tile e o
    composite fica com buracos em L (tiles vizinhos sem cena)."""
    from collections import defaultdict
    from pystac_client import Client
    cli = Client.open(STAC_URL)
    itens = list(cli.search(collections=[COLECAO], bbox=bbox,
                            datetime=f"{ini}/{fim}",
                            query={"eo:cloud_cover": {"lt": max_nuvem}}).items())
    portile = defaultdict(list)
    for it in itens:
        tile = (it.properties.get("grid:code")
                or it.properties.get("s2:mgrs_tile", "?"))
        portile[tile].append(it)
    sel = []
    print(f"  {len(itens)} cenas {ini}..{fim} em {len(portile)} tiles:")
    for tile, lst in sorted(portile.items()):
        lst.sort(key=lambda it: it.properties.get("eo:cloud_cover", 100))
        sel += lst[:por_tile]
        melhores = ", ".join(f"{it.datetime:%d/%m}({it.properties['eo:cloud_cover']:.0f}%)"
                             for it in lst[:por_tile])
        print(f"    {tile}: {len(lst)} cenas -> usando {melhores}")
    if len(portile) < 2:
        print("  !! Só 1 tile encontrado — se o mapa sair com buraco, alargue "
              "a janela de datas ou suba --max-nuvem.")
    return sel

def compositar_ndvi(itens, bbox, res=20, com_rgb=True):
    """Mediana de NDVI (nuvem mascarada via SCL) + composito COR VERDADEIRA."""
    from odc.stac import load as stac_load
    bandas = ["red", "nir", "scl"] + (["green", "blue"] if com_rgb else [])
    ds = stac_load(itens, bands=bandas,
                   bbox=bbox, resolution=res, chunks={},
                   groupby="solar_day")
    red = ds.red.astype("float32")
    nir = ds.nir.astype("float32")
    scl = ds.scl
    ruim = scl.isin(SCL_RUIM)
    ndvi = (nir - red) / (nir + red + 1e-6)
    ndvi = ndvi.where(~ruim)
    agua = scl.isin([SCL_AGUA]).sum("time") > (len(ds.time) / 2)
    comp = ndvi.median("time").compute()
    cobertura = 100 * float(np.isfinite(comp.values).mean())
    print(f"  cobertura válida do composite: {cobertura:.0f}%"
          + ("  !! alargue a janela/nuvem" if cobertura < 85 else ""))
    rgb = None
    if com_rgb:
        pilha = []
        for b in ("red", "green", "blue"):
            band = ds[b].astype("float32").where(~ruim)
            pilha.append(band.median("time").compute().values)
        # esticamento adaptativo: p2-p98 por banda + gama 1.6 (clareia)
        canais = []
        for v in pilha:
            lo, hi = np.nanpercentile(v, [2, 98])
            canais.append(np.clip((v - lo) / max(hi - lo, 1), 0, 1) ** (1 / 1.6))
        rgb = np.dstack(canais)
    return comp, agua.compute(), rgb

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    # bbox default: Vale do Taquari / encosta da Serra (lonW latS lonE latN)
    ap.add_argument("--bbox", nargs=4, type=float,
                    default=[-52.3, -29.9, -50.9, -28.8])
    ap.add_argument("--antes-ini", default="2024-03-15")
    ap.add_argument("--antes-fim", default="2024-04-26")
    ap.add_argument("--depois-ini", default="2024-05-13")
    ap.add_argument("--depois-fim", default="2024-06-30")
    ap.add_argument("--res", type=int, default=20, help="m/pixel (10 = pesado)")
    ap.add_argument("--dndvi", type=float, default=-0.25)
    ap.add_argument("--ndvi-min-antes", type=float, default=0.5)
    ap.add_argument("--nome", default="cicatrizes_mai2024")
    ap.add_argument("--max-nuvem", type=int, default=60)
    ap.add_argument("--por-tile", type=int, default=3,
                    help="nº de cenas menos nubladas usadas por tile MGRS")
    a = ap.parse_args()
    bbox = a.bbox

    print("== ANTES ==")
    it_a = buscar_cenas(bbox, a.antes_ini, a.antes_fim, a.max_nuvem, a.por_tile)
    print("== DEPOIS ==")
    it_d = buscar_cenas(bbox, a.depois_ini, a.depois_fim, a.max_nuvem, a.por_tile)
    if not it_a or not it_d:
        raise SystemExit("Sem cenas suficientes — alargue as janelas/nuvem.")

    print("Compositando ANTES (pode demorar)...")
    ndvi_a, agua_a, rgb_a = compositar_ndvi(it_a, bbox, a.res)
    print("Compositando DEPOIS...")
    ndvi_d, agua_d, rgb_d = compositar_ndvi(it_d, bbox, a.res)

    dndvi = ndvi_d - ndvi_a
    cicatriz = (ndvi_a > a.ndvi_min_antes) & (dndvi < a.dndvi) & \
               (~agua_a) & (~agua_d)

    pasta = AQUI / f"saida_{a.nome}"
    pasta.mkdir(exist_ok=True)

    # GeoTIFFs p/ SIG (QGIS etc.)
    import rioxarray  # noqa: F401 — registra o acessor .rio no xarray
    crs = ndvi_a.rio.crs or "EPSG:32722"
    for nome, arr in [("ndvi_antes", ndvi_a), ("ndvi_depois", ndvi_d),
                      ("dndvi", dndvi),
                      ("cicatriz", cicatriz.astype("uint8"))]:
        arr = arr.rio.write_crs(crs)
        arr.rio.to_raster(pasta / f"{nome}.tif")
    print("GeoTIFFs salvos em", pasta)

    # figura 2x3: cor verdadeira antes/depois em cima, análise embaixo
    import matplotlib.pyplot as plt
    ext = [bbox[0], bbox[2], bbox[1], bbox[3]]
    fig, axs = plt.subplots(2, 3, figsize=(17, 11), sharex=True, sharey=True)
    if rgb_a is not None:
        axs[0, 0].imshow(rgb_a, extent=ext)
        axs[0, 0].set_title("COR VERDADEIRA — antes")
    if rgb_d is not None:
        axs[0, 1].imshow(rgb_d, extent=ext)
        axs[0, 1].set_title("COR VERDADEIRA — depois")
    # depois com as cicatrizes por cima (é aqui que se VÊ a erosão)
    if rgb_d is not None:
        axs[0, 2].imshow(rgb_d, extent=ext)
        cic = np.ma.masked_where(~cicatriz.values, cicatriz.values)
        axs[0, 2].imshow(cic, cmap="autumn", extent=ext, alpha=0.9,
                         vmin=0, vmax=1)  # 1 -> amarelo de verdade
        axs[0, 2].set_title("depois + cicatrizes (amarelo)")
    for ax, (arr, t, cm, vmin, vmax) in zip(axs[1], [
            (ndvi_a, "NDVI antes", "RdYlGn", 0, 0.9),
            (ndvi_d, "NDVI depois", "RdYlGn", 0, 0.9),
            (dndvi, "ΔNDVI (depois-antes)", "RdBu", -0.5, 0.5)]):
        im = ax.imshow(arr.values, cmap=cm, vmin=vmin, vmax=vmax, extent=ext)
        ax.set_title(t); plt.colorbar(im, ax=ax, shrink=0.7)
    # rio real por cima de todos os painéis + estatística por distância
    caso = _caso()
    for ax in axs.ravel():
        caso.plotar_rio(ax, cor="cyan", lw=0.9, alpha=0.9)
        ax.set_xlim(bbox[0], bbox[2]); ax.set_ylim(bbox[1], bbox[3])
    frac = float(cicatriz.mean()) * 100
    fig.suptitle(f"{a.nome} — {frac:.2f}% da área virou cicatriz "
                 f"(NDVI>{a.ndvi_min_antes} antes, ΔNDVI<{a.dndvi})")
    plt.tight_layout()
    plt.savefig(pasta / f"{a.nome}.png", dpi=150)
    print("Figura salva:", pasta / f"{a.nome}.png")

    # cicatriz vs. distância ao rio (amostrada p/ não pesar)
    jj, ii = np.where(cicatriz.values)
    if jj.size:
        passo = max(1, jj.size // 4000)          # amostra ~4000 pixels
        ny, nx = cicatriz.shape
        lats = bbox[3] + (bbox[1] - bbox[3]) * (jj[::passo] + 0.5) / ny
        lons = bbox[0] + (bbox[2] - bbox[0]) * (ii[::passo] + 0.5) / nx
        d = caso.dist_km_ao_rio(lats, lons)
        print("\n--- Cicatrizes por distância ao rio (amostra) ---")
        for lim in (1, 2, 5, 10):
            print(f"  até {lim:2d} km do rio: {100 * (d < lim).mean():.0f}%")
        print("  (concentração perto do rio = toró fluvial; espalhada = "
              "chuva generalizada)")
    print("\nLembrete: fundo de vale = alagamento, encosta = deslizamento. "
          "Cruze o cicatriz.tif com declividade no QGIS antes de concluir.")

if __name__ == "__main__":
    main()
