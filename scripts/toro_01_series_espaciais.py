#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01_series_espaciais.py
======================
TODAS as séries temporais espaciais num script só (substitui os antigos
01_timeline, 09_coluna_jz e 12_graficos_desde_0104, hoje em scripts_antigos/).

Séries: GCR/NMDB (OULU, IRK3, MXCO...), Kp (GFZ), Dst (Kyoto), AE (OMNI),
Ey=-VxBz (OMNI), prótons GOES (evento documentado) e TEC (IONEX do 03).

REGRA DE OURO: CACHE PRIMEIRO. Cada série é lida de dados_nmdb/ ou
dados_geomag/ se existir; só baixa da internet o que faltar — e o que baixar
vira cache. Nada é rebaixado, nada é apagado.

Figuras (resultados/series_espaciais/):
  timeline_gcr.png          GCR OULU + marcos do caso
  gcr_multi_rigidez.png     OULU/IRK3/MXCO + estimativa do FD no corte do RS
  gcr_eficiencia.png        JBGO/OULU/KERG/JUNG1 (revised corr_for_efficiency, 30min) (--figuras bruto)
  tec.png                   anomalia de TEC na caixa AMAS/RS (IONEX em cache)
  coluna_jz.png             Kp + Dst + TEC + GCR
  coluna_jz_expandida.png   Ey+Kp+Dst+AE+prótons+TEC+GCR(corr_for_efficiency); fonte por painel
  coluna_jz_super.png       expandida + ΔH local (SMS/VSS) sob o Dst + múons SMS sob os nêutrons

Uso:
  python 01_series_espaciais.py                        # 01/04-16/05, tudo
  python 01_series_espaciais.py --ini 2024-04-25 --fim 2024-05-16
  python 01_series_espaciais.py --figuras coluna tec   # só algumas
