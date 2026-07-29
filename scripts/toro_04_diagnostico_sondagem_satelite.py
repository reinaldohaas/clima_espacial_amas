#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04_diagnostico_sondagem_satelite.py
===================================
DIAGNÓSTICO COMBINADO: radiossondagem (skew-T + índices) e satélite
(Rosenfeld r_e(T), reusando o 02) para um caso qualquer.

CASO DEFAULT: Santa Maria (SBSM / WMO 83937), 01–02/mar/2024, 00Z e 12Z.

O QUE FAZ:
  1) Baixa as sondagens da Univ. de Wyoming (via siphon; fallback wsgi cru).
  2) Calcula índices: CAPE/CIN (superfície e camada média), LI, K, TT,
     água precipitável, cisalhamento 0-6 km, SRH 0-3 km (se houver vento).
  3) Plota skew-T + hodógrafa de cada sondagem.
  4) Roda o Rosenfeld r_e(T) do script 02 sobre o alvo (mesmas ressalvas:
     o r_e é PROXY — troque por retrieval calibrado antes de publicar).
  5) Roda a LINHA DO TEMPO do script 01 (Oulu + marcos solares do mês +
     fase das datas do caso vs. o SSC de referência).
  6) Roda a cadeia GNSS/TEC do script 03 (evento vs. controles; o EMBRACE
     exige download manual — use --tec-local para apontar o TECMAP).
  7) Escreve relatorio_<caso>.md com tabelas e figuras.

COMO USAR (na sua máquina — o chat não alcança Wyoming/NOAA):
  pip install siphon metpy pandas numpy matplotlib goes2go xarray pyproj netcdf4
  python 04_diagnostico_sondagem_satelite.py                      # caso default
  python 04_diagnostico_sondagem_satelite.py --sem-goes           # só sondagem
  python 04_diagnostico_sondagem_satelite.py --datas 2024-04-15 --estacao 83971

CONTEXTO DO CASO 01–02/mar/2024 (para a linha do tempo do script 01):
  Sem evento solar relevante nessas datas; o grande FD de março/2024 foi
  23–24/mar (X1.1 + halo-CME ~1470 km/s -> tempestade G4 em 24/mar).
  Ou seja: 01–02/mar serve como CANDIDATO A CONTROLE "sem FD" — exatamente
  o que a disciplina metodológica do README pede (item 2).
