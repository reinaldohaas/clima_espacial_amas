#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
01_timeline_may2024.py
======================
ESPINHA TEMPORAL — Gannon storm (maio/2024) vs. eventos de toró.

OBJETIVO (honesto): NÃO assumir que 2/maio é o gatilho. Construir a linha do
tempo completa com os marcos solares/geomagnéticos + o fluxo de raios
cósmicos (Forbush) de Oulu, e SOBREPOR as datas dos torós/eventos extremos.
Deixar os dados mostrarem se há alinhamento — ou não.

COMO USAR NO COWORK:
  1. pip install requests pandas matplotlib numpy
  2. python 01_timeline_may2024.py
  3. O script baixa os dados de neutron monitor de Oulu (precisa de internet).
     No chat da Anthropic isso NÃO roda (rede restrita); rode na sua máquina.

O QUE ELE FAZ:
  - Baixa a contagem de raios cósmicos de Oulu (resolução horária) p/ maio 2024.
  - Marca os eventos solares conhecidos (datas verificadas por fontes primárias).
  - Plota a série + marcadores + as SUAS datas de toró (você preenche EVENTOS_TORO).
  - Calcula, para cada toró, a "fase" em relação ao Forbush (antes/durante/depois).

Fontes das datas solares (verificadas):
  - CME geoefetivo lançado: 8 maio 22:36 UT (IOPscience Flash Data Report 2024)
  - SSC (chegada à Terra): 10 maio 17:05 UT  -> trânsito ~42,5 h
  - FD ~15% (mínimo) : 10-11 maio (~00 UT dia 11)
  - GLE74            : 11 maio ~03 UT
  - Região ativa surge no limbo leste: ~2 maio (NÃO é efeito na Terra ainda)
