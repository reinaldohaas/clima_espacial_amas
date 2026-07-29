#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
16_era5_serie_completa.py
=========================
JOB PARA O CLUSTER (nao e script de inspecao). Monta UM arquivo unico de ERA5 em
niveis de pressao para o evento inteiro, 27/04 a 15/05/2024, com niveis finos.

O QUE ELE PRODUZ, nesta ordem:
  1. imprime o PLANO (dias, niveis, variaveis, caixa, numero de requisicoes ao CDS
     e o tamanho estimado do arquivo final) e PARA, se voce nao passar --executar;
  2. baixa UM ARQUIVO POR DIA em dados/era5/serie/ — se o dia ja existe e abre sem
     erro, PULA. E assim que ele "completa a serie": rodar de novo so busca o que
     falta, e uma interrupcao nao perde o que ja veio;
  3. concatena os dias num unico .nc, ordenado no tempo, sem duplicatas;
  4. RELATA os buracos que sobraram no eixo de tempo, dia por dia.

Uso:
    python scripts/16_era5_serie_completa.py                      (so o plano)
    python scripts/16_era5_serie_completa.py --executar           (baixa e concatena)
    python scripts/16_era5_serie_completa.py --executar --passo 3 (3-horario)
    python scripts/16_era5_serie_completa.py --so-concatenar      (usa o que ja baixou)

Pre-requisitos: conta no CDS e ~/.cdsapirc apontando para
    url: https://cds.climate.copernicus.eu/api
