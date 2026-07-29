#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02_rosenfeld_goes16.py
======================
MÉTODO ROSENFELD (r_e vs. T) aplicado ao GOES-16 (ABI) sobre um alvo de toró.

OBJETIVO: verificar a assinatura microfísica que o toró prevê:
  (1) ÁGUA SUPER-RESFRIADA (SLW) persistente  -> r_e cresce (fase líquida)
      ABAIXO de -20 C, em vez de glaciar cedo.
  (2) GLACIAÇÃO RETARDADA + salto abrupto      -> transição p/ gelo tardia.
  (3) DSD ESTREITA (ar prístino)               -> r_e cresce devagar com a altura.

BASE FÍSICA (Rosenfeld & Lensky 1998; Rosenfeld et al. 2008):
  Relaciona o raio efetivo no topo (r_e, da banda 3,9 um) com a temperatura
  do topo (T, da banda 10,3 um). A curva r_e(T), montada com MUITOS pixels de
  uma região convectiva num instante, revela as zonas termodinâmicas.

COMO USAR NO COWORK (precisa de internet + ~GBs de dados):
  pip install goes2go xarray numpy matplotlib pyproj netcdf4
  Editar ALVO (lat, lon, raio) e JANELA (data/hora UT).
  python 02_rosenfeld_goes16.py

BANDAS ABI USADAS:
  C07 (3,9 um)  -> reflectância p/ derivar r_e no topo
  C13 (10,3 um) -> temperatura de brilho do topo (T)
  C02 (0,64 um) -> reflectância visível (contexto / máscara de nuvem)
  (r_e rigoroso usa C05/1,6um ou C06/2,2um; 3,9um é a aproximação clássica)