"""

import datetime as dt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ----------------------------------------------------------------------
# 1) MARCOS SOLARES / GEOMAGNÉTICOS (datas verificadas, UT)
# ----------------------------------------------------------------------
MARCOS = [
    ("2024-05-02 00:00", "Região ativa surge no limbo (NÃO é efeito terrestre)", "gray"),
    ("2024-05-08 22:36", "CME geoefetivo lançado", "orange"),
    ("2024-05-10 17:05", "SSC — CME chega à Terra (início da tempestade)", "red"),
    ("2024-05-11 00:00", "Mínimo do Forbush (~15%)", "purple"),
    ("2024-05-11 03:00", "GLE74", "blue"),
]

# ----------------------------------------------------------------------
# 2) SEUS EVENTOS DE TORÓ / EXTREMOS  <<< PREENCHER >>>
#    Coloque data (e hora se souber, UT) + rótulo + lat/lon se tiver.
#    Ex.: ("2024-05-12 06:00", "Cheia máxima RS / supercélula", -29.5, -51.2)
# ----------------------------------------------------------------------
EVENTOS_TORO = [
    # ("2024-04-28 00:00", "Início das chuvas RS", None, None),
    # ("2024-05-12 06:00", "Cheia máxima / supercélula", -29.5, -51.2),
    # <<< ADICIONE AQUI >>>
]

# ----------------------------------------------------------------------
# 3) BAIXAR DADOS DE RAIOS CÓSMICOS DE OULU
#    Oulu NM: serviço de dados em cosmicrays.oulu.fi
#    (Se a URL mudar, use a interface https://cosmicrays.oulu.fi/ -> "Data")
# ----------------------------------------------------------------------
def baixar_oulu(inicio="2024-05-01", fim="2024-05-15"):
    """Baixa contagem horária corrigida por pressão do Oulu NM.
    Retorna DataFrame [tempo, counts]. Ajuste a URL conforme o serviço atual."""
    import requests
    # Formato do serviço "get_data" do Oulu (pode exigir ajuste de parâmetros):
    # Muitos usam o NMDB (www.nmdb.eu) via API 'nest'. Alternativa robusta:
    #   http://www.nmdb.eu/nest/draw_graph.php  (interface) -> exporte CSV
    # Aqui deixamos o esqueleto com NMDB (estação OULU):
    url = ("https://www.nmdb.eu/nest/draw_graph.php?formchk=1"
           "&stations[]=OULU&tabchoice=revori&dtype=corr_for_efficiency"
           f"&tresolution=60&yunits=0&date_choice=bydate"
           f"&start_year={inicio[:4]}&start_month={inicio[5:7]}&start_day={inicio[8:10]}"
           f"&start_hour=0&start_min=0"
           f"&end_year={fim[:4]}&end_month={fim[5:7]}&end_day={fim[8:10]}"
           f"&end_hour=23&end_min=59&output=ascii")
    print("Tentando baixar de NMDB/Oulu:\n", url)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    # O NMDB retorna texto com cabeçalho; as linhas de dados são "YYYY-MM-DD HH:MM:SS ; valor"
    linhas = [l for l in r.text.splitlines() if ";" in l and l[:4].isdigit()]
    if not linhas:
        raise RuntimeError("Sem dados — verifique a URL/estação no NMDB (www.nmdb.eu/nest).")
    tempos, vals = [], []
    for l in linhas:
        p = l.split(";")
        try:
            tempos.append(pd.to_datetime(p[0].strip()))
            vals.append(float(p[1]))
        except Exception:
            continue
    return pd.DataFrame({"tempo": tempos, "counts": vals})


# ----------------------------------------------------------------------
# 3b) MULTI-ESTAÇÃO: o FD visto em vários cortes de rigidez + estimativa
#     do que um monitor NO RS (corte ~10.5 GV) teria registrado.
#     Nuance do Reinaldo: Oulu (polar) superestima o "choque" sobre a AMAS.
# ----------------------------------------------------------------------
ESTACOES_NMDB = [          # (código NMDB, corte de rigidez GV)
    ("OULU", 0.81),        # polar, nível do mar — a referência histórica
    ("IRK2", 3.64),        # Irkutsk, 2000 m  } mesmo corte, alturas != :
    ("IRK3", 3.64),        # Irkutsk, 3000 m  } testa o efeito altitude
    ("JUNG", 4.49),        # Jungfraujoch, 3570 m
    ("MXCO", 8.28),        # Cidade do México, 2274 m — melhor proxy do RS
]
R_LOCAL_GV = 10.5          # corte aproximado sul do Brasil (AMAS reduz isso!)

def baixar_nmdb_multi(inicio, fim, estacoes=None):
    """Baixa várias estações de uma vez. Retorna DataFrame tempo + 1 col/estação."""
    import requests
    estacoes = estacoes or [e for e, _ in ESTACOES_NMDB]
    st = "".join(f"&stations[]={e}" for e in estacoes)
    url = ("https://www.nmdb.eu/nest/draw_graph.php?formchk=1" + st +
           "&tabchoice=revori&dtype=corr_for_efficiency"
           f"&tresolution=60&yunits=0&date_choice=bydate"
           f"&start_year={inicio[:4]}&start_month={inicio[5:7]}&start_day={inicio[8:10]}"
           f"&start_hour=0&start_min=0"
           f"&end_year={fim[:4]}&end_month={fim[5:7]}&end_day={fim[8:10]}"
           f"&end_hour=23&end_min=59&output=ascii")
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    linhas = [l for l in r.text.splitlines() if ";" in l and l[:4].isdigit()]
    if not linhas:
        raise RuntimeError("NMDB sem dados — confira estações/URL em nmdb.eu/nest")
    tempos, cols = [], [[] for _ in estacoes]
    for l in linhas:
        p = [x.strip() for x in l.split(";")]
        try:
            t = pd.to_datetime(p[0])
        except Exception:
            continue
        tempos.append(t)
        for k in range(len(estacoes)):
            try:
                cols[k].append(float(p[1 + k]))
            except (ValueError, IndexError):
                cols[k].append(np.nan)
    df = pd.DataFrame({"tempo": tempos})
    for k, e in enumerate(estacoes):
        df[e] = cols[k]
    return df

def fd_local_estimado(df, t_fd_ini, t_fd_fim):
    """Amplitude do FD em cada estação (% vs baseline pré-evento) e
    extrapolação p/ o corte local via lei de potência A ~ R^-gamma."""
    janela_fd = (df.tempo >= pd.to_datetime(t_fd_ini)) & \
                (df.tempo <= pd.to_datetime(t_fd_fim))
    base = df.tempo < pd.to_datetime(t_fd_ini)
    Rs, As = [], []
    print("\n--- Amplitude do FD por estação ---")
    for e, R in ESTACOES_NMDB:
        if e not in df or df[e].isna().all():
            continue
        b = df.loc[base, e].mean()
        amp = 100.0 * (b - df.loc[janela_fd, e].min()) / b
        print(f"  {e} (R={R:.2f} GV): {amp:.1f}%")
        if np.isfinite(amp) and amp > 0:
            Rs.append(R); As.append(amp)
    if len(Rs) >= 2:
        gamma, lna = np.polyfit(np.log(Rs), np.log(As), 1)
        a_local = float(np.exp(lna) * R_LOCAL_GV ** gamma)
        print(f"  ajuste A~R^{gamma:.2f}  ->  FD estimado em R={R_LOCAL_GV} GV "
              f"(sul do Brasil): ~{a_local:.1f}%")
        print("  (a AMAS REDUZ o corte local — o valor real fica entre isso e "
              "o de MXCO; um monitor de múons como o de São Martinho é a régua certa)")
        return a_local
    return None

def baseline_pct(df):
    """Converte contagem em % relativo à média dos 2 primeiros dias (pré-evento)."""
    base = df[df.tempo < df.tempo.min() + pd.Timedelta(days=2)].counts.mean()
    df = df.copy()
    df["pct"] = 100.0 * (df.counts - base) / base
    return df


# ----------------------------------------------------------------------
# 4) PLOTAR
# ----------------------------------------------------------------------
def plotar(df, marcos, eventos, saida="timeline_may2024.png"):
    fig, ax = plt.subplots(figsize=(13, 6))
    if df is not None:
        ax.plot(df.tempo, df.pct, color="k", lw=1.0, label="Raios cósmicos Oulu (% do baseline)")
        ax.axhline(0, color="gray", lw=0.5, ls=":")
    for t, lab, cor in marcos:
        x = pd.to_datetime(t)
        ax.axvline(x, color=cor, lw=1.6, alpha=0.8)
        ax.annotate(lab, (x, ax.get_ylim()[1]), rotation=90, va="top", ha="right",
                    fontsize=7.5, color=cor)
    for ev in eventos:
        t, lab = ev[0], ev[1]
        x = pd.to_datetime(t)
        ax.axvline(x, color="green", lw=2.2, ls="--")
        ax.annotate("TORÓ: " + lab, (x, ax.get_ylim()[0]), rotation=90,
                    va="bottom", ha="left", fontsize=8, color="green", weight="bold")
    ax.set_title("Linha do tempo — maio/2024: raios cósmicos, marcos solares e eventos de toró")
    ax.set_ylabel("Desvio da contagem de raios cósmicos (%)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.legend(loc="lower left", fontsize=8)
    plt.tight_layout()
    plt.savefig(saida, dpi=150)
    print("Figura salva:", saida)


def fase_relativa(eventos, t_ssc="2024-05-10 17:05", t_min="2024-05-11 00:00"):
    """Para cada toró, diz se caiu ANTES do CME chegar, DURANTE o FD, ou DEPOIS."""
    ssc = pd.to_datetime(t_ssc); tmin = pd.to_datetime(t_min)
    print("\n--- Fase de cada evento em relação ao Forbush ---")
    for ev in eventos:
        x = pd.to_datetime(ev[0])
        if x < ssc:
            fase = f"ANTES da chegada do CME ({(ssc-x).total_seconds()/86400:.1f} d antes)"
        elif x < tmin + pd.Timedelta(days=10):
            fase = f"DURANTE/APÓS o FD ({(x-ssc).total_seconds()/86400:.1f} d após SSC)"
        else:
            fase = "muito depois (fora da janela do FD)"
        print(f"  {ev[0]}  [{ev[1]}]  -> {fase}")


if __name__ == "__main__":
    try:
        df = baixar_oulu()
        df = baseline_pct(df)
        print(f"Baixados {len(df)} pontos. FD mínimo: {df.pct.min():.1f}% "
              f"em {df.loc[df.pct.idxmin(),'tempo']}")
    except Exception as e:
        print("!! Não consegui baixar Oulu (rode na sua máquina com internet):", e)
        print("   Plotando só os marcos e eventos.")
        df = None

    plotar(df, MARCOS, EVENTOS_TORO)
    if EVENTOS_TORO:
        fase_relativa(EVENTOS_TORO)
    else:
        print("\n>>> Preencha EVENTOS_TORO com suas datas para ver a fase relativa. <<<")

    # --- FD visto em vários cortes de rigidez + estimativa local (RS) ---
    try:
        dm = baixar_nmdb_multi("2024-05-01", "2024-05-15")
        fd_local_estimado(dm, "2024-05-10 17:00", "2024-05-12 00:00")
        fig, ax = plt.subplots(figsize=(13, 5))
        for e, R in ESTACOES_NMDB:
            if e in dm and not dm[e].isna().all():
                b = dm.loc[dm.tempo < dm.tempo.min() + pd.Timedelta(days=2), e].mean()
                ax.plot(dm.tempo, 100 * (dm[e] - b) / b, lw=1,
                        label=f"{e} (R={R} GV)")
        for t, lab, cor in MARCOS:
            ax.axvline(pd.to_datetime(t), color=cor, lw=1.2, alpha=0.7)
        ax.axhline(0, color="gray", lw=0.5, ls=":")
        ax.set_ylabel("Desvio (%) do baseline pré-evento")
        ax.set_title("FD de maio/2024 em função do corte de rigidez — "
                     "quanto maior o corte (mais perto do RS), menor o FD")
        ax.legend(fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        plt.tight_layout(); plt.savefig("timeline_multi_rigidez.png", dpi=150)
        print("Figura salva: timeline_multi_rigidez.png")
    except Exception as e:
        print("!! multi-estação falhou (rode com internet):", e)