"""

import argparse
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parents[1]

# ----------------------------------------------------------------------
# CONFIG DEFAULT DO CASO  <<< pode sobrescrever via linha de comando >>>
# ----------------------------------------------------------------------
CASO = dict(
    nome="Toro_01-02mai",
    estacoes=["83937", "83971", "83827"],   # SBSM, SBPA, SBFI (edite à vontade)
    datas=["2024-05-01", "2024-05-02"],
    horas=[0, 12],                # UT
    lat=-29.5, lon=-51.2,         # centro do toró (encosta da Serra/Caxias)
    raio_km=150,
    goes_horas=["20:00", "21:00", "22:00", "23:00"],  # 17-21h local = 20-00 UT
)

# nomes amigáveis (qualquer código WMO não listado funciona igual)
ESTACOES_NOMES = {
    "83937": "Santa Maria/SBSM",
    "83971": "Porto Alegre/SBPA",
    "83827": "Foz do Iguaçu/SBFI",
    "83840": "Curitiba/SBCT",
    "83779": "São Paulo/SBMT",
}

# Marcos solares do período (datas verificadas — mesmas do script 01).
# O toró de 01-02/mai cai ~8,5 dias ANTES da chegada do CME -> "sem FD".
MARCOS_SOLARES = [
    ("2024-05-08 22:36", "CME geoefetivo lançado", "orange"),
    ("2024-05-10 17:05", "SSC — CME chega à Terra", "red"),
    ("2024-05-11 00:00", "Mínimo do Forbush (~15%)", "purple"),
    ("2024-05-11 03:00", "GLE74", "blue"),
]
T_SSC_REF = "2024-05-10 17:05"    # referência p/ fase_relativa
JANELA_OULU = ("2024-04-25", "2024-05-16")   # cobre o toró E o FD de maio

# Janelas p/ TEC (script 03): evento = datas do caso +-2 d; controles na
# mesma sazonalidade SEM toró (edite conforme seu catálogo EVENTOS_TORO).
JANELAS_TEC_CONTROLE = [
    dict(nome="Controle abr calmo", ini="2024-04-10", fim="2024-04-16"),
    dict(nome="Controle jun calmo", ini="2024-06-10", fim="2024-06-16"),
]

# ----------------------------------------------------------------------
# 1) SONDAGEM — download
# ----------------------------------------------------------------------
def baixar_sondagem(estacao, dt):
    """Sondagem com CACHE local (dados_sondagens/) — só baixa uma vez.
    PRIMÁRIO: endpoint wsgi novo do Wyoming. FALLBACK: siphon."""
    import pandas as pd
    cache = AQUI / "dados/sondagens"
    cache.mkdir(exist_ok=True)
    f = cache / f"{estacao}_{dt:%Y%m%d_%H}Z.csv"
    if f.exists():
        print(f"  (cache) {f.name}")
        return pd.read_csv(f)
    try:
        df = _baixar_wsgi(estacao, dt)
    except Exception as e:
        print(f"  wsgi falhou ({e}); tentando siphon...")
        from siphon.simplewebservice.wyoming import WyomingUpperAir
        df = WyomingUpperAir.request_data(dt, estacao)
        df = df.drop_duplicates(subset="pressure", keep="first")
        df = df.sort_values("pressure", ascending=False).reset_index(drop=True)
    df.to_csv(f, index=False)
    return df

def _baixar_wsgi(estacao, dt):
    """Endpoint novo https://weather.uwyo.edu/wsgi/sounding."""
    import io
    import requests
    import pandas as pd
    url = ("https://weather.uwyo.edu/wsgi/sounding?"
           f"datetime={dt:%Y-%m-%d%%20%H:%M:%S}&id={estacao}&type=TEXT:LIST")
    txt = requests.get(url, timeout=60,
                       headers={"User-Agent": "Mozilla/5.0 (research script)"}).text
    # bloco de dados: linhas fixas entre os cabeçalhos '-----'
    blocos = txt.split("-" * 10)
    dados = max(blocos, key=len)
    cols = ["pressure", "height", "temperature", "dewpoint", "relh", "mixr",
            "direction", "speed", "theta", "theta_e", "theta_v"]
    df = pd.read_fwf(io.StringIO(dados), names=cols, header=None,
                     widths=[7] * 11).apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["pressure", "temperature"]).reset_index(drop=True)
    # níveis com pressão repetida (ex.: 50.0 hPa duplicado) quebram o MetPy
    df = df.drop_duplicates(subset="pressure", keep="first")
    df = df.sort_values("pressure", ascending=False).reset_index(drop=True)
    if df.empty:
        raise RuntimeError(f"Sem dados p/ {estacao} em {dt} (sondagem não lançada?)")
    return df

# ----------------------------------------------------------------------
# 2) SONDAGEM — índices
# ----------------------------------------------------------------------
def _nivel_isoterma(df, T_alvo, col="temperature"):
    """(pressão hPa, altura m MSL) da primeira travessia de T_alvo, de baixo
    para cima. NaN se o perfil não cruza."""
    T = df[col].values
    p = df["pressure"].values
    z = df["height"].values
    for i in range(len(T) - 1):
        if np.isfinite(T[i]) and np.isfinite(T[i + 1]) and \
           (T[i] - T_alvo) * (T[i + 1] - T_alvo) <= 0 and T[i] != T[i + 1]:
            f = (T_alvo - T[i]) / (T[i + 1] - T[i])
            return (p[i] + f * (p[i + 1] - p[i]),
                    z[i] + f * (z[i + 1] - z[i]))
    return np.nan, np.nan

