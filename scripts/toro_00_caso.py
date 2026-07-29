#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
00_caso.py
==========
CONFIGURAÇÃO CENTRAL DO CASO — fonte única de verdade para todos os scripts.

Sistematização (pedido do Reinaldo):
  - O PROTAGONISTA é o toró de 01-02/mai/2024 no corredor do TAQUARI-ANTAS.
    O 12/mai é comparação (pós-FD), não o evento.
  - Período padrão de análise cobre do pré-condicionamento ao pós-FD.
  - Saídas padronizadas: resultados/<modulo>/serie/  (período inteiro)
                         resultados/<modulo>/<YYYY-MM-DD>/  (por data)
  - O rio real (dados_geo/rio_taquari_antas.geojson) é o eixo espacial:
    todo diagnóstico pode ser condicionado à distância ao rio.

Uso nos outros scripts:
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "caso", pathlib.Path(__file__).parent / "toro_00_caso.py")
    caso = importlib.util.module_from_spec(spec); spec.loader.exec_module(caso)
"""

import json
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parents[1]

# ----------------------------------------------------------------------
# TEMPO
# ----------------------------------------------------------------------
PERIODO = ("2024-04-25", "2024-05-16")     # análise padrão (séries)
PERIODO_CHUVA = ("2024-04-27", "2024-05-03")  # os dias de chuva do EOCE
DATAS_CHUVA = ["2024-04-27", "2024-04-28", "2024-04-29", "2024-04-30",
               "2024-05-01", "2024-05-02", "2024-05-03"]
DATAS_TORO = ["2024-05-01", "2024-05-02"]  # O EVENTO (pico 17-21h local
                                           #   de 02/mai = 20-00 UT)
# Cicatrizes: 'antes' fecha ANTES das chuvas (~22/04); 'depois' fecha antes
# de 06/05 p/ NÃO misturar com o evento de 10-12/05.
CICATRIZ_ANTES = ("2024-04-12", "2024-04-26")
CICATRIZ_DEPOIS = ("2024-05-03", "2024-05-09")
DATAS_POSFD = ["2024-05-11", "2024-05-12"] # comparação pós-FD
DATAS_CONTROLE = ["2024-04-15", "2024-06-12"]  # dias comuns sem toró/FD

MARCOS_SOLARES = [
    ("2024-04-27 00:00", "INÍCIO DAS CHUVAS (27/04)", "teal"),
    ("2024-05-03 02:00", "TORÓ (02 UT 03/05)", "green"),
    ("2024-05-08 22:36", "CME geoefetivo lançado", "orange"),
    ("2024-05-10 17:05", "SSC — CME chega à Terra", "red"),
    ("2024-05-11 00:00", "Mínimo do Forbush (~15% Oulu; ~2-3% no RS)", "purple"),
    ("2024-05-11 03:00", "GLE74", "blue"),
]

# Sismos catalogados (RSBR/USP), madrugada de 13/05/2024 — tempos de origem UT
SISMOS_UT = ["2024-05-13 04:48:43",   # usp2024jjjl mR 2,39 Bento Gonçalves
             "2024-05-13 05:37:48",   # usp2024jjlb mR 2,18 Veranópolis
             "2024-05-13 05:58:46",   # usp2024jjlt mR 2,19 Caxias do Sul
             "2024-05-13 06:03:09"]   # usp2024jjlx mR 2,16 Caxias do Sul
T_SSC_REF = "2024-05-10 17:05"

# ----------------------------------------------------------------------
# ESPAÇO — o corredor do Taquari-Antas
# ----------------------------------------------------------------------
ALVO = dict(nome="Toro_TaquariAntas", lat=-29.5, lon=-51.2)
ESTACAO_SONDAGEM = "83971"                 # POA (mais perto do corredor)
RIO_GEOJSON = AQUI / "dados/geo" / "rio_taquari_antas.geojson"

_SEGMENTOS = None   # cache: lista de arrays (N,2) [lon, lat]

def carregar_rio():
    """Segmentos do rio real (geojson). Retorna lista de arrays (N,2) lon/lat."""
    global _SEGMENTOS
    if _SEGMENTOS is not None:
        return _SEGMENTOS
    segs = []
    if RIO_GEOJSON.exists():
        d = json.loads(RIO_GEOJSON.read_text(encoding="utf-8"))
        for ft in d.get("features", [d]):
            g = ft.get("geometry", ft)
            if g["type"] == "LineString":
                segs.append(np.asarray(g["coordinates"], float)[:, :2])
            elif g["type"] == "MultiLineString":
                segs += [np.asarray(p, float)[:, :2] for p in g["coordinates"]]
    else:
        print(f"!! {RIO_GEOJSON} não encontrado — usando traçado aproximado")
        segs = [np.array([[-49.85, -28.75], [-50.30, -28.90], [-50.75, -29.00],
                          [-51.20, -29.05], [-51.55, -29.10], [-51.87, -29.17],
                          [-51.95, -29.45], [-51.86, -29.80], [-51.70, -29.95]])]
    _SEGMENTOS = segs
    return segs

def dist_km_ao_rio(lat, lon):
    """Distância (km) de pontos ao rio. Aceita escalares ou arrays (broadcast).
    Aproximação plana local (~-29.5S): 1° lon = 96 km, 1° lat = 111 km."""
    lat = np.atleast_1d(np.asarray(lat, float))
    lon = np.atleast_1d(np.asarray(lon, float))
    px = lon * 96.0
    py = lat * 111.0
    dmin = np.full(lat.shape, np.inf)
    for seg in carregar_rio():
        sx = seg[:, 0] * 96.0
        sy = seg[:, 1] * 111.0
        ax, ay = sx[:-1], sy[:-1]
        bx, by = sx[1:], sy[1:]
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy + 1e-12
        # distância ponto-segmento, vetorizada nos segmentos, loop nos pontos
        for i in np.ndindex(lat.shape):
            wx, wy = px[i] - ax, py[i] - ay
            t = np.clip((wx * vx + wy * vy) / L2, 0, 1)
            d2 = (wx - t * vx) ** 2 + (wy - t * vy) ** 2
            dmin[i] = min(dmin[i], np.sqrt(d2.min()))
    return dmin if dmin.size > 1 else float(dmin.ravel()[0])

def plotar_rio(ax, cor="blue", lw=1.2, alpha=0.8, rotulo="Taquari-Antas"):
    """Desenha o rio real num eixo lon/lat."""
    for k, seg in enumerate(carregar_rio()):
        ax.plot(seg[:, 0], seg[:, 1], color=cor, lw=lw, alpha=alpha,
                label=rotulo if k == 0 else None)

def bbox_corredor(folga_km=25):
    """Bounding box do rio + folga (lonW, latS, lonE, latN)."""
    segs = np.vstack(carregar_rio())
    dlon = folga_km / 96.0
    dlat = folga_km / 111.0
    return [segs[:, 0].min() - dlon, segs[:, 1].min() - dlat,
            segs[:, 0].max() + dlon, segs[:, 1].max() + dlat]

# ----------------------------------------------------------------------
# SAÍDAS PADRONIZADAS
# ----------------------------------------------------------------------
def pasta_saida(modulo, data=None):
    """resultados/<modulo>/serie/ ou resultados/<modulo>/<data>/"""
    p = AQUI / "resultados" / modulo / (data if data else "serie")
    p.mkdir(parents=True, exist_ok=True)
    return p

if __name__ == "__main__":
    segs = carregar_rio()
    print(f"Rio: {len(segs)} segmentos, {sum(len(s) for s in segs)} vértices")
    print("bbox corredor (25 km):", [round(x, 2) for x in bbox_corredor()])
    print("dist teste (Lajeado -29.45,-51.96):",
          round(dist_km_ao_rio(-29.45, -51.96), 1), "km")
    print("dist teste (POA -30.03,-51.23):",
          round(dist_km_ao_rio(-30.03, -51.23), 1), "km")
    print("Períodos:", PERIODO, "| toró:", DATAS_TORO, "| pós-FD:", DATAS_POSFD)