Rode a partir da RAIZ do projeto.
"""
import argparse, os, sys
import numpy as np
import pandas as pd

DIA0, DIA1 = "2024-04-27", "2024-05-15"

# Niveis finos: 25 hPa de 1000 a 750 (onde vive o dipolo diabatico de baixos niveis)
# e 25 hPa ate 250. O ERA5 nao tem todos os multiplos de 25; usa-se a grade nativa.
NIVEIS_FINO = [1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750,
               700, 650, 600, 550, 500, 450, 400, 350, 300, 250]
NIVEIS_PADRAO = [925, 850, 700, 600, 500, 400, 300]

VARS = ["potential_vorticity", "temperature", "u_component_of_wind",
        "v_component_of_wind", "vertical_velocity", "specific_humidity",
        "geopotential", "specific_cloud_liquid_water_content",
        "specific_cloud_ice_water_content"]

# caixa 'sul' do nb04, com folga: N, W, S, E
CAIXA = [-18.0, -68.0, -40.0, -42.0]


def plano(a, dias, niveis, horas):
    nlat = int(abs(CAIXA[0] - CAIXA[2]) / 0.25) + 1
    nlon = int(abs(CAIXA[3] - CAIXA[1]) / 0.25) + 1
    ntempo = len(dias) * len(horas)
    valores = ntempo * len(niveis) * nlat * nlon * len(VARS)
    print("=" * 74)
    print("PLANO")
    print("=" * 74)
    print("periodo      : %s a %s  (%d dias)" % (dias[0], dias[-1], len(dias)))
    print("passo        : %d h  ->  %d tempos no total" % (a.passo, ntempo))
    print("niveis       : %d  %s" % (len(niveis), niveis))
    print("variaveis    : %d  %s" % (len(VARS), ", ".join(v[:14] for v in VARS)))
    print("caixa        : lat %.1f a %.1f, lon %.1f a %.1f  ->  %d x %d pontos"
          % (CAIXA[2], CAIXA[0], CAIXA[1], CAIXA[3], nlat, nlon))
    print("requisicoes  : %d (uma por dia; o CDS enfileira cada uma)" % len(dias))
    print("tamanho est. : %.2f GB descomprimido, ~%.2f GB em disco (float32 + zlib)"
          % (valores * 4 / 1e9, valores * 4 / 1e9 * 0.45))
    print("saida por dia: %s/era5_pl_<AAAA-MM-DD>.nc" % a.diario)
    print("saida final  : %s" % a.saida)
    print("=" * 74)


def baixa_dia(dia, niveis, horas, destino):
    import cdsapi
    c = cdsapi.Client()
    d = pd.Timestamp(dia)
    c.retrieve("reanalysis-era5-pressure-levels", {
        "product_type": ["reanalysis"],
        "variable": VARS,
        "pressure_level": [str(n) for n in niveis],
        "year": ["%04d" % d.year], "month": ["%02d" % d.month], "day": ["%02d" % d.day],
        "time": ["%02d:00" % h for h in horas],
        "area": CAIXA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }, destino)


def abre(p):
    import xarray as xr, zipfile
    if zipfile.is_zipfile(p):
        d = p + "_x"
        os.makedirs(d, exist_ok=True)
        with zipfile.ZipFile(p) as z:
            ncs = [n for n in z.namelist() if n.endswith(".nc")]
            for n in ncs:
                alvo = os.path.join(d, n)
                if not os.path.exists(alvo) or os.path.getsize(alvo) != z.getinfo(n).file_size:
                    z.extract(n, d)
        cs = [os.path.join(d, n) for n in ncs]
        if len(cs) == 1:
            return xr.open_dataset(cs[0])
        try:
            return xr.open_mfdataset(cs)
        except ImportError:
            return xr.merge([xr.open_dataset(c) for c in cs], compat="override")
    return xr.open_dataset(p)


def nome_tempo(ds):
    for c in ("valid_time", "time"):
        if c in ds.dims:
            return c
    raise SystemExit("ERRO: sem dimensao de tempo em %s" % list(ds.dims))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ini", default=DIA0)
    ap.add_argument("--fim", default=DIA1)
    ap.add_argument("--passo", type=int, default=6, help="passo em horas (1, 3 ou 6)")
    ap.add_argument("--niveis", choices=["fino", "padrao"], default="fino")
    ap.add_argument("--diario", default="dados/era5/serie")
    ap.add_argument("--saida", default="dados/era5/era5_pl_evento_27abr-15mai.nc")
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--so-concatenar", action="store_true")
    a = ap.parse_args()

    dias = [d.strftime("%Y-%m-%d") for d in pd.date_range(a.ini, a.fim, freq="D")]
    niveis = NIVEIS_FINO if a.niveis == "fino" else NIVEIS_PADRAO
    horas = list(range(0, 24, a.passo))
    plano(a, dias, niveis, horas)

    if not (a.executar or a.so_concatenar):
        print("\nPLANO APENAS. Rode com --executar para baixar, ou --so-concatenar "
              "para juntar o que ja esta em disco.")
        return

    os.makedirs(a.diario, exist_ok=True)
    prontos, faltando = [], []
    for dia in dias:
        p = os.path.join(a.diario, "era5_pl_%s.nc" % dia)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            try:
                ds = abre(p); ds.close(); prontos.append((dia, p)); continue
            except Exception as e:
                print("  %s existe mas nao abre (%s) — vai rebaixar" % (dia, str(e)[:40]))
        faltando.append((dia, p))

    print("\njá em disco: %d dia(s) | a baixar: %d dia(s)" % (len(prontos), len(faltando)))
    if faltando and not a.executar:
        print("faltam dias e voce passou --so-concatenar: vou concatenar so o que existe.")

    if a.executar:
        for k, (dia, p) in enumerate(faltando, 1):
            print("[%d/%d] baixando %s ..." % (k, len(faltando), dia), flush=True)
            tmp = p + ".parcial"
            try:
                baixa_dia(dia, niveis, horas, tmp)
                os.replace(tmp, p)
                prontos.append((dia, p))
                print("      ok  %.1f MB" % (os.path.getsize(p) / 1e6))
            except Exception as e:
                print("      FALHOU: %s" % str(e)[:140])
                if os.path.exists(tmp):
                    os.remove(tmp)

    if not prontos:
        sys.exit("nada em disco para concatenar.")

    import xarray as xr
    prontos.sort()
    print("\nconcatenando %d dia(s) ..." % len(prontos))
    dss = [abre(p) for _, p in prontos]
    td = nome_tempo(dss[0])
    out = xr.concat(dss, dim=td, coords="minimal", compat="override").sortby(td)
    t = pd.to_datetime(out[td].values)
    dup = int(pd.Series(t).duplicated().sum())
    if dup:
        out = out.isel({td: np.where(~pd.Series(t).duplicated().values)[0]})
        t = pd.to_datetime(out[td].values)
        print("  %d tempos duplicados removidos" % dup)

    print("\n=== EIXO DE TEMPO ===")
    print("%d tempos, %s -> %s" % (len(t), t.min(), t.max()))
    esperado = pd.date_range(a.ini + " 00:00", a.fim + " %02d:00" % horas[-1],
                             freq="%dh" % a.passo)
    ausentes = sorted(set(esperado) - set(t))
    if ausentes:
        por_dia = {}
        for x in ausentes:
            por_dia.setdefault(x.strftime("%Y-%m-%d"), 0)
            por_dia[x.strftime("%Y-%m-%d")] += 1
        print("ATENCAO: %d tempo(s) ausente(s), em %d dia(s):" % (len(ausentes), len(por_dia)))
        for dia in sorted(por_dia):
            print("   %s  faltam %d de %d" % (dia, por_dia[dia], len(horas)))
    else:
        print("serie COMPLETA: nenhum tempo ausente no periodo pedido")

    enc = {}
    for v in out.data_vars:
        out[v].encoding = {}
        enc[v] = {"zlib": True, "complevel": 4}
    os.makedirs(os.path.dirname(a.saida) or ".", exist_ok=True)
    out.to_netcdf(a.saida, encoding=enc)
    for ds in dss:
        ds.close()
    print("\n=== SAIDA ===")
    print("%s  (%.2f GB)" % (a.saida, os.path.getsize(a.saida) / 1e9))
    print("niveis: %s" % [int(x) for x in np.atleast_1d(
        out[[c for c in ('pressure_level', 'level') if c in out.dims][0]].values)])


if __name__ == "__main__":
    main()