def _z_de_p(df, p_alvo):
    """Altura (m MSL) interpolada para uma pressão alvo (hPa)."""
    p = df["pressure"].values
    z = df["height"].values
    return float(np.interp(np.log(p_alvo), np.log(p[::-1]), z[::-1]))

def _T_de_p(df, p_alvo):
    p = df["pressure"].values
    T = df["temperature"].values
    return float(np.interp(np.log(p_alvo), np.log(p[::-1]), T[::-1]))

def indices(df):
    """Índices termodinâmicos/cinemáticos + PARÂMETROS DE GELO (MetPy).
    Alturas em m acima do solo (AGL), exceto onde indicado."""
    import metpy.calc as mpcalc
    from metpy.units import units

    p = df["pressure"].values * units.hPa
    T = df["temperature"].values * units.degC
    Td = df["dewpoint"].values * units.degC
    z_solo = float(df["height"].values[0])
    out = {}

    # --- instabilidade clássica ---
    prof = mpcalc.parcel_profile(p, T[0], Td[0]).to("degC")
    cape, cin = mpcalc.cape_cin(p, T, Td, prof)
    out["CAPE_sfc (J/kg)"] = float(cape.m)
    out["CIN_sfc (J/kg)"] = float(cin.m)
    try:
        mlcape, mlcin = mpcalc.mixed_layer_cape_cin(p, T, Td)
        out["MLCAPE (J/kg)"] = float(mlcape.m)
        out["MLCIN (J/kg)"] = float(mlcin.m)
    except Exception:
        pass
    try:
        mucape, mucin = mpcalc.most_unstable_cape_cin(p, T, Td)
        out["MUCAPE (J/kg)"] = float(mucape.m)
    except Exception:
        pass
    out["LI (C)"] = float(mpcalc.lifted_index(p, T, prof)[0].m)
    try:
        out["Showalter (C)"] = float(mpcalc.showalter_index(p, T, Td)[0].m)
    except Exception:
        pass
    out["K (C)"] = float(mpcalc.k_index(p, T, Td).m)
    out["TT (C)"] = float(mpcalc.total_totals_index(p, T, Td).m)
    out["PW (mm)"] = float(mpcalc.precipitable_water(p, Td).to("mm").m)
    try:
        dcape = mpcalc.downdraft_cape(p, T, Td)[0]
        out["DCAPE (J/kg)"] = float(dcape.m)
    except Exception:
        pass

    # --- níveis da parcela ---
    try:
        p_lcl, _ = mpcalc.lcl(p[0], T[0], Td[0])
        out["LCL (m AGL)"] = _z_de_p(df, float(p_lcl.m)) - z_solo
    except Exception:
        pass
    try:
        p_lfc, _ = mpcalc.lfc(p, T, Td, prof)
        if np.isfinite(p_lfc.m):
            out["LFC (m AGL)"] = _z_de_p(df, float(p_lfc.m)) - z_solo
    except Exception:
        pass
    try:
        p_el, T_el = mpcalc.el(p, T, Td, prof)
        if np.isfinite(p_el.m):
            out["EL (m AGL)"] = _z_de_p(df, float(p_el.m)) - z_solo
            out["T_topo/EL (C)"] = float(T_el.m)
    except Exception:
        pass

    # --- PARÂMETROS DE GELO / FASE MISTA ---
    for Ta, rot in [(0, "Z 0C"), (-10, "Z -10C"), (-20, "Z -20C"),
                    (-38, "Z -38C (glaciação)")]:
        _, zt = _nivel_isoterma(df, Ta)
        if np.isfinite(zt):
            out[f"{rot} (m AGL)"] = zt - z_solo
    # bulbo úmido 0C (WBZ — granizo em superfície)
    try:
        tw = mpcalc.wet_bulb_temperature(p, T, Td).to("degC").m
        dfw = df.copy(); dfw["tw"] = tw
        _, zwbz = _nivel_isoterma(dfw, 0.0, col="tw")
        if np.isfinite(zwbz):
            out["WBZ 0C bulbo umido (m AGL)"] = zwbz - z_solo
    except Exception:
        pass
    # profundidade da nuvem quente (LCL -> 0C): colisão-coalescência
    if "LCL (m AGL)" in out and "Z 0C (m AGL)" in out:
        out["Nuvem quente LCL-0C (m)"] = out["Z 0C (m AGL)"] - out["LCL (m AGL)"]
    # espessura da zona de crescimento de granizo (-10 a -30C)
    _, zm10 = _nivel_isoterma(df, -10)
    _, zm30 = _nivel_isoterma(df, -30)
    if np.isfinite(zm10) and np.isfinite(zm30):
        out["Espessura HGZ -10..-30C (m)"] = zm30 - zm10
    # CAPE dentro da HGZ (empuxo da parcela onde o ambiente esta entre -10 e -30C)
    Te, Tp, pm = T.m, prof.m, p.m
    sel = (Te <= -10) & (Te >= -30)
    if sel.sum() >= 2:
        # CAPE = int Rd (Tp - Te) d ln p  (na camada onde -30C <= Te <= -10C)
        # np.trapz foi removido no NumPy 2.x (agora np.trapezoid)
        _trapz = getattr(np, "trapezoid", None) or np.trapz
        b = 287.05 * np.maximum(Tp[sel] - Te[sel], 0)
        out["CAPE_HGZ (J/kg)"] = float(-_trapz(b, np.log(pm[sel])))

    # --- lapse rates ---
    try:
        out["LR 850-500 (C/km)"] = 1000 * (_T_de_p(df, 850) - _T_de_p(df, 500)) \
            / (_z_de_p(df, 500) - _z_de_p(df, 850))
        out["LR 700-500 (C/km)"] = 1000 * (_T_de_p(df, 700) - _T_de_p(df, 500)) \
            / (_z_de_p(df, 500) - _z_de_p(df, 700))
    except Exception:
        pass

    # --- cinemática ---
    if df["speed"].notna().sum() > 5:          # há vento?
        from metpy.units import units as u
        wdir = df["direction"].values * u.deg
        wspd = (df["speed"].values * u.knot)
        u_w, v_w = mpcalc.wind_components(wspd, wdir)
        h = df["height"].values * u.meter
        for dep, rot in [(1, "Shear 0-1km"), (3, "Shear 0-3km"),
                         (6, "Shear 0-6km")]:
            try:
                us, vs = mpcalc.bulk_shear(p, u_w, v_w, height=h,
                                           depth=dep * u.km)
                out[f"{rot} (m/s)"] = float(np.hypot(us.m, vs.m)
                                            * 0.514444)  # kt->m/s se necessario
            except Exception:
                pass
        try:
            _, _, srh1 = mpcalc.storm_relative_helicity(h, u_w, v_w, depth=1 * u.km)
            _, _, srh3 = mpcalc.storm_relative_helicity(h, u_w, v_w, depth=3 * u.km)
            out["SRH 0-1km (m2/s2)"] = float(srh1.m)
            out["SRH 0-3km (m2/s2)"] = float(srh3.m)
        except Exception:
            pass
    return out