"""

import argparse
import importlib.util
import pathlib

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

AQUI = pathlib.Path(__file__).resolve().parents[1]
D_NMDB = AQUI / "dados/nmdb"
D_GEO = AQUI / "dados/geomag"

def _mod(nome, alias):
    spec = importlib.util.spec_from_file_location(alias, AQUI / nome)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

caso = _mod("toro_00_caso.py", "caso")

MARCOS = list(caso.MARCOS_SOLARES)
SISMOS = list(getattr(caso, "SISMOS_UT", []))
ESTACOES_NMDB = [("OULU", 0.81), ("IRK2", 3.64), ("IRK3", 3.64),
                 ("JUNG", 4.49), ("MXCO", 8.28)]
R_LOCAL_GV = 10.5
SEP_INI, SEP_FIM = "2024-05-10 16:40", "2024-05-15"   # S2 -> fim aprox.
GLE74 = ("2024-05-11 02:45", 238)                      # pico >10 MeV (pfu)

# ======================================================================
# LEITURA DE CACHE (formatos aceitos: "t;v" OU grade de valores por linha)
# ======================================================================
def _ler_arquivo_serie(f, inicio=None, freq=None):
    """Lê um cache de série. Linhas 't;v' são autoexplicativas; grades de
    valores exigem inicio+freq (inferidos do nome quando possível)."""
    ts, vs = [], []
    grade = []
    for l in f.read_text(encoding="utf-8").splitlines():
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        if ";" in l:
            a, b = l.split(";")[:2]
            ts.append(pd.to_datetime(a.strip()))
            vs.append(float(b))
        else:
            grade += [float(x) for x in l.replace(",", " ").split()]
    if ts:
        return pd.DataFrame({"tempo": ts, "v": vs})
    t = pd.date_range(inicio, periods=len(grade), freq=freq)
    return pd.DataFrame({"tempo": t, "v": grade})

def _acha_cache(pasta, prefixo, ini, fim):
    """Procura cache cujo NOME cubra [ini, fim] (convenção *_YYYYMMDD_YYYYMMDD)."""
    i0 = ini.replace("-", "")
    f0 = fim.replace("-", "")
    for f in sorted(pasta.glob(f"{prefixo}_2*.txt")):
        partes = f.stem.split("_")
        dts = [p for p in partes if len(p) == 8 and p.isdigit()]
        if len(dts) == 2 and dts[0] <= i0 and dts[1] >= f0:
            return f, dts[0]
    return None, None

def _recorta(df, ini, fim):
    m = (df.tempo >= pd.to_datetime(ini)) & \
        (df.tempo < pd.to_datetime(fim) + pd.Timedelta(days=1))
    return df[m].reset_index(drop=True)

# ======================================================================
# FONTES (cache -> download -> cache)
# ======================================================================
def nmdb(est, ini, fim, passo_min=60, correcao="pressao"):
    """Série NMDB do nest (ascii). `correcao`:
      'pressao'    -> corrigido de pressão (padrão do projeto; caminho e URL
                      inalterados — os caches h1/h3 já existentes continuam
                      válidos e NÃO são rebaixados);
      'eficiencia' -> 'revised corr_for_efficiency' (pressão + eficiência,
                      tabchoice=revori); o nest JÁ devolve em % de desvio,
                      então NÃO se converte nada — fica como veio;
      'cru'        -> uncorrected (SEM correção barométrica): contagem,
                      convertida a % de desvio.
    CACHE PRIMEIRO — só baixa o que faltar; suporta passo sub-horário (ex. 30)."""
    suf = {"pressao": "", "eficiencia": "_ef", "cru": "_nc"}[correcao]
    if passo_min % 60 == 0:
        res_tag = f"h{passo_min // 60}"
        freq = "h" if passo_min == 60 else f"{passo_min // 60}h"
    else:
        res_tag = f"m{passo_min}"
        freq = f"{passo_min}min"
    tag = res_tag + suf
    f, ini_arq = _acha_cache(D_NMDB, f"{est}_{tag}", ini, fim)
    if f:
        df = _ler_arquivo_serie(f, inicio=pd.to_datetime(ini_arq), freq=freq)
        return _recorta(df, ini, fim)
    # download (NMDB nest, ascii) — na sua máquina
    import requests
    dtypes = {"cru": ["uncorrected", "uncorr"],
              "eficiencia": ["corr_for_efficiency"]}.get(correcao, [None])
    linhas = []
    for dt in dtypes:
        url = ("https://www.nmdb.eu/nest/draw_graph.php?formchk=1"
               f"&stations[]={est}&tresolution={passo_min}&date_choice=bydate"
               f"&start_year={ini[:4]}&start_month={ini[5:7]}"
               f"&start_day={ini[8:10]}&start_hour=0&start_min=0"
               f"&end_year={fim[:4]}&end_month={fim[5:7]}"
               f"&end_day={fim[8:10]}&end_hour=23&end_min=59&output=ascii")
        if correcao == "eficiencia":
            url += "&tabchoice=revori"      # série revisada (revori)
        if dt:
            url += f"&dtype={dt}"
        print(f"  baixando NMDB {est} ({correcao}, {passo_min} min)...")
        txt = requests.get(url, timeout=120).text
        linhas = [l for l in txt.splitlines() if ";" in l and l[:4].isdigit()]
        if linhas:
            break
    if not linhas:
        raise RuntimeError(f"NMDB sem dados p/ {est} ({correcao}) — "
                           "confira nmdb.eu/nest")
    D_NMDB.mkdir(exist_ok=True)
    fc = D_NMDB / f"{est}_{tag}_{ini.replace('-','')}_{fim.replace('-','')}.txt"
    rot = {"pressao": "corr. pressão",
           "eficiencia": "revised corr_for_efficiency",
           "cru": "SEM correções"}[correcao]
    fc.write_text(f"# {est} NMDB ({rot}, {passo_min} min) "
                  "(agradecer www.nmdb.eu e o PI da estação)\n"
                  + "\n".join(linhas) + "\n", encoding="utf-8")
    df = _recorta(_ler_arquivo_serie(fc), ini, fim)
    if correcao == "cru" and df.v.abs().max() > 100:   # só 'cru' vem em contagem
        b = df.loc[df.tempo < df.tempo.min() + pd.Timedelta(days=5),
                   "v"].median()
        df["v"] = 100.0 * (df.v - b) / b      # contagem -> % de desvio
    return df

def kp_gfz(ini, fim):
    f, ini_arq = _acha_cache(D_GEO, "kp", ini, fim)
    if f:
        return _recorta(_ler_arquivo_serie(f, inicio=pd.to_datetime(ini_arq),
                                           freq="3h"), ini, fim)
    import requests
    print("  baixando Kp (GFZ)...")
    j = requests.get("https://kp.gfz-potsdam.de/app/json/?start="
                     f"{ini}T00:00:00Z&end={fim}T23:59:59Z&index=Kp",
                     timeout=60).json()
    df = pd.DataFrame({"tempo": pd.to_datetime(j["datetime"]).tz_localize(None)
                       if hasattr(pd.to_datetime(j["datetime"]), "tz_localize")
                       else pd.to_datetime(j["datetime"]), "v": j["Kp"]})
    D_GEO.mkdir(exist_ok=True)
    fc = D_GEO / f"kp_{ini.replace('-','')}_{fim.replace('-','')}.txt"
    fc.write_text("# Kp GFZ (CC BY 4.0)\n" + "\n".join(
        f"{t:%Y-%m-%d %H:%M};{v}" for t, v in zip(df.tempo, df.v)),
        encoding="utf-8")
    return df

def dst_kyoto(ini, fim):
    """Dst horário: caches mensais dados_geomag/dst_YYYYMM.txt
    (formato: dia + 24 valores). Meses ausentes são baixados do WDC."""
    import re
    out = []
    for mes in pd.period_range(ini, fim, freq="M"):
        f = D_GEO / f"dst_{mes.year}{mes.month:02d}.txt"
        if not f.exists():
            import requests
            print(f"  baixando Dst {mes}...")
            linhas_mes = []
            for base in ("dst_final", "dst_provisional", "dst_realtime"):
                url = (f"https://wdc.kugi.kyoto-u.ac.jp/{base}/"
                       f"{mes.year}{mes.month:02d}/index.html")
                try:
                    txt = requests.get(url, timeout=60).text
                except Exception:
                    continue
                txt = re.sub(r"<[^>]+>", "", txt)
                for l in txt.splitlines():
                    p = l.split()
                    if len(p) == 25 and p[0].isdigit() and 1 <= int(p[0]) <= 31:
                        linhas_mes.append(l.rstrip())
                if linhas_mes:
                    break
            if not linhas_mes:
                print(f"  !! Dst indisponível p/ {mes}")
                continue
            D_GEO.mkdir(exist_ok=True)
            f.write_text(f"# Dst WDC Kyoto {mes} (dia + 24 valores UT, nT)\n"
                         + "\n".join(linhas_mes) + "\n", encoding="utf-8")
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.startswith("#") or not l.strip():
                continue
            p = l.split()
            dia = int(p[0])
            for h, v in enumerate(p[1:25]):
                out.append((pd.Timestamp(mes.year, mes.month, dia, h),
                            float(v)))
    df = pd.DataFrame(out, columns=["tempo", "v"]).sort_values("tempo")
    return _recorta(df, ini, fim)

def omni_var(var, rotulo, ini, fim):
    """Série horária do OMNIWeb (var 35=Ey, 41=AE...). Cache em dados_geomag."""
    pref = {35: "ey_omni", 41: "ae"}.get(var, f"omni{var}")
    f, ini_arq = _acha_cache(D_GEO, pref, ini, fim)
    if f:
        df = _ler_arquivo_serie(f, inicio=pd.to_datetime(ini_arq), freq="h")
        df.loc[df.v > 999, "v"] = np.nan          # fill 999.99/9999
        return _recorta(df, ini, fim)
    import requests
    print(f"  baixando OMNI var {var} ({rotulo})...")
    url = ("https://omniweb.gsfc.nasa.gov/cgi/nx1.cgi?activity=retrieve"
           f"&res=hour&spacecraft=omni2&start_date={ini.replace('-','')}"
           f"&end_date={fim.replace('-','')}&vars={var}")
    txt = requests.get(url, timeout=90).text
    ts, vs = [], []
    for l in txt.splitlines():
        p = l.split()
        if len(p) == 4 and p[0] == ini[:4]:
            t = (pd.Timestamp(int(p[0]), 1, 1)
                 + pd.Timedelta(days=int(p[1]) - 1, hours=int(p[2])))
            ts.append(t)
            vs.append(float(p[3]))
    if not ts:
        raise RuntimeError(f"OMNI var {var} sem dados")
    df = pd.DataFrame({"tempo": ts, "v": vs})
    D_GEO.mkdir(exist_ok=True)
    fc = D_GEO / f"{pref}_{ini.replace('-','')}_{fim.replace('-','')}.txt"
    fc.write_text(f"# OMNI2 var {var} ({rotulo}) — NASA/SPDF OMNIWeb\n"
                  + "\n".join(f"{t:%Y-%m-%d %H:%M};{v}"
                              for t, v in zip(df.tempo, df.v)),
                  encoding="utf-8")
    df.loc[df.v > 999, "v"] = np.nan
    return df

ALVO_BOX = dict(nome="AMAS/RS", lat_min=-32, lat_max=-27,
                lon_min=-56, lon_max=-49)

def _parse_ionex(txt, box):
    """Parser IONEX 1.0: média do TEC na caixa por época (absorvido do 03)."""
    exp = -1.0
    for l in txt.splitlines():
        if "EXPONENT" in l:
            try:
                exp = float(l.split()[0])
            except ValueError:
                pass
        if "END OF HEADER" in l:
            break
    out = []
    for b in txt.split("START OF TEC MAP")[1:]:
        b = b.split("END OF TEC MAP")[0]
        ls = b.splitlines()
        epoca, soma, n, i = None, 0.0, 0, 0
        while i < len(ls):
            l = ls[i]
            if "EPOCH OF CURRENT MAP" in l:
                epoca = pd.Timestamp(*[int(x) for x in l.split()[:6]])
            elif "LAT/LON1/LON2/DLON/H" in l:
                lat = float(l[2:8]); lon1 = float(l[8:14])
                lon2 = float(l[14:20]); dlon = float(l[20:26])
                nlon = int(round((lon2 - lon1) / dlon)) + 1
                vals = []
                while len(vals) < nlon and i + 1 < len(ls):
                    i += 1
                    vl = ls[i]
                    vals += [int(vl[k:k + 5])
                             for k in range(0, len(vl.rstrip()), 5)]
                if box["lat_min"] <= lat <= box["lat_max"]:
                    lons = lon1 + dlon * np.arange(nlon)
                    m = (lons >= box["lon_min"]) & (lons <= box["lon_max"])
                    v = np.array(vals[:nlon], float)[m]
                    v = v[v != 9999]
                    if v.size:
                        soma += (v * 10.0 ** exp).sum()
                        n += v.size
            i += 1
        if epoca is not None and n > 0:
            out.append((epoca, soma / n))
    return out

def ztd_gnss(ini, fim, estacao="POAL"):
    """ZTD GNSS (atraso zenital total) da estação RBMC via produtos
    troposféricos do Nevada Geodetic Laboratory — proxy do PWV (as variações
    dia-a-dia do ZTD são dominadas pelo termo úmido; PWV ~ 0,15 x ZWD).
    Cache: dados_gnss/ (zip anual) + série pronta em dados_geomag/.
    Retorna DataFrame tempo,v = anomalia de ZTD em mm."""
    f, _ = _acha_cache(D_GEO, f"ztd_{estacao}", ini, fim)
    if f:
        return _recorta(_ler_arquivo_serie(f), ini, fim)
    try:
        import io
        import zipfile
        import requests
        pasta = AQUI / "dados/gnss"
        pasta.mkdir(exist_ok=True)
        regs = []
        anos = sorted({pd.to_datetime(ini).year, pd.to_datetime(fim).year})
        for ano in anos:
            fz = pasta / f"{estacao}.{ano}.trop.zip"
            if not fz.exists():
                url = ("https://geodesy.unr.edu/gps_timeseries/trop/"
                       f"{estacao}/{estacao}.{ano}.trop.zip")
                print(f"  baixando ZTD {estacao} {ano} (NGL)...")
                r = requests.get(url, timeout=120)
                if r.status_code != 200 or len(r.content) < 1000:
                    print(f"  !! NGL sem trop p/ {estacao} {ano} ({url})")
                    continue
                fz.write_bytes(r.content)
            with zipfile.ZipFile(fz) as z:
                for nome in z.namelist():
                    for l in io.TextIOWrapper(z.open(nome),
                                              errors="ignore"):
                        p = l.split()
                        if len(p) < 3:
                            continue
                        t = None
                        v = None
                        for x in p:
                            try:
                                fx = float(x)
                            except ValueError:
                                continue
                            # tempo: MJD (~60000) ou ano decimal
                            if t is None and 59000 < fx < 62000:
                                t = pd.Timestamp("1858-11-17") + \
                                    pd.Timedelta(days=fx)
                            elif t is None and ano <= fx < ano + 1:
                                t = pd.Timestamp(ano, 1, 1) + pd.Timedelta(
                                    days=(fx - ano) * 365.25)
                            # ZTD: ~2,0-2,8 m ou 2000-2800 mm
                            if v is None and 1.5 < fx < 3.2:
                                v = fx * 1000.0
                            elif v is None and 1500 < fx < 3200:
                                v = fx
                        if t is not None and v is not None:
                            regs.append((t, v))
        if not regs:
            return None
        df = pd.DataFrame(regs, columns=["tempo", "v"]).sort_values("tempo")
        df = df.groupby(pd.Grouper(key="tempo", freq="1h"),
                        as_index=False).mean()
        df = _recorta(df.dropna(), ini, fim)
        df["v"] = df.v - df.v.mean()          # anomalia em mm
        D_GEO.mkdir(exist_ok=True)
        fc = D_GEO / (f"ztd_{estacao}_{ini.replace('-','')}_"
                      f"{fim.replace('-','')}.txt")
        fc.write_text(f"# ZTD {estacao} (NGL, anomalia em mm) — proxy de PWV\n"
                      + "\n".join(f"{t:%Y-%m-%d %H:%M};{v:.1f}"
                                  for t, v in zip(df.tempo, df.v)),
                      encoding="utf-8")
        return df
    except Exception as e:
        print(f"  !! ZTD {estacao} indisponível:", e)
        return None

def muons_sms(ini, fim, corrigido=True):
    """MÚONS DE SÃO MARTINHO DA SERRA (OES/INPE — GMDN/Shinshu): o detector
    de raios cósmicos DO RS, sob a AMAS — a medida local que substitui a
    extrapolação de rigidez. Baixa o arquivo anual (canal vertical, horário,
    corrigido de pressão) para dados_muons/ e guarda a série pronta.
    CITAÇÃO OBRIGATÓRIA: GMDN collaboration, http://hdl.handle.net/10091/0002001448
    Retorna DataFrame tempo,v em % de desvio vs. os primeiros 5 dias."""
    sub, suf = ("Correct", "CP") if corrigido else ("Uncorrect", "NC")
    pref = "muons_sms" if corrigido else "muons_sms_nc"
    f, _ = _acha_cache(D_GEO, pref, ini, fim)
    if f:
        return _recorta(_ler_arquivo_serie(f), ini, fim)
    try:
        import requests
        pasta = AQUI / "dados/muons"
        pasta.mkdir(exist_ok=True)
        regs = []
        anos = sorted({pd.to_datetime(ini).year, pd.to_datetime(fim).year})
        base = ("http://cosray.shinshu-u.ac.jp/crest/DB/Public/Archives/"
                f"GMDN/{sub}/SaoMartinho/")
        for ano in anos:
            raw = None
            for v in ("v3", "v2", "v1"):
                fr = pasta / f"Sao{ano}_{suf}_{v}.txt"
                if fr.exists():
                    raw = fr
                    break
            if raw is None:
                for v in ("v3", "v2", "v1"):
                    print(f"  tentando múons SMS {suf} {ano} ({v})...")
                    r = requests.get(base + f"Sao{ano}_{suf}_{v}.txt",
                                     timeout=180)
                    if r.status_code == 200 and len(r.text) > 10000:
                        raw = pasta / f"Sao{ano}_{suf}_{v}.txt"
                        raw.write_text(r.text, encoding="utf-8")
                        break
            if raw is None:
                continue
            for l in raw.read_text(encoding="utf-8",
                                   errors="ignore").splitlines():
                p = l.split()
                if len(p) >= 5 and p[0] == str(ano) and p[1].isdigit():
                    try:
                        t = pd.Timestamp(int(p[0]), int(p[1]), int(p[2]),
                                         int(p[3]) % 24)
                    except ValueError:
                        continue
                    val = np.nan
                    for x in p[4:12]:          # 1ª contagem plausível (canal V)
                        try:
                            fx = float(x)
                            if fx > 1000:
                                val = fx
                                break
                        except ValueError:
                            pass
                    if np.isfinite(val):
                        regs.append((t, val))
        if not regs:
            return None
        df = pd.DataFrame(regs, columns=["tempo", "v"]).sort_values("tempo")
        df = _recorta(df, ini, fim)
        b = df.loc[df.tempo < df.tempo.min() + pd.Timedelta(days=5),
                   "v"].median()
        df["v"] = 100.0 * (df.v - b) / b       # % de desvio
        df.loc[df.v.abs() > 25, "v"] = np.nan  # spikes instrumentais
        D_GEO.mkdir(exist_ok=True)
        fc = D_GEO / (f"{pref}_{ini.replace('-','')}_"
                      f"{fim.replace('-','')}.txt")
        fc.write_text(f"# Múons São Martinho da Serra (GMDN, canal vertical, "
                      f"{'corrigido de pressão' if corrigido else 'SEM correções'}),"
                      " % de desvio — citar hdl.handle.net/10091/0002001448\n"
                      + "\n".join(f"{t:%Y-%m-%d %H:%M};{v:.3f}"
                                  for t, v in zip(df.tempo, df.v)),
                      encoding="utf-8")
        return df
    except Exception as e:
        print("  !! múons SMS indisponíveis:", e)
        return None

def _parse_iaga2002(txt):
    """Extrai (tempo, H em nT) de um arquivo IAGA-2002. Usa a coluna H se
    existir; senão H=sqrt(X²+Y²). Trata 99999/88888 como faltante."""
    cols = None
    out = []
    for l in txt.splitlines():
        if l.startswith("DATE"):
            cols = l.split()               # DATE TIME DOY <c1> <c2> <c3> <c4>
            continue
        if not l[:4].isdigit() or cols is None:
            continue
        p = l.split()
        if len(p) < 7:
            continue
        try:
            t = pd.Timestamp(p[0] + " " + p[1])
        except ValueError:
            continue
        comp = {cols[i][-1].upper(): p[i]
                for i in range(3, min(len(cols), len(p)))}

        def val(k):
            try:
                v = float(comp.get(k, "99999"))
            except ValueError:
                return np.nan
            return np.nan if v >= 88888 else v
        H = val("H")
        if not np.isfinite(H):
            X, Y = val("X"), val("Y")
            if np.isfinite(X) and np.isfinite(Y):
                H = (X * X + Y * Y) ** 0.5
        if np.isfinite(H):
            out.append((t, H))
    return out

def _flatline(df):
    """True se a série está travada/morta: poucos pontos, ou a maioria dos
    minutos é idêntica ao minuto anterior (sensor em fill — ex.: SMS emitiu
    valor constante o dia todo; um magnetômetro real sempre tem ruído)."""
    if df is None or len(df) < 10:
        return True
    return (df["v"].diff().abs() < 1e-6).mean() > 0.5

def mag_embrace(ini, fim, est="SMS"):
    """Magnetômetro da rede Embrace MagNet (INPE) — componente horizontal H.
    Baixa os arquivos diários (stnDDmmm.YYm, 1 min) para dados_magnet/ e guarda
    a série pronta de ANOMALIA de H (nT, vs. mediana dos primeiros 5 dias) em
    dados_geomag/. Retorna DataFrame tempo,v (ΔH nT) ou None.
    Fonte: embracedata.inpe.br/magnetometer — citar Embrace/INPE."""
    f, _ = _acha_cache(D_GEO, f"magH_{est}", ini, fim)
    if f:
        df = _recorta(_ler_arquivo_serie(f), ini, fim)
        if _flatline(df):
            print(f"  !! {est}: magnetômetro flatline/sem variação — descartado")
            return None
        return df
    try:
        import requests
        pasta = AQUI / "dados/magnet"
        pasta.mkdir(exist_ok=True)
        MES = ["jan", "feb", "mar", "apr", "may", "jun",
               "jul", "aug", "sep", "oct", "nov", "dec"]
        regs = []
        for dia in pd.date_range(ini, fim, freq="D"):
            nome = (f"{est.lower()}{dia.day:02d}{MES[dia.month - 1]}"
                    f".{dia.year % 100:02d}m")
            fr = pasta / nome
            if not fr.exists():
                url = (f"https://embracedata.inpe.br/magnetometer/{est}/"
                       f"{dia.year}/{nome}")
                try:
                    r = requests.get(url, timeout=60,
                                     headers={"User-Agent": "Mozilla/5.0"})
                    if r.status_code == 200 and len(r.content) > 200:
                        fr.write_bytes(r.content)
                    else:
                        continue
                except Exception:
                    continue
            for l in fr.read_text(errors="ignore").splitlines():
                p = l.split()
                if len(p) < 10 or not p[0].isdigit():
                    continue
                try:
                    t = pd.Timestamp(int(p[2]), int(p[1]), int(p[0]),
                                     int(p[3]), int(p[4]))
                    H = float(p[6])            # col 7 = H (nT)
                except (ValueError, IndexError):
                    continue
                if 5000 < H < 60000:           # descarta sentinelas (99999...)
                    regs.append((t, H))
        if not regs:
            return None
        df = _recorta(pd.DataFrame(regs, columns=["tempo", "v"])
                      .sort_values("tempo"), ini, fim)
        # despike: remove glitches (desvio > 100 nT da mediana móvel de 21 min;
        # a variação real de tempestade é gradual e sobrevive ao filtro).
        h = pd.Series(df.v.values, index=pd.DatetimeIndex(df.tempo))
        rm = h.rolling("21min", center=True, min_periods=5).median()
        df = df.loc[((h - rm).abs() < 100).values].reset_index(drop=True)
        if len(df) < 10:
            return None
        b = df.loc[df.tempo < df.tempo.min() + pd.Timedelta(days=5),
                   "v"].median()
        df["v"] = df.v - b                     # anomalia ΔH (nT)
        if _flatline(df):
            print(f"  !! {est}: magnetômetro flatline/sem variação real "
                  "(sensor travado ou fill) — descartado")
            return None
        D_GEO.mkdir(exist_ok=True)
        fc = D_GEO / f"magH_{est}_{ini.replace('-','')}_{fim.replace('-','')}.txt"
        fc.write_text(f"# ΔH {est} (Embrace MagNet/INPE, nT vs. baseline)\n"
                      + "\n".join(f"{t:%Y-%m-%d %H:%M};{v:.1f}"
                                  for t, v in zip(df.tempo, df.v)),
                      encoding="utf-8")
        return df
    except Exception as e:
        print(f"  !! magnetômetro Embrace {est} indisponível:", e)
        return None

def mag_intermagnet(ini, fim, obs="VSS"):
    """Observatório INTERMAGNET (ex.: VSS Vassouras) — componente H, 1 min.
    Serviço REST do GIN de Edimburgo (IAGA-2002). Baixa por mês para
    dados_magnet/ e guarda a ANOMALIA de H (nT) em dados_geomag/.
    Retorna DataFrame tempo,v (ΔH nT) ou None."""
    f, _ = _acha_cache(D_GEO, f"magH_{obs}", ini, fim)
    if f:
        df = _recorta(_ler_arquivo_serie(f), ini, fim)
        if _flatline(df):
            print(f"  !! {obs}: magnetômetro flatline/sem variação — descartado")
            return None
        return df
    try:
        import requests
        pasta = AQUI / "dados/magnet"
        pasta.mkdir(exist_ok=True)
        regs = []
        for mes in pd.period_range(ini, fim, freq="M"):
            fr = pasta / f"{obs}_{mes.year}{mes.month:02d}_iaga.min"
            if not fr.exists():
                d0 = f"{mes.year}-{mes.month:02d}-01"
                txt = None
                for estado in ("definitive", "quasi-def",
                               "adjusted", "reported"):
                    url = ("https://imag-data.bgs.ac.uk/GIN_V1/GINServices?"
                           "Request=GetData&Format=iaga2002"
                           f"&observatoryIagaCode={obs}&samplesPerDay=Minute"
                           f"&dataStartDate={d0}"
                           f"&dataDuration={mes.days_in_month}"
                           f"&publicationState={estado}")
                    try:
                        r = requests.get(url, timeout=120,
                                         headers={"User-Agent": "Mozilla/5.0"})
                    except Exception as e:
                        print(f"  INTERMAGNET {obs} {mes} ({estado}): erro {e}")
                        continue
                    raw = r.content
                    if raw[:2] == b"\x1f\x8b":          # gzip sem header?
                        import gzip
                        try:
                            raw = gzip.decompress(raw)
                        except Exception:
                            pass
                    cand = raw.decode("latin-1", errors="ignore")
                    print(f"  INTERMAGNET {obs} {mes} ({estado}): "
                          f"HTTP {r.status_code}, {len(r.content)} bytes"
                          + (", OK" if "DATE" in cand else ""))
                    if r.status_code == 200 and "DATE" in cand \
                            and cand.count("\n") > 100:
                        txt = cand
                        break
                if not txt:
                    print(f"  !! INTERMAGNET {obs} sem dado p/ {mes} "
                          "(veja os HTTP acima)")
                    continue
                fr.write_text(txt, encoding="utf-8")
            regs += _parse_iaga2002(fr.read_text(errors="ignore"))
        if not regs:
            return None
        df = _recorta(pd.DataFrame(regs, columns=["tempo", "v"])
                      .sort_values("tempo"), ini, fim)
        b = df.loc[df.tempo < df.tempo.min() + pd.Timedelta(days=5),
                   "v"].median()
        df["v"] = df.v - b
        if _flatline(df):
            print(f"  !! {obs}: magnetômetro flatline/sem variação real "
                  "(fill/fora do ar) — descartado")
            return None
        D_GEO.mkdir(exist_ok=True)
        fc = D_GEO / f"magH_{obs}_{ini.replace('-','')}_{fim.replace('-','')}.txt"
        fc.write_text(f"# ΔH {obs} (INTERMAGNET, nT vs. baseline)\n"
                      + "\n".join(f"{t:%Y-%m-%d %H:%M};{v:.1f}"
                                  for t, v in zip(df.tempo, df.v)),
                      encoding="utf-8")
        return df
    except Exception as e:
        print(f"  !! INTERMAGNET {obs} indisponível:", e)
        return None

def protons_goes(ini, fim):
    """Fluxo integral de prótons >10 MeV do GOES-16 (SGPS L2 avg5m, NCEI),
    reamostrado para 1 h. Baixa os netCDF diários (~600 kB) para
    dados_goesp/ (cache) e guarda a série pronta em dados_geomag/.
    Retorna None se indisponível (a figura usa a banda do evento)."""
    # prefixo NOVO (protons10_goes): ignora o cache antigo 'protons_goes_*'
    # (que era >500 MeV) e força a reconstrução >10 MeV do netCDF — sem apagar.
    f, _ = _acha_cache(D_GEO, "protons10_goes", ini, fim)
    if f:
        return _recorta(_ler_arquivo_serie(f), ini, fim)
    try:
        import re
        import requests
        import xarray as xr
        cache_nc = AQUI / "dados/goesp"
        cache_nc.mkdir(exist_ok=True)
        series = []
        for dia in pd.date_range(ini, fim, freq="D"):
            hits = sorted(cache_nc.glob(f"*d{dia:%Y%m%d}*.nc"))
            if not hits:
                base = ("https://data.ngdc.noaa.gov/platforms/"
                        "solar-space-observing-satellites/goes/goes16/l2/"
                        f"data/sgps-l2-avg5m/{dia.year}/{dia:%m}/")
                nome = f"sci_sgps-l2-avg5m_g16_d{dia:%Y%m%d}_v3-0-2.nc"
                r = requests.get(base + nome, timeout=120)
                if r.status_code != 200:      # versão diferente? lê o índice
                    idx = requests.get(base, timeout=60).text
                    m = re.search(
                        rf"(sci_sgps[\w\-]*d{dia:%Y%m%d}[\w\-\.]*\.nc)", idx)
                    if not m:
                        continue
                    nome = m.group(1)
                    r = requests.get(base + nome, timeout=120)
                    if r.status_code != 200:
                        continue
                (cache_nc / nome).write_bytes(r.content)
                hits = [cache_nc / nome]
                print("  baixado", nome)
            ds = xr.open_dataset(hits[0])
            if "AvgDiffProtonFlux" not in ds or \
                    "DiffProtonLowerEnergy" not in ds:
                print("  !! canais diferenciais não achados em", hits[0].name)
                ds.close()
                return None
            # >10 MeV INTEGRAL reconstruído dos canais DIFERENCIAIS. O produto
            # avg5m só traz AvgIntProtonFlux = >500 MeV (quase zero) — NÃO é o
            # >10 MeV do S-scale. Integral = Σ fluxo_dif(canal) × largura_keV,
            # só a parte acima de 10 MeV; soma canais, máx. entre os 2 sensores.
            # Unid.: p/(cm²·sr·keV·s) × keV = pfu. (Reconstrução SGPS roda ~2x
            # abaixo do >10 MeV operacional do SWPC — diferença de calibração.)
            da = ds["AvgDiffProtonFlux"].transpose(
                "time", "sensor_units", "diff_channels")
            lo = ds["DiffProtonLowerEnergy"].transpose(
                "sensor_units", "diff_channels").values
            up = ds["DiffProtonUpperEnergy"].transpose(
                "sensor_units", "diff_channels").values
            frac = np.clip((up - 10000.0) / (up - lo), 0.0, 1.0)
            w = (up - lo) * frac                         # keV efetivo >10 MeV
            intg = np.nansum(da.values * w[np.newaxis, :, :], axis=2)  # (t,sen)
            intg = np.nanmax(intg, axis=1)               # (t,) pfu >10 MeV
            idx = pd.to_datetime(ds["time"].values)
            if getattr(idx, "tz", None) is not None:
                idx = idx.tz_localize(None)
            series.append(pd.Series(intg, index=idx).resample("1h").max())
            ds.close()
        if not series:
            return None
        s = pd.concat(series).sort_index()
        df = pd.DataFrame({"tempo": s.index, "v": s.values})
        df.loc[df.v <= 0, "v"] = np.nan
        D_GEO.mkdir(exist_ok=True)
        fc = D_GEO / (f"protons10_goes_{ini.replace('-','')}_"
                      f"{fim.replace('-','')}.txt")
        fc.write_text("# GOES-16 SGPS: fluxo integral >10 MeV (pfu), média "
                      "horária — NCEI\n" + "\n".join(
                          f"{t:%Y-%m-%d %H:%M};{v:.4g}"
                          for t, v in zip(df.tempo, df.v)),
                      encoding="utf-8")
        return _recorta(df, ini, fim)
    except Exception as e:
        print("  !! prótons GOES indisponíveis:", e)
        return None

def tec_ionex(ini, fim, box=None):
    """Anomalia de TEC (ciclo diurno removido) da caixa AMAS/RS a partir dos
    IONEX do EMBRACE em dados_tec/ — baixa (e guarda) os dias que faltarem."""
    box = box or ALVO_BOX
    cache = AQUI / "dados/tec"
    cache.mkdir(exist_ok=True)
    linhas = []
    for dia in pd.date_range(ini, fim, freq="D"):
        f = cache / f"INPE{dia.dayofyear:03d}0.{dia.year % 100:02d}I"
        if not f.exists():
            try:
                import requests
                url = (f"https://embracedata.inpe.br/ionex/{dia.year}/"
                       f"{f.name}")
                r = requests.get(url, timeout=120)
                if r.status_code == 200:
                    f.write_bytes(r.content)
                    print("  baixado", f.name)
            except Exception:
                pass
        if f.exists():
            linhas += _parse_ionex(f.read_text(errors="ignore"), box)
    if not linhas:
        return None
    tec = pd.DataFrame(linhas, columns=["tempo", "v"]).sort_values("tempo")
    ref = tec.groupby(tec.tempo.dt.hour)["v"].transform("mean")
    tec["v"] = tec.v - ref
    tec.loc[tec.tempo.diff() > pd.Timedelta("3h"), "v"] = np.nan
    return tec.reset_index(drop=True)

def comparar_tec(ev, ctrls):
    """Evento x controle (absorvido do 03) — só a DIFERENÇA é evidência."""
    print("\n--- TEC: EVENTO vs. CONTROLE (anomalia na caixa) ---")
    print(f"  Evento:   média={ev.v.mean():+.2f}  máx={ev.v.max():+.2f} TECU")
    todos = []
    for c in ctrls:
        if c is not None and len(c):
            todos.append(c.v)
            print(f"  Controle: média={c.v.mean():+.2f}  "
                  f"máx={c.v.max():+.2f} TECU")
    if todos:
        base = pd.concat(todos)
        pct = (base < ev.v.max()).mean() * 100
        print(f"  Pico do evento supera {pct:.0f}% dos valores de controle.")
        print("  >>> Só é EVIDÊNCIA se o evento se destacar CLARAMENTE.")

# ======================================================================
# UTILITÁRIOS DE PLOTAGEM
# ======================================================================
def rebase(df, dias=5):
    b = df.loc[df.tempo < df.tempo.min() + pd.Timedelta(days=dias), "v"].mean()
    df = df.copy()
    df["v"] = df.v - b
    return df

def _prep_ef(df, passo_min=30):
    """A série 'revised corr_for_efficiency' do nest JÁ vem em % de desvio
    (não é contagem). Aqui NÃO se converte nem re-normaliza — só: ordena por
    tempo, remove timestamps duplicados, mascara fills não físicos (|v|>25) e
    reamostra para grade regular, o que INSERE NaN nos buracos e faz a linha
    QUEBRAR em vez de atravessar o gráfico. Retorna uma Series indexada por
    tempo, ou None se não sobrar dado.
    (Substitui a antiga _limpa_gcr, que erradamente tratava o dado como
     contagem: descartava a metade negativa — o Forbush — e explodia a escala.)"""
    s = df.dropna(subset=["v"]).set_index("tempo")["v"].sort_index()
    s = s[~s.index.duplicated(keep="first")]
    s[s.abs() > 25] = np.nan
    if s.notna().sum() < 3:
        return None
    return s.asfreq(f"{passo_min}min")

def marcar(ax, rotular=False):
    for t, lab, cor in MARCOS:
        x = pd.to_datetime(t)
        ax.axvline(x, color=cor, lw=1.4, alpha=0.75)
        if rotular:
            ax.annotate(lab, (x, ax.get_ylim()[1]), rotation=90, va="top",
                        ha="right", fontsize=7, color=cor)
    for t in SISMOS:
        ax.axvline(pd.to_datetime(t), color="saddlebrown", lw=0.9, ls="--",
                   alpha=0.9)
    if rotular and SISMOS:
        ax.annotate("SISMOS 13/05 (04:48-06:03 UT)",
                    (pd.to_datetime(SISMOS[0]), ax.get_ylim()[0]),
                    rotation=90, va="bottom", ha="right", fontsize=7,
                    color="saddlebrown")

# ======================================================================
# COMPATIBILIDADE com o 04 (API do antigo 01_timeline)
# ======================================================================
def baixar_oulu(inicio="2024-05-01", fim="2024-05-15"):
    df = nmdb("OULU", inicio, fim, 60)
    return df.rename(columns={"v": "counts"})

def baixar_nmdb_multi(inicio, fim, estacoes=None):
    estacoes = estacoes or [e for e, _ in ESTACOES_NMDB]
    out = None
    for e in estacoes:
        df = nmdb(e, inicio, fim, 180).rename(columns={"v": e})
        out = df if out is None else out.merge(df, on="tempo", how="outer")
    return out.sort_values("tempo").reset_index(drop=True)

def baseline_pct(df):
    b = df[df.tempo < df.tempo.min() + pd.Timedelta(days=2)].counts.mean()
    df = df.copy()
    df["pct"] = df.counts - b        # séries NMDB nest já vêm em % de desvio
    return df

def plotar(df, marcos, eventos, saida="timeline_gcr.png"):
    fig, ax = plt.subplots(figsize=(14, 6))
    if df is not None:
        ax.plot(df.tempo, df.pct, "k", lw=0.9, label="GCR OULU (% desvio)")
        ax.axhline(0, color="gray", lw=0.5, ls=":")
    for t, lab, cor in marcos:
        x = pd.to_datetime(t)
        ax.axvline(x, color=cor, lw=1.6, alpha=0.8)
        ax.annotate(lab, (x, ax.get_ylim()[1]), rotation=90, va="top",
                    ha="right", fontsize=7.5, color=cor)
    for ev in eventos:
        x = pd.to_datetime(ev[0])
        ax.axvline(x, color="green", lw=2.2, ls="--")
        ax.annotate("EVENTO: " + ev[1], (x, ax.get_ylim()[0]), rotation=90,
                    va="bottom", ha="left", fontsize=8, color="green",
                    weight="bold")
    ax.set_ylabel("Desvio (%)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.legend(loc="lower left", fontsize=8)
    plt.tight_layout()
    plt.savefig(saida, dpi=150)
    plt.close()
    print("Figura salva:", saida)

def fase_relativa(eventos, t_ssc="2024-05-10 17:05", t_min="2024-05-11 00:00"):
    ssc = pd.to_datetime(t_ssc)
    print("\n--- Fase de cada evento em relação ao Forbush ---")
    for ev in eventos:
        x = pd.to_datetime(ev[0])
        if x < ssc:
            fase = f"ANTES do CME ({(ssc - x).total_seconds() / 86400:.1f} d)"
        else:
            fase = f"APÓS o SSC (+{(x - ssc).total_seconds() / 86400:.1f} d)"
        print(f"  {ev[0]}  [{ev[1]}]  -> {fase}")

# ======================================================================
def main():
    ap = argparse.ArgumentParser(description="Séries espaciais unificadas")
    ap.add_argument("--ini", default="2024-04-01")
    ap.add_argument("--fim", default="2024-05-16")
    ap.add_argument("--figuras", nargs="+",
                    default=["timeline", "rigidez", "tec", "coluna",
                             "expandida", "super", "bruto", "pwv"],
                    choices=["timeline", "rigidez", "tec", "coluna",
                             "expandida", "super", "bruto", "pwv"])
    ap.add_argument("--gnss", default="POAL",
                    help="estação RBMC p/ o ZTD/PWV (padrão POAL)")
    ap.add_argument("--proton-max", type=float, default=None,
                    help="teto do eixo-y do painel de prótons (pfu); satura o "
                         "GLE p/ ver o fundo/onset. Ex.: --proton-max 2")
    a = ap.parse_args()
    OUT = AQUI / "resultados" / "series_espaciais"
    OUT.mkdir(parents=True, exist_ok=True)
    ini, fim = a.ini, a.fim

    print(f">> Séries {ini} a {fim} (cache primeiro)")
    oulu = rebase(nmdb("OULU", ini, fim, 60))
    irk3 = nmdb("IRK3", ini, fim, 180)
    irk3.loc[irk3.v < -15, "v"] = np.nan
    irk3.loc[(irk3.tempo < "2024-05-10") & (irk3.v < -5), "v"] = np.nan
    irk3 = rebase(irk3)
    mxco = rebase(nmdb("MXCO", ini, fim, 180))
    kp = kp_gfz(ini, fim)
    dst = dst_kyoto(ini, fim)
    try:
        ey = omni_var(35, "Ey (mV/m)", ini, fim)
        ae = omni_var(41, "AE (nT)", ini, fim)
    except Exception as e:
        print("  !! OMNI indisponível:", e)
        ey = ae = None
    tec = tec_ionex(ini, fim)
    prot = protons_goes(ini, fim)
    mu = muons_sms(ini, fim)
    ztd = ztd_gnss(ini, fim, a.gnss) if "pwv" in a.figuras else None

    # GCR 'revised corr_for_efficiency' (30 min) das estações limpas — usado
    # na figura 'bruto' E no painel de GCR da coluna expandida (ef_plot).
    EST_EF = [("JBGO", 0.30, 29, "#d62728"),      # vermelho
              ("OULU", 0.81, 15, "#1f77b4"),      # azul
              ("KERG", 1.14, 33, "#2ca02c"),      # verde
              ("JUNG1", 4.49, 3475, "#9467bd")]   # roxo
    ef_plot = []
    if any(x in a.figuras for x in ("bruto", "expandida", "super")):
        for est, R, alt, cor in EST_EF:
            try:
                s = _prep_ef(nmdb(est, ini, fim, 30, correcao="eficiencia"))
            except Exception as e:
                print(f"  !! {est} (eficiência) indisponível:", e)
                continue
            if s is not None and s.notna().sum() >= 10:
                ef_plot.append((est, R, alt, cor, s))

    # Magnetômetros regionais (ΔH), só na figura 'super': testa estações
    # Embrace de latitude média perto do evento + VSS (INTERMAGNET). A guarda
    # _flatline descarta as mortas. Estado abr–mai/2024 (verificado): MED
    # (Medianeira/PR, a mais próxima) é a única viva na janela — pega o toró,
    # falta o pico do Gannon; SMS travado; VSS fora do ar; TCM sem abr–mai.
    magH = []
    if "super" in a.figuras:
        for code, lab, cor in (("MED", "Medianeira/PR (25°S)", "tab:cyan"),
                               ("SMS", "São Martinho/RS (29°S)", "seagreen")):
            d = mag_embrace(ini, fim, code)
            if d is not None and len(d):
                magH.append((lab, d, cor))
        vss = mag_intermagnet(ini, fim, "VSS")
        if vss is not None and len(vss):
            magH.append(("Vassouras/RJ (22°S)", vss, "navy"))

    if mu is not None:
        jan = (mu.tempo >= "2024-05-10 17:00") & \
              (mu.tempo <= "2024-05-12 00:00")
        if jan.any() and np.isfinite(mu.loc[jan, "v"].min()):
            print(f"[FD] Múons SMS (medida LOCAL do RS): "
                  f"{-mu.loc[jan, 'v'].min():.1f}%")

    if "timeline" in a.figuras:
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(oulu.tempo, oulu.v, "k", lw=0.9,
                label="GCR OULU (% vs. início)")
        ax.axhline(0, color="gray", lw=0.5, ls=":")
        marcar(ax, rotular=True)
        ax.set_ylabel("Desvio (%)")
        ax.set_title(f"GCR e marcos do caso — {ini} a {fim}")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        ax.legend(loc="lower left", fontsize=8)
        plt.tight_layout()
        plt.savefig(OUT / "timeline_gcr.png", dpi=150)
        plt.close()
        i = oulu.v.idxmin()
        print(f"[GCR] mínimo OULU {oulu.v[i]:.1f}% em {oulu.tempo[i]}")

    if "rigidez" in a.figuras:
        series = [("OULU", 0.81, oulu, "k"), ("IRK3", 3.64, irk3, "tab:blue"),
                  ("MXCO", 8.28, mxco, "tab:red")]
        fig, ax = plt.subplots(figsize=(14, 5))
        Rs, As = [], []
        for nome, R, df, cor in series:
            ax.plot(df.tempo, df.v, lw=1, color=cor, label=f"{nome} ({R} GV)")
            jan = (df.tempo >= "2024-05-10 17:00") & \
                  (df.tempo <= "2024-05-12 00:00")
            if jan.any():
                amp = -df.loc[jan, "v"].min()
                if np.isfinite(amp) and amp > 0:
                    Rs.append(R)
                    As.append(amp)
                    print(f"[FD] {nome}: {amp:.1f}%")
        titulo = "FD por corte de rigidez"
        if len(Rs) >= 2:
            g, ln = np.polyfit(np.log(Rs), np.log(As), 1)
            fd_rs = float(np.exp(ln) * R_LOCAL_GV ** g)
            titulo += f" — estimado ~{fd_rs:.1f}% no corte do RS (~10.5 GV)"
            print(f"[FD] A~R^{g:.2f} -> ~{fd_rs:.1f}% no RS")
        if mu is not None:
            ax.plot(mu.tempo, mu.v, color="darkgreen", lw=1.4,
                    label="Múons São Martinho/RS (GMDN) — MEDIDA LOCAL")
        ax.axhline(0, color="gray", lw=0.5, ls=":")
        marcar(ax)
        ax.set_ylabel("Desvio (%)")
        ax.set_title(titulo)
        ax.legend(fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        plt.tight_layout()
        plt.savefig(OUT / "gcr_multi_rigidez.png", dpi=150)
        plt.close()

    if "tec" in a.figuras and tec is not None:
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(tec.tempo, tec.v, color="darkred", lw=1.0,
                label="Anomalia TEC — caixa AMAS/RS (EMBRACE)")
        ax.axhline(0, color="gray", ls=":", lw=0.5)
        ax.set_xlim(pd.to_datetime(ini), pd.to_datetime(fim))
        marcar(ax)
        ax.set_ylabel("TECU")
        ax.set_title(f"Anomalia de TEC — {ini} a {fim} (lacunas = sem IONEX)")
        ax.legend(fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        plt.tight_layout()
        plt.savefig(OUT / "tec.png", dpi=150)
        plt.close()
        ev = _recorta(tec, "2024-05-08", "2024-05-14")
        ct = _recorta(tec, "2024-04-10", "2024-04-16")
        if len(ev) and len(ct):
            comparar_tec(ev, [ct])
        tec.to_csv(OUT / "anomalia_tec.csv", index=False)

    def coluna(camadas, arquivo, titulo):
        fig, axs = plt.subplots(len(camadas), 1,
                                figsize=(14, 2.2 * len(camadas)), sharex=True)
        axs = np.atleast_1d(axs)
        for ax, camada in zip(axs, camadas):
            rot, df, cor, tipo = camada[:4]
            fonte = camada[4] if len(camada) > 4 else None
            if tipo == "bar":
                ax.bar(df.tempo, df.v, width=0.11, color=cor, alpha=0.8)
            elif tipo == "gcref":
                # painel de GCR = 4 estações de eficiência (JÁ em %), suavizadas;
                # cada curva rotulada com onde foi medida (estação, rigidez, alt).
                if df:
                    for est_e, R_e, alt_e, cor_e, s_e in df:
                        su = s_e.rolling("3h", center=True,
                                         min_periods=5).median()
                        ax.plot(su.index, su.values, color=cor_e, lw=1.0,
                                label=f"{est_e} ({R_e} GV, {alt_e} m)")
                    ax.axhline(0, color="gray", lw=0.4, ls=":")
                    ax.legend(fontsize=5.5, ncol=2, loc="lower left")
            elif tipo == "multi":
                # df = lista de (rótulo, DataFrame tempo/v, cor); reamostra por
                # hora p/ QUEBRAR a linha nos buracos (SMS tem dias faltando).
                if df:
                    for lab, dd, cc in df:
                        if dd is not None and len(dd):
                            se = dd.set_index("tempo")["v"].sort_index()
                            se = se[~se.index.duplicated()].resample("1h").mean()
                            ax.plot(se.index, se.values, color=cc, lw=1.0,
                                    label=lab)
                    ax.axhline(0, color="gray", lw=0.4, ls=":")
                    ax.legend(fontsize=6, loc="lower left")
            elif tipo == "sep":
                ax.axvspan(pd.to_datetime(SEP_INI), pd.to_datetime(SEP_FIM),
                           color=cor, alpha=0.25, label="evento S2 (>10 pfu)")
                ax.axvline(pd.to_datetime(GLE74[0]), color=cor, lw=1.6)
                if prot is not None and prot.v.notna().any():
                    ax.plot(prot.tempo, prot.v, color="k", lw=1.0,
                            label="GOES-16 SGPS >10 MeV (pfu, 1h)")
                    vmax = float(np.nanmax(prot.v))
                    # teto: fixo (--proton-max, satura o GLE p/ ver o fundo) ou
                    # automático (mostra o pico inteiro).
                    teto = a.proton_max if a.proton_max else max(vmax * 1.1, 12)
                    if teto >= 10:
                        ax.axhline(10, color="r", ls=":", lw=0.8)  # limiar S1
                    ax.set_ylim(0, teto)
                    ax.annotate(f"GLE74 pico ~{vmax:.0f} pfu"
                                + (" (satura)" if vmax > teto else
                                   f" (SWPC {GLE74[1]})"),
                                (pd.to_datetime(GLE74[0]), teto * 0.8),
                                fontsize=7, color=cor)
                else:
                    ax.scatter([pd.to_datetime(GLE74[0])], [GLE74[1]],
                               color="k", zorder=5)
                    ax.annotate(f"GLE74 — pico {GLE74[1]} pfu (02:45 UT "
                                "11/05); série contínua: rode na sua máquina "
                                "(SWPC/DPD)",
                                (pd.to_datetime(GLE74[0]), GLE74[1] * 0.4),
                                fontsize=7)
                    ax.set_yscale("log")
                    ax.set_ylim(1, 1000)
                ax.legend(loc="upper left", fontsize=7)
            elif df is not None:
                ax.plot(df.tempo, df.v, color=cor, lw=0.9)
                ax.axhline(0, color="gray", lw=0.4, ls=":")
                if tipo == "l2":
                    ax.plot(irk3.tempo, irk3.v, color="tab:blue", lw=0.7,
                            alpha=0.7)
                    if mu is not None:
                        ax.plot(mu.tempo, mu.v, color="darkgreen", lw=1.1)
            ax.set_ylabel(rot, fontsize=7.5)
            if fonte:                                 # fonte da medida (inglês)
                ax.text(0.995, 0.04, fonte, transform=ax.transAxes,
                        fontsize=6, ha="right", va="bottom", color="0.35",
                        bbox=dict(boxstyle="round,pad=0.2", fc="white",
                                  ec="0.8", alpha=0.7))
            marcar(ax)
        for t, lab, c in MARCOS:
            axs[0].annotate(lab, (pd.to_datetime(t), axs[0].get_ylim()[1]),
                            rotation=90, fontsize=7, color=c, va="top",
                            ha="right")
        axs[-1].set_xlim(pd.to_datetime(ini), pd.to_datetime(fim))
        axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        axs[0].set_title(titulo)
        plt.tight_layout()
        plt.savefig(OUT / arquivo, dpi=150)
        plt.close()
        print("Figura salva:", OUT / arquivo)

    if "bruto" in a.figuras:
        # Estações limpas (IRK3/MXCO estavam com problemas): JBGO/OULU/KERG e
        # JUNG1 (alto dos Alpes, 3475 m). 'revised corr_for_efficiency' do NMDB
        # nest a 30 min, JÁ em % — só suavizado (mediana 3 h). Séries em ef_plot.
        fig, ax = plt.subplots(figsize=(15, 6.5))
        for est, R, alt, cor, s in ef_plot:
            suave = s.rolling("3h", center=True, min_periods=5).median()
            ax.plot(s.index, s.values, color=cor, lw=0.4, alpha=0.15)   # cru tênue
            ax.plot(suave.index, suave.values, color=cor, lw=1.7,
                    label=f"{est} (R={R} GV, alt {alt} m)")             # suavizado 3h
        n_ok = len(ef_plot)
        ax.axhline(0, color="gray", lw=0.5, ls=":")
        marcar(ax, rotular=False)
        ax.set_ylabel("Desvio (%)")
        ax.grid(axis="y", color="0.85", lw=0.6)    # escala automática (min–máx)
        ax.set_title("GCR revised corr_for_efficiency (30 min, suavizado 3 h) — "
                     f"JBGO/OULU/KERG/JUNG1 — {ini} a {fim}")
        ax.set_xlim(pd.to_datetime(ini), pd.to_datetime(fim))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        ax.legend(loc="lower left", fontsize=9, ncol=2)
        plt.tight_layout()
        plt.savefig(OUT / "gcr_eficiencia.png", dpi=150)
        plt.close()
        print(f"Figura salva: {OUT / 'gcr_eficiencia.png'} ({n_ok} estações)")

    if "pwv" in a.figuras and ztd is not None:
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(ztd.tempo, ztd.v, color="teal", lw=1.0,
                label=f"Anomalia de ZTD GNSS {a.gnss} (mm) — proxy de PWV")
        ax.axhline(0, color="gray", ls=":", lw=0.5)
        marcar(ax)
        ax.set_ylabel("ZTD (mm)")
        ax.set_title(f"GNSS troposférico — {a.gnss} — {ini} a {fim} "
                     "(ZTD sobe = coluna mais úmida)")
        ax.legend(fontsize=8)
        ax.set_xlim(pd.to_datetime(ini), pd.to_datetime(fim))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        plt.tight_layout()
        plt.savefig(OUT / "gnss_ztd_pwv.png", dpi=150)
        plt.close()
        print("Figura salva:", OUT / "gnss_ztd_pwv.png")

    if "coluna" in a.figuras:
        coluna([("Kp", kp, "tab:red", "bar", "GFZ Potsdam"),
                ("Dst (nT)", dst, "tab:purple", "l", "WDC Kyoto"),
                ("TEC (TECU)", tec, "tab:orange", "l", "IONEX EMBRACE/INPE"),
                ("GCR %: cinza=MXCO, azul=IRK3", mxco, "tab:gray", "l2",
                 "NMDB NEST (MXCO, IRK3)")],
               "coluna_jz.png", f"A coluna do Jz — {ini} a {fim}")

    if "expandida" in a.figuras:
        camadas = [("Ey (mV/m)", ey, "tab:green", "l", "OMNI (NASA/SPDF)"),
                   ("Kp", kp, "tab:red", "bar", "GFZ Potsdam"),
                   ("Dst (nT)", dst, "tab:purple", "l", "WDC Kyoto"),
                   ("AE (nT)", ae, "tab:brown", "l", "OMNI (NASA/SPDF)"),
                   ("Prótons >10 MeV", None, "tab:olive", "sep",
                    "GOES-16 SGPS (NOAA/NCEI)"),
                   ("TEC (TECU)", tec, "tab:orange", "l", "IONEX EMBRACE/INPE")]
        if ztd is not None:
            camadas.append((f"ZTD {a.gnss} (mm)\nproxy de PWV", ztd,
                            "teal", "l", f"GNSS {a.gnss} (NGL)"))
        camadas.append(("GCR (%)\ncorr_for_efficiency", ef_plot, None, "gcref",
                        "NMDB NEST — JBGO/OULU/KERG/JUNG1"))
        coluna(camadas, "coluna_jz_expandida.png",
               f"A coluna do Jz EXPANDIDA — {ini} a {fim}")

    if "super" in a.figuras:
        # Coluna SUPER: tudo da expandida + o monitor de MÚONS de São Martinho
        # da Serra (GMDN/OES-INPE) logo ABAIXO do painel de nêutrons — a medida
        # LOCAL de raio cósmico do RS, sob a AMAS. Estrutura-base p/ variações.
        camadas = [("Ey (mV/m)", ey, "tab:green", "l", "OMNI (NASA/SPDF)"),
                   ("Kp", kp, "tab:red", "bar", "GFZ Potsdam"),
                   ("Dst (nT)", dst, "tab:purple", "l", "WDC Kyoto")]
        if magH:                                    # só se houver mag. VÁLIDO
            camadas.append(("ΔH local (nT)", magH, None, "multi",
                            "Embrace MagNet/INPE · INTERMAGNET"))
        else:
            print("  (sem magnetômetro válido no período — painel ΔH omitido)")
        camadas += [("AE (nT)", ae, "tab:brown", "l", "OMNI (NASA/SPDF)"),
                    ("Prótons >10 MeV", None, "tab:olive", "sep",
                     "GOES-16 SGPS (NOAA/NCEI)"),
                    ("TEC (TECU)", tec, "tab:orange", "l", "IONEX EMBRACE/INPE")]
        if ztd is not None:
            camadas.append((f"ZTD {a.gnss} (mm)\nproxy de PWV", ztd,
                            "teal", "l", f"GNSS {a.gnss} (NGL)"))
        camadas.append(("GCR (%)\ncorr_for_efficiency", ef_plot, None, "gcref",
                        "NMDB NEST — JBGO/OULU/KERG/JUNG1"))     # nêutrons
        camadas.append(("Múons SMS (%)", mu, "darkgreen", "l",
                        "GMDN — São Martinho da Serra/RS (OES/INPE)"))  # logo abaixo
        coluna(camadas, "coluna_jz_super.png",
               f"A coluna do Jz SUPER — {ini} a {fim}")

    print(f"\nSaídas em {OUT}")

if __name__ == "__main__":
    main()
