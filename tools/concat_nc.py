# -*- coding: utf-8 -*-
"""Concatena varios .nc no tempo (substituto do ncrcat, so com xarray).

Uso:
    python concat_nc.py "era5_pv_*.nc" era5_pv_concat.nc

O que faz, nesta ordem:
  1. lista os arquivos que casam com o padrao e imprime, de cada um, quantos
     tempos tem, o intervalo coberto e as variaveis;
  2. confere se todos tem as MESMAS variaveis e os MESMOS niveis (se divergir,
     para e diz qual arquivo destoa, em vez de concatenar lixo silenciosamente);
  3. concatena na dimensao de tempo (valid_time ou time), ordena e remove
     tempos duplicados;
  4. RELATA os buracos no eixo de tempo (intervalos maiores que o passo tipico);
  5. grava a saida com compressao zlib.
"""
import glob, os, sys
import numpy as np, pandas as pd, xarray as xr

PADRAO = sys.argv[1] if len(sys.argv) > 1 else "era5_pv_*.nc"
SAIDA = sys.argv[2] if len(sys.argv) > 2 else "concat.nc"


def nome_tempo(ds):
    for c in ("valid_time", "time"):
        if c in ds.dims:
            return c
    raise SystemExit("ERRO: nao achei dimensao de tempo (valid_time/time) em %s" % list(ds.dims))


def nome_nivel(ds):
    for c in ("pressure_level", "level", "lev", "isobaricInhPa", "plev"):
        if c in ds.dims:
            return c
    return None


arqs = sorted(glob.glob(PADRAO))
if not arqs:
    raise SystemExit("ERRO: nenhum arquivo casa com %r" % PADRAO)

print("=== ENTRADA (%d arquivos) ===" % len(arqs))
dss, assinaturas = [], []
for a in arqs:
    ds = xr.open_dataset(a)
    td = nome_tempo(ds)
    t = pd.to_datetime(ds[td].values)
    ln = nome_nivel(ds)
    niveis = tuple(np.atleast_1d(ds[ln].values).tolist()) if ln else ()
    variaveis = tuple(sorted(ds.data_vars))
    print("%-34s %3d tempos  %s -> %s  vars=%s" % (
        os.path.basename(a), len(t), t.min(), t.max(), ",".join(variaveis)))
    assinaturas.append((variaveis, niveis, a))
    dss.append(ds)

ref = assinaturas[0]
for vs, nv, a in assinaturas[1:]:
    if vs != ref[0]:
        raise SystemExit("ERRO: %s tem variaveis %s, diferente de %s em %s" % (a, vs, ref[0], ref[2]))
    if nv != ref[1]:
        raise SystemExit("ERRO: %s tem niveis %s, diferente de %s em %s" % (a, nv, ref[1], ref[2]))
if ref[1]:
    print("niveis (iguais em todos): %s" % (list(ref[1]),))

td = nome_tempo(dss[0])
out = xr.concat(dss, dim=td, coords="minimal", compat="override")
out = out.sortby(td)

t = pd.to_datetime(out[td].values)
dup = int(pd.Series(t).duplicated().sum())
if dup:
    keep = ~pd.Series(t).duplicated().values
    out = out.isel({td: np.where(keep)[0]})
    t = pd.to_datetime(out[td].values)
    print("AVISO: %d tempos duplicados removidos" % dup)

print("=== EIXO DE TEMPO ===")
print("%d tempos, %s -> %s" % (len(t), t.min(), t.max()))
if len(t) > 2:
    d = pd.Series(t).diff().dropna()
    passo = d.mode().iloc[0]
    print("passo tipico: %s" % passo)
    buracos = [(t[i], t[i + 1], d.iloc[i]) for i in range(len(d)) if d.iloc[i] > passo]
    if buracos:
        print("ATENCAO: %d buraco(s) no eixo de tempo:" % len(buracos))
        for a0, a1, dt in buracos:
            print("   %s  ate  %s   (%s sem dado)" % (a0, a1, dt))
    else:
        print("sem buracos: eixo continuo")

enc = {}
for v in out.data_vars:
    out[v].encoding = {}
    enc[v] = {"zlib": True, "complevel": 4}
out.to_netcdf(SAIDA, encoding=enc)
for ds in dss:
    ds.close()
print("=== SAIDA ===")
print("%s  (%.1f MB)" % (SAIDA, os.path.getsize(SAIDA) / 1e6))