# ----------------------------------------------------------------------
# 3) SONDAGEM — skew-T + hodógrafa
# ----------------------------------------------------------------------
def plotar_skewt(df, titulo, saida, idx=None):
    """Skew-T completo: perfis, parcela, CAPE/CIN sombreados, NÍVEIS DE GELO
    (0/-10/-20/-38C e WBZ), zona de crescimento de granizo sombreada,
    hodógrafa e caixa com todos os índices calculados."""
    import matplotlib.pyplot as plt
    import metpy.calc as mpcalc
    from metpy.plots import SkewT, Hodograph
    from metpy.units import units

    p = df["pressure"].values * units.hPa
    T = df["temperature"].values * units.degC
    Td = df["dewpoint"].values * units.degC

    fig = plt.figure(figsize=(12, 9))
    skew = SkewT(fig, rotation=45, rect=(0.05, 0.05, 0.60, 0.90))
    skew.plot(p, T, "r", lw=2, label="T")
    skew.plot(p, Td, "g", lw=2, label="Td")
    prof = mpcalc.parcel_profile(p, T[0], Td[0]).to("degC")
    skew.plot(p, prof, "k--", lw=1.5, label="parcela (sfc)")
    skew.shade_cape(p, T, prof)
    skew.shade_cin(p, T, prof, Td)
    skew.plot_dry_adiabats(alpha=.25)
    skew.plot_moist_adiabats(alpha=.25)
    skew.plot_mixing_lines(alpha=.25)

    # ---- níveis de gelo: linhas na pressão em que o AMBIENTE cruza ----
    niveis = [(0, "purple", "0C"), (-10, "royalblue", "-10C"),
              (-20, "navy", "-20C"), (-38, "black", "-38C glaciação")]
    for Ta, cor, rot in niveis:
        pn, zn = _nivel_isoterma(df, Ta)
        if np.isfinite(pn):
            skew.ax.axhline(pn, color=cor, ls=":", lw=1.2)
            skew.ax.annotate(f" {rot} ({zn/1000:.1f} km)", (0.02, pn),
                             xycoords=("axes fraction", "data"),
                             fontsize=7.5, color=cor, va="bottom")
    # zona de crescimento de granizo (-10 a -30C) sombreada
    p10, _ = _nivel_isoterma(df, -10)
    p30, _ = _nivel_isoterma(df, -30)
    if np.isfinite(p10) and np.isfinite(p30):
        skew.ax.axhspan(p30, p10, color="skyblue", alpha=0.12)
    # WBZ
    try:
        tw = mpcalc.wet_bulb_temperature(p, T, Td).to("degC").m
        dfw = df.copy(); dfw["tw"] = tw
        pwbz, zwbz = _nivel_isoterma(dfw, 0.0, col="tw")
        if np.isfinite(pwbz):
            skew.ax.axhline(pwbz, color="darkorange", ls="--", lw=1.0)
            skew.ax.annotate(f" WBZ ({zwbz/1000:.1f} km)", (0.02, pwbz),
                             xycoords=("axes fraction", "data"),
                             fontsize=7.5, color="darkorange", va="top")
    except Exception:
        pass

    skew.ax.set_ylim(1050, 100)
    skew.ax.set_xlim(-40, 45)
    skew.ax.set_title(titulo)
    skew.ax.legend(loc="lower left", fontsize=8)

    if df["speed"].notna().sum() > 5:
        wdir = df["direction"].values * units.deg
        wspd = df["speed"].values * units.knot
        u_w, v_w = mpcalc.wind_components(wspd, wdir)
        skew.plot_barbs(p[::3], u_w[::3], v_w[::3])
        ax_h = fig.add_axes([0.68, 0.62, 0.28, 0.30])
        h = Hodograph(ax_h, component_range=40)
        h.add_grid(increment=10)
        km = df["height"].values / 1000.0
        sel = km < 10
        h.plot_colormapped(u_w[sel].to("m/s"), v_w[sel].to("m/s"),
                           (km[sel] * units.km))
        ax_h.set_title("Hodógrafa 0-10 km", fontsize=8)

    # ---- caixa com TODOS os índices ----
    if idx:
        linhas = [f"{k:<26s}{v:>8.0f}" if abs(v) >= 10 else
                  f"{k:<26s}{v:>8.1f}" for k, v in idx.items()]
        fig.text(0.68, 0.05, "\n".join(linhas), fontsize=7.5,
                 family="monospace", va="bottom",
                 bbox=dict(boxstyle="round", facecolor="ivory", alpha=0.9))

    fig.savefig(saida, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Figura salva:", saida)

# ----------------------------------------------------------------------
# 4) SATÉLITE / TIMELINE / TEC — reusa os scripts 01, 02 e 03 (sem duplicar)
# ----------------------------------------------------------------------
def _carregar(nome_arquivo, alias):
    spec = importlib.util.spec_from_file_location(alias, AQUI / nome_arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def _carregar_mod02():
    return _carregar("toro_02_rosenfeld_goes16.py", "rosenfeld02")

def rodar_timeline(caso, pasta):
    """Script 01 aplicado ao caso: raios cósmicos Oulu + marcos do mês +
    as datas do caso como 'toró'; calcula a fase de cada data vs. o SSC."""
    m1 = _carregar("toro_01_series_espaciais.py", "series01")
    eventos = [(f"{d} 12:00", f"caso {caso['nome']}", caso["lat"], caso["lon"])
               for d in caso["datas"]]
    try:
        df = m1.baixar_oulu(*JANELA_OULU)
        df = m1.baseline_pct(df)
        print(f"  Oulu: {len(df)} pontos; mínimo {df.pct.min():.1f}% em "
              f"{df.loc[df.pct.idxmin(), 'tempo']}")
    except Exception as e:
        print("  !! Oulu indisponível (segue só com marcos):", e)
        df = None
    png = pasta / f"timeline_{caso['nome']}.png"
    m1.plotar(df, MARCOS_SOLARES, eventos, saida=str(png))
    m1.fase_relativa(eventos, t_ssc=T_SSC_REF, t_min=T_SSC_REF)
    return png

def rodar_tec(caso, pasta, tec_local=None):
    """TEC do caso via 01_series_espaciais (IONEX do EMBRACE com cache):
    anomalia evento vs. controles + figura."""
    import matplotlib.pyplot as plt
    import pandas as pd
    m1 = _carregar("toro_01_series_espaciais.py", "series01_tec")
    datas = sorted(caso["datas"])
    ini = (pd.to_datetime(datas[0]) - pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    fim = (pd.to_datetime(datas[-1]) + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    tec = m1.tec_ionex(ini, fim)
    if tec is None:
        raise RuntimeError(f"sem IONEX p/ {ini}..{fim} (cache/rede)")
    ctrls = []
    for j in JANELAS_TEC_CONTROLE:
        try:
            ctrls.append(m1.tec_ionex(j["ini"], j["fim"]))
        except Exception as e:
            print(f"  controle {j['nome']} indisponível: {e}")
    m1.comparar_tec(tec, ctrls)
    png = pasta / f"tec_{caso['nome']}.png"
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(tec.tempo, tec.v, color="darkred", lw=1.2,
            label="Anomalia de TEC na caixa AMAS/RS")
    ax.axhline(0, color="gray", ls=":", lw=0.5)
    for t, lab, cor in MARCOS_SOLARES:
        ax.axvline(pd.to_datetime(t), color=cor, lw=1.3, alpha=0.7)
    for d in caso["datas"]:
        ax.axvline(pd.to_datetime(f"{d} 12:00"), color="green", lw=2, ls="--")
    ax.set_ylabel("Anomalia TEC (TECU)")
    ax.legend(fontsize=8)
    ax.set_title(f"TEC — {caso['nome']}")
    plt.tight_layout()
    fig.savefig(png, dpi=150)
    plt.close(fig)
    return png

def rodar_rosenfeld(caso, data, hora, pasta):
    m2 = _carregar_mod02()
    cenas = m2.baixar_goes(data, hora)
    rec = {b: m2.recortar(cenas[b], caso["lat"], caso["lon"], caso["raio_km"])
           for b in cenas}
    Tc, re = m2.curva_re_T(rec["C07"], rec["C13"], rec["C02"])
    mb = m2.diagnosticar(Tc, re)
    hh = hora.replace(":", "")
    png = pasta / f"rosenfeld_{data}_{hh}UT.png"
    m2.plotar(Tc, re, mb, saida=str(png),
              titulo=f"Rosenfeld — {caso['nome']} — {data} {hora} UT")
    mapa = pasta / f"mapa_topo_{data}_{hh}UT.png"
    m2.mapa_topo(rec["C13"], str(mapa),
                 titulo=f"Topo (C13) — {caso['nome']} — {data} {hora} UT")
    bins, med = mb
    # salva a curva mediana p/ comparação entre casos (06_compara_curvas.py)
    import pandas as pd
    regime = getattr(m2, "REGIME_ULTIMA_CENA", "desconhecido")
    pd.DataFrame(dict(T_bin=bins, mediana=med, caso=caso["nome"],
                      quando=f"{data} {hora}UT", n_pixels=len(Tc),
                      regime=regime)).to_csv(
        pasta / f"curva_{data}_{hh}UT.csv", index=False)
    return (png, mapa), list(zip(bins.tolist(),
                                 [float(x) if np.isfinite(x) else None for x in med]))

# ----------------------------------------------------------------------
# 5) RELATÓRIO
# ----------------------------------------------------------------------
def escrever_relatorio(caso, resultados, pasta):
    ests = ", ".join(f"{e} ({ESTACOES_NOMES.get(e, '?')})"
                     for e in caso["estacoes"])
    md = [f"# Diagnóstico — {caso['nome']}",
          "",
          f"Estações: {ests} | alvo {caso['lat']:.2f}, {caso['lon']:.2f} "
          f"(raio {caso['raio_km']} km) | gerado em {datetime.utcnow():%Y-%m-%d %H:%M} UT",
          ""]
    md += ["## Sondagens (skew-T + índices de instabilidade, gelo e cisalhamento)", ""]
    for est in caso["estacoes"]:
        md += [f"## Estação {ESTACOES_NOMES.get(est, est)} ({est})", ""]
        for r in resultados["sondagens"]:
            if r.get("estacao") != est:
                continue
            md += [f"### {r['quando']}", ""]
            if r.get("erro"):
                md += [f"*Falha: {r['erro']}*", ""]
                continue
            md += ["| Índice | Valor |", "|---|---|"]
            md += [f"| {k} | {v:.1f} |" for k, v in r["indices"].items()]
            md += ["", f"![skew-T]({r['figura'].name})", ""]
    md += ["## Rosenfeld r_e(T) — GOES-16 (proxy; ver ressalva do 02)", ""]
    for r in resultados["goes"]:
        if r.get("erro"):
            md += [f"*{r['quando']}: falha — {r['erro']}*", ""]
            continue
        md += [f"### {r['quando']}", "", f"![rosenfeld]({r['figura'].name})", ""]
        if r.get("mapa"):
            md += [f"![mapa topo]({r['mapa'].name})", ""]
    md += ["## Linha do tempo solar (script 01)", ""]
    t = resultados.get("timeline")
    if t is None:
        md += ["*pulada (--sem-timeline)*", ""]
    elif isinstance(t, str):
        md += [f"*falha — {t}*", ""]
    else:
        md += [f"![timeline]({t.name})", "",
               "Fase das datas do caso em relação ao SSC de referência "
               f"({T_SSC_REF}, aprox.): ver saída do console.", ""]
    md += ["## Cadeia GNSS/TEC (script 03)", ""]
    g = resultados.get("tec")
    if g is None:
        md += ["*pulada (--sem-tec)*", ""]
    elif isinstance(g, str):
        md += [f"*pendente/falha — {g}*",
               "",
               "Passo manual: baixe o TECMAP do período no portal EMBRACE",
               "(www2.inpe.br/climaespacial) e rode de novo com",
               "`--tec-local caminho/do/arquivo`.", ""]
    else:
        md += [f"![tec]({g.name})", ""]
    md += ["## Leitura honesta",
           "",
           "- O toró de 01–02/mai/2024 cai ~8,5 dias ANTES da chegada do CME",
           "  (SSC 10/mai 17:05) — é o 'evento extremo SEM FD concomitante'.",
           "  O 12/mai (1,5 d após o SSC) é o par 'COM FD'. Mesma região,",
           "  mesma semana, mesma estação do ano: comparação quase ideal.",
           "- Se a assinatura Rosenfeld/BTD dos dois for IGUAL, a microfísica",
           "  não discrimina o gatilho solar. Se diferente, aprofunde.",
           "- N=2 ainda não prova nada; o teste real é o estatístico (README).", ""]
    out = pasta / f"relatorio_{caso['nome']}.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print("Relatório salvo:", out)

# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("--estacoes", "--estacao", nargs="+", dest="estacoes",
                    default=CASO["estacoes"],
                    help="códigos WMO, ex.: --estacoes 83937 83971 83827")
    ap.add_argument("--datas", nargs="+", default=CASO["datas"])
    ap.add_argument("--horas", nargs="+", type=int, default=CASO["horas"])
    ap.add_argument("--lat", type=float, default=CASO["lat"])
    ap.add_argument("--lon", type=float, default=CASO["lon"])
    ap.add_argument("--raio", type=float, default=CASO["raio_km"])
    ap.add_argument("--nome", default=CASO["nome"])
    ap.add_argument("--goes-horas", nargs="+", default=CASO["goes_horas"],
                    help="horas UT p/ o Rosenfeld, ex.: --goes-horas 09:00 12:00 15:00")
    ap.add_argument("--sem-goes", action="store_true",
                    help="pula o Rosenfeld (só sondagens)")
    ap.add_argument("--sem-timeline", action="store_true",
                    help="pula a linha do tempo solar (script 01)")
    ap.add_argument("--sem-tec", action="store_true",
                    help="pula a cadeia GNSS/TEC (script 03)")
    ap.add_argument("--tec-local", default=None,
                    help="TECMAP baixado manualmente do EMBRACE (p/ script 03)")
    a = ap.parse_args()
    caso = dict(nome=a.nome, estacoes=a.estacoes, datas=a.datas, horas=a.horas,
                lat=a.lat, lon=a.lon, raio_km=a.raio,
                goes_horas=a.goes_horas)

    pasta = AQUI / f"saida_{caso['nome']}"
    pasta.mkdir(exist_ok=True)
    resultados = {"sondagens": [], "goes": [], "timeline": None, "tec": None}

    for est in caso["estacoes"]:
        nome_est = ESTACOES_NOMES.get(est, est)
        for data in caso["datas"]:
            for hh in caso["horas"]:
                dt = datetime.strptime(f"{data} {hh:02d}", "%Y-%m-%d %H")
                quando = f"{nome_est} ({est}) — {data} {hh:02d}Z"
                print("\n==>", quando)
                try:
                    df = baixar_sondagem(est, dt)
                    idx = indices(df)
                    for k, v in idx.items():
                        print(f"  {k:28s} {v:9.1f}")
                    png = pasta / f"skewt_{est}_{data}_{hh:02d}Z.png"
                    plotar_skewt(df, quando, png, idx=idx)
                    resultados["sondagens"].append(
                        dict(quando=quando, estacao=est, indices=idx,
                             figura=png))
                except Exception as e:
                    print("  !! falhou:", e)
                    resultados["sondagens"].append(
                        dict(quando=quando, estacao=est, erro=str(e)))

    if not a.sem_goes:
        for data in caso["datas"]:
            for hora in caso["goes_horas"]:
                quando = f"GOES-16 — {data} {hora} UT"
                print("\n==>", quando)
                try:
                    (png, mapa), curva = rodar_rosenfeld(caso, data, hora, pasta)
                    resultados["goes"].append(
                        dict(quando=quando, figura=png, mapa=mapa, curva=curva))
                except Exception as e:
                    print("  !! falhou (rode na sua máquina c/ goes2go):", e)
                    resultados["goes"].append(dict(quando=quando, erro=str(e)))

    if not a.sem_timeline:
        print("\n==> Linha do tempo solar (script 01)")
        try:
            resultados["timeline"] = rodar_timeline(caso, pasta)
        except Exception as e:
            print("  !! timeline falhou:", e)
            resultados["timeline"] = str(e)

    if not a.sem_tec:
        print("\n==> Cadeia GNSS/TEC (script 03)")
        try:
            resultados["tec"] = rodar_tec(caso, pasta, tec_local=a.tec_local)
        except NotImplementedError as e:
            print("  !! passo manual do EMBRACE pendente:", e)
            resultados["tec"] = str(e)
        except Exception as e:
            print("  !! TEC falhou:", e)
            resultados["tec"] = str(e)

    escrever_relatorio(caso, resultados, pasta)

if __name__ == "__main__":
    sys.exit(main())