"""

import numpy as np
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------
# CONFIG  <<< PREENCHER >>>
# ----------------------------------------------------------------------
ALVO = dict(nome="Cheia RS 12mai", lat=-29.5, lon=-51.2, raio_km=150)
# Rosenfeld é DIURNO: use 12-21 UT no RS (03-09 UT é madrugada -> visível=0).
JANELA = dict(data="2024-05-12", hora_ini="15:00", hora_fim="18:00")  # UT
# Para comparar: rode também num dia-CONTROLE sem evento solar (ex. abril calmo)
# e num evento de "chuva comum" para ver a diferença de assinatura.

# ----------------------------------------------------------------------
# 1) BAIXAR GOES-16 ABI (via goes2go)
# ----------------------------------------------------------------------
# Cache local dos NetCDF do GOES (ficam guardados; goes2go NÃO baixa de novo
# o que já existe aqui). Apague a pasta se precisar liberar espaço.
CACHE_GOES = __import__("pathlib").Path(__file__).resolve().parents[1] / "dados/goes"

def baixar_goes(data, hora, bandas=("C07", "C13", "C02")):
    """Baixa cenas ABI Full-Disk para uma hora. Retorna dict de xarray.
    Reusa arquivos já baixados em dados_goes/ (cache persistente)."""
    from goes2go import GOES
    out = {}
    for b in bandas:
        # goes2go exige channel como INT (ou lista de ints): "C07" -> [7].
        # (string estoura em df.band.isin() dentro do goes2go)
        g = GOES(satellite=16, product="ABI-L2-CMIPF", channel=[int(b[1:])])
        ds = g.nearesttime(f"{data} {hora}", save_dir=str(CACHE_GOES),
                           overwrite=False)
        out[b] = ds
    return out

# ----------------------------------------------------------------------
# 2) RECORTAR O ALVO (lat/lon -> índices da grade fixa GOES)
# ----------------------------------------------------------------------
def recortar(ds, lat0, lon0, raio_km):
    """Recorta um quadrado ~2*raio em torno do alvo. Usa pyproj p/ geo->scan."""
    import pyproj
    # A projeção GOES está nos atributos goes_imager_projection.
    h = ds.goes_imager_projection.perspective_point_height
    lon_origin = ds.goes_imager_projection.longitude_of_projection_origin
    p = pyproj.Proj(proj="geos", h=h, lon_0=lon_origin, sweep="x")
    x0, y0 = p(lon0, lat0)                       # metros no plano do satélite
    xs = ds.x.values * h                          # rad -> m
    ys = ds.y.values * h
    dr = raio_km * 1000
    ix = np.where((xs > x0 - dr) & (xs < x0 + dr))[0]
    iy = np.where((ys > y0 - dr) & (ys < y0 + dr))[0]
    return ds.isel(x=slice(ix.min(), ix.max()+1), y=slice(iy.min(), iy.max()+1))

# ----------------------------------------------------------------------
# 3) DERIVAR r_e E T, MONTAR A CURVA r_e(T)
# ----------------------------------------------------------------------
def curva_re_T(c07, c13, c02, thr_vis=0.4):
    """Constrói a nuvem de pontos r_e(T) para pixels nublados.
    NOTA: a conversão 3,9um->r_e rigorosa exige remover a parte térmica da
    radiância de 3,9um usando C13 e a geometria solar. Aqui deixamos o
    ESQUELETO com um proxy; troque por retrieval calibrado (ex. método de
    Rosenfeld/CAPPI ou a biblioteca 'satpy' com o modificador de r_e)."""
    # As bandas têm resoluções diferentes (C02=0,5 km; C07/C13=2 km), então
    # os recortes saem com grades distintas. Interpola tudo p/ a grade da C13.
    c07 = c07.interp(x=c13.x, y=c13.y)
    c02 = c02.interp(x=c13.x, y=c13.y)
    T = c13["CMI"].values            # K, temperatura de brilho do topo
    vis = c02["CMI"].values          # reflectância visível (0-1)
    r39 = c07["CMI"].values          # K (brilho 3,9um) — proxy

    # máscara de nuvem (visível alto + topo frio). ATENÇÃO: o método Rosenfeld
    # é DIURNO — o r_e vem da reflectância SOLAR em 3,9um. À noite o visível
    # é ~0 e a máscara zera; caímos numa máscara só-IR e o "r_e" vira o BTD
    # noturno 3,9-10,3um (indicador de fase, mas NÃO é a curva de Rosenfeld).
    global REGIME_ULTIMA_CENA
    if np.nanmax(vis) < 0.15:
        print("  !! Cena NOTURNA (visível ~0): usando máscara só-IR. O eixo")
        print("     r_e vira BTD 3,9-10,3um noturno — para a curva Rosenfeld")
        print("     de verdade, use hora DIURNA (~12-21 UT no RS).")
        nuvem = (T < 273.15) & (T > 180.0)
        REGIME_ULTIMA_CENA = "noturno"
    else:
        nuvem = (vis > thr_vis) & (T < 273.15)
        REGIME_ULTIMA_CENA = "diurno"
        if np.nanmax(vis) < 0.6:
            print("  !! Sol BAIXO (crepúsculo?): 3,9um parcialmente solar —")
            print("     não compare esta curva nem com as diurnas nem com as noturnas.")
            REGIME_ULTIMA_CENA = "crepusculo"
    if nuvem.sum() == 0:
        raise RuntimeError(
            "0 pixels nublados no recorte — cena sem nuvem fria neste "
            f"horário. Estatísticas: topo mais frio={np.nanmin(T)-273.15:.0f}C, "
            f"visível máx={np.nanmax(vis):.2f}, "
            f"pixels com vis>{thr_vis}={(vis > thr_vis).sum()}. "
            "Varra outros horários (--goes-horas no 04) ou reduza thr_vis.")
    # Corta topos < -60C: lá a radiância de 3,9um é tão baixa que o passo
    # digital do ABI vale vários K -> BT(3,9) quantizado -> as "listras
    # diagonais" (retas de inclinação -1) no scatter. Não é física, é o
    # limite do sensor; nem retrieval calibrado resolve abaixo disso.
    nuvem = nuvem & (T > 213.15)
    # PROXY de r_e: menor reflectância residual de 3,9um ~ gotas maiores.
    # >>> SUBSTITUA por retrieval calibrado antes de publicar <<<
    re_proxy = (r39 - T)             # diferença 3,9-10,3um: cresce com r_e
    return T[nuvem] - 273.15, re_proxy[nuvem]   # T em Celsius, re (proxy)

# ----------------------------------------------------------------------
# 4) DIAGNÓSTICO: SLW abaixo de -20C? glaciação abrupta?
# ----------------------------------------------------------------------
def diagnosticar(Tc, re):
    print("\n--- Diagnóstico Rosenfeld ---")
    # binning por temperatura
    bins = np.arange(-60, 5, 5)
    med = [np.nanmedian(re[(Tc >= bins[i]) & (Tc < bins[i+1])]) for i in range(len(bins)-1)]
    for i, m in enumerate(med):
        marca = ""
        if bins[i] <= -20 and np.isfinite(m):
            marca = "  <-- SLW abaixo de -20C? (r_e ainda crescendo = líquido)"
        print(f"  T[{bins[i]:+.0f},{bins[i+1]:+.0f})C : r_e~{m:.2f}{marca}")
    print("Interpretação: se r_e continua ALTO/subindo abaixo de -20C -> SLW "
          "persistente (assinatura do toró). Queda abrupta -> glaciação súbita (SIP).")
    return bins[:-1], med

def plotar(Tc, re, med_bins, saida="rosenfeld_re_T.png", titulo=None):
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(re, Tc, s=2, alpha=0.15, color="steelblue")
    b, m = med_bins
    ax.plot(m, b + 2.5, "r-o", lw=2, label="mediana por faixa de T")
    ax.axhline(-20, color="purple", ls="--", label="-20 C (limiar SLW)")
    ax.invert_yaxis()
    ax.set_xlabel("r_e (proxy — substituir por retrieval calibrado)")
    ax.set_ylabel("Temperatura do topo (C)")
    if titulo is None:
        titulo = f"Rosenfeld r_e(T) — {ALVO['nome']} — {JANELA['data']}"
    ax.set_title(f"{titulo}\nN={len(Tc)} pixels nublados")
    ax.legend(fontsize=8)
    plt.tight_layout(); plt.savefig(saida, dpi=150)
    plt.close(fig)
    print("Figura salva:", saida)

def mapa_topo(c13, saida, titulo="Topo de nuvem (C13)"):
    """Mapa do recorte na banda 10,3um — para IDENTIFICAR a tempestade:
    supercélula mostra núcleo frio compacto (<-55C), topo overshooting e,
    às vezes, assinatura em 'V' a favor do vento. Chuva comum: topos mornos
    e difusos. Use junto com radar/pluviômetro para confirmar."""
    import matplotlib.pyplot as plt
    T = c13["CMI"].values - 273.15
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    # chão/mar (topo "quente") em cinza; só NUVEM (< 5 C) colorida
    ax.imshow(np.ones_like(T), cmap="gray", vmin=0, vmax=1.6)
    Tnuvem = np.ma.masked_where(T > 5, T)
    im = ax.imshow(Tnuvem, cmap="turbo_r", vmin=-75, vmax=5)
    plt.colorbar(im, ax=ax, label="T do topo da nuvem (C)")
    if np.nanmin(T) < -20:
        cs = ax.contour(T, levels=[-55, -35, -20], colors="k", linewidths=0.7)
        ax.clabel(cs, fmt="%.0f", fontsize=7)
    ny, nx = T.shape
    ax.plot(nx / 2, ny / 2, "k+", ms=16, mew=2.5)   # alvo no centro
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{titulo}\ncinza=sem nuvem | + = alvo | contornos -20/-35/-55 C")
    plt.tight_layout(); plt.savefig(saida, dpi=150)
    plt.close(fig)
    print("Figura salva:", saida)

if __name__ == "__main__":
    print(f"Alvo: {ALVO}  Janela: {JANELA}")
    try:
        cenas = baixar_goes(JANELA["data"], JANELA["hora_ini"])
        rec = {b: recortar(cenas[b], ALVO["lat"], ALVO["lon"], ALVO["raio_km"]) for b in cenas}
        Tc, re = curva_re_T(rec["C07"], rec["C13"], rec["C02"])
        mb = diagnosticar(Tc, re)
        plotar(Tc, re, mb)
    except Exception as e:
        print("!! Precisa rodar na sua máquina (internet + goes2go):", e)
        print("   Este é o esqueleto; ajuste ALVO/JANELA e o retrieval de r_e.")
