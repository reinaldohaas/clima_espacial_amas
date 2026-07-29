#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03_gnss_tec.py
==============
CADEIA GNSS: ionosfera (TEC) + troposfera (PWV) sobre a AMAS/RS,
sobreposta à linha do tempo solar e às datas de toró.

IDEIA (a hipótese de Reinaldo):
  Sol/AMAS -> termalização (elétrons extra descem e ionizam a alta troposfera
  dentro da AMAS) -> condutividade/Jz anômalos -> anti-varredura ->
  microfísica -> chuva/toró. O GNSS mede as DUAS PONTAS da cadeia:
    - TEC  (EMBRACE/INPE)  = ionização da coluna (o lado ionosférico/solar)
    - PWV  (RBMC/IBGE)     = vapor d'água integrado (o lado troposférico)
  O MEIO da cadeia (Jz -> microfísica) permanece INFERÊNCIA (contestado).

BASE OBSERVACIONAL (para citar no artigo):
  Abdu et al. (2005), J. Atmos. Solar-Terr. Phys. 67:1643-1657 — ionização
  aumentada por precipitação de partículas sobre a AMAS eleva a condutividade
  ionosférica; opera até em condições calmas, intensifica em tempestades.
  (Isto sustenta o seu ponto de "termalização"; é observado, não conjectura.)

FONTES DE DADOS (públicas, brasileiras):
  - TEC/ROTI/S4 : EMBRACE/INPE  http://www2.inpe.br/climaespacial/portal/en/
                  (mapas TEC 10-min desde 2013; redes RBMC/LISN/IGS/RAMSAC)
  - PWV/observáveis GNSS : RBMC/IBGE (RINEX) -> processar com GAMIT/GipsyX
                  ou usar produto ZTD do IGS p/ estações brasileiras.

COMO USAR NO COWORK (precisa de internet):
  pip install requests pandas numpy matplotlib
  Editar ALVO_BOX (a caixa AMAS/RS) e as JANELAS (evento + controle).
  python 03_gnss_tec.py

⚠️ HONESTIDADE ESTATÍSTICA (leia antes de concluir qualquer coisa):
  A AMAS tem TEC anômalo QUASE SEMPRE (é a natureza dela). Achar "TEC anômalo
  no dia do toró" é quase garantido por acaso. Por isso este script SEMPRE
  compara EVENTO vs. CONTROLE (dias equivalentes sem toró). Só uma DIFERENÇA
  evento-controle é evidência; a mera presença de anomalia no evento não é.
"""

import datetime as dt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ----------------------------------------------------------------------
# CONFIG  <<< PREENCHER >>>
# ----------------------------------------------------------------------
ALVO_BOX = dict(nome="AMAS/RS", lat_min=-32, lat_max=-27, lon_min=-56, lon_max=-49)

# Janela do EVENTO (a cheia de 12/mai) e janelas de CONTROLE (dias sem toró,
# mesma estação do ano, para comparação justa). Preencha várias de controle.
JANELA_EVENTO   = dict(nome="Cheia 12mai2024", ini="2024-04-04", fim="2024-05-14")
JANELAS_CONTROLE = [
    dict(nome="Controle abr calmo", ini="2024-04-10", fim="2024-04-16"),
    dict(nome="Controle jun calmo", ini="2024-06-10", fim="2024-06-16"),
    # <<< ADICIONE mais dias-controle sem toró, mesma sazonalidade >>>
]

# datas de toró (para marcar) — reaproveite de 01_timeline
EVENTOS_TORO = [
    # ("2024-05-12 06:00", "Cheia máxima RS"),
]

# ----------------------------------------------------------------------
# 1) BAIXAR TEC DO EMBRACE
#    O EMBRACE serve mapas TEC (grade) e séries por estação. A API/estrutura
#    de arquivos muda; abaixo o ESQUELETO. Se o download automático falhar,
#    baixe manualmente do portal e aponte LER_TEC_LOCAL para o arquivo.
# ----------------------------------------------------------------------
LER_TEC_LOCAL = None   # ex.: "tecmap_2024_05.txt" se baixar manual

def baixar_tec_embrace(data_ini, data_fim, box):
    """Baixa os IONEX diários do EMBRACE (embracedata.inpe.br/ionex/) e
    devolve DataFrame [tempo, tec_box] = média do TEC na caixa AMAS/RS.
    Guarda os arquivos em dados_tec/ (cache — não rebaixa)."""
    if LER_TEC_LOCAL:
        return _ler_tecmap_local(LER_TEC_LOCAL, box, data_ini, data_fim)
    import requests
    from pathlib import Path
    cache = Path(__file__).resolve().parent / "dados_tec"
    cache.mkdir(exist_ok=True)
    linhas = []
    for dia in pd.date_range(data_ini, data_fim, freq="D"):
        doy = dia.dayofyear
        nome = f"INPE{doy:03d}0.{dia.year % 100:02d}I"
        f = cache / nome
        if not f.exists():
            url = f"https://embracedata.inpe.br/ionex/{dia.year}/{nome}"
            print("  baixando", url)
            r = requests.get(url, timeout=120)
            if r.status_code != 200:
                print(f"    !! {r.status_code} — sem IONEX p/ {dia.date()}")
                continue
            f.write_bytes(r.content)
        linhas += _parse_ionex(f.read_text(errors="ignore"), box)
    if not linhas:
        raise RuntimeError("Nenhum IONEX lido — confira o período em "
                           "embracedata.inpe.br/ionex/")
    return pd.DataFrame(linhas, columns=["tempo", "tec_box"])

def _parse_ionex(txt, box):
    """Parser IONEX 1.0: extrai média do TEC na caixa por época.
    Valores I5 em unidades 10^EXPONENT TECU; 9999 = faltante."""
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
    blocos = txt.split("START OF TEC MAP")[1:]
    for b in blocos:
        b = b.split("END OF TEC MAP")[0]
        ls = b.splitlines()
        epoca = None
        soma, n = 0.0, 0
        i = 0
        while i < len(ls):
            l = ls[i]
            if "EPOCH OF CURRENT MAP" in l:
                p = l.split()
                epoca = pd.Timestamp(*[int(x) for x in p[:6]])
            elif "LAT/LON1/LON2/DLON/H" in l:
                lat = float(l[2:8]); lon1 = float(l[8:14])
                lon2 = float(l[14:20]); dlon = float(l[20:26])
                nlon = int(round((lon2 - lon1) / dlon)) + 1
                vals = []
                while len(vals) < nlon and i + 1 < len(ls):
                    i += 1
                    vl = ls[i]
                    vals += [int(vl[k:k + 5]) for k in range(0, len(vl.rstrip()), 5)]
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

def _ler_tecmap_local(caminho, box, ini, fim):
    """Lê um TECMAP salvo localmente e extrai a média na caixa AMAS/RS.
    Espera colunas: tempo, lat, lon, tec  (ajuste ao formato do seu arquivo)."""
    df = pd.read_csv(caminho, sep=None, engine="python")
    df.columns = [c.strip().lower() for c in df.columns]
    m = ((df.lat >= box["lat_min"]) & (df.lat <= box["lat_max"]) &
         (df.lon >= box["lon_min"]) & (df.lon <= box["lon_max"]))
    df = df[m].copy()
    df["tempo"] = pd.to_datetime(df["tempo"])
    df = df[(df.tempo >= pd.to_datetime(ini)) & (df.tempo <= pd.to_datetime(fim))]
    return df.groupby("tempo", as_index=False)["tec"].mean().rename(columns={"tec":"tec_box"})

# ----------------------------------------------------------------------
# 2) ANOMALIA DE TEC = TEC - climatologia (mesma hora do dia, mesma estação)
#    Sem tirar o ciclo diurno/sazonal, a "anomalia" é só o ciclo normal.
# ----------------------------------------------------------------------
def anomalia_tec(df, clim=None):
    """Se clim (média por hora-do-dia de dias calmos) for dada, subtrai.
    Senão, usa a média do próprio período como referência (pior, mas serve p/ 1ª olhada)."""
    df = df.copy()
    df["hora"] = df.tempo.dt.hour
    if clim is None:
        ref = df.groupby("hora")["tec_box"].transform("mean")
    else:
        ref = df["hora"].map(clim)
    df["tec_anom"] = df["tec_box"] - ref
    return df

# ----------------------------------------------------------------------
# 3) COMPARAR EVENTO vs. CONTROLE (o passo que separa sinal de acaso)
# ----------------------------------------------------------------------
def comparar_evento_controle(tec_evento, tec_controles):
    print("\n--- EVENTO vs. CONTROLE (anomalia de TEC na caixa) ---")
    ev = tec_evento["tec_anom"]
    print(f"  Evento: média={ev.mean():+.2f}  máx={ev.max():+.2f}  TECU")
    todos_ctrl = []
    for c in tec_controles:
        a = c["tec_anom"]; todos_ctrl.append(a)
        print(f"  Controle: média={a.mean():+.2f}  máx={a.max():+.2f}  TECU")
    if todos_ctrl:
        base = pd.concat(todos_ctrl)
        # teste simples: a anomalia do evento excede a distribuição dos controles?
        pct = (base < ev.max()).mean() * 100
        print(f"\n  O pico do evento é maior que {pct:.0f}% dos valores de controle.")
        print("  >>> Só é EVIDÊNCIA se o evento se destacar CLARAMENTE dos controles.")
        print("  >>> Se ficar dentro da faixa dos controles, TEC não discrimina o toró.")

# ----------------------------------------------------------------------
# 4) (OPCIONAL) PWV troposférico da RBMC — mesmo esqueleto
# ----------------------------------------------------------------------
def carregar_pwv(caminho_ztd):
    """Lê ZTD/PWV processado (de RINEX RBMC via GAMIT/GipsyX, ou produto IGS).
    Espera colunas: tempo, estacao, pwv_mm. Retorna média na caixa."""
    df = pd.read_csv(caminho_ztd, sep=None, engine="python")
    df.columns = [c.strip().lower() for c in df.columns]
    df["tempo"] = pd.to_datetime(df["tempo"])
    return df.groupby("tempo", as_index=False)["pwv_mm"].mean()

# ----------------------------------------------------------------------
# 5) PLOTAR: TEC + PWV + marcos solares + torós
# ----------------------------------------------------------------------
def plotar(tec_ev, marcos, eventos, pwv=None, saida="gnss_tec_pwv.png"):
    fig, ax = plt.subplots(2 if pwv is not None else 1, 1, figsize=(13, 8), sharex=True)
    axs = np.atleast_1d(ax)
    axs[0].plot(tec_ev.tempo, tec_ev.tec_anom, color="darkred", lw=1.2,
                label="Anomalia de TEC na caixa AMAS/RS")
    axs[0].axhline(0, color="gray", ls=":", lw=0.5)
    axs[0].set_ylabel("Anomalia TEC (TECU)")
    axs[0].legend(fontsize=8)
    if pwv is not None:
        axs[1].plot(pwv.tempo, pwv.pwv_mm, color="teal", lw=1.2, label="PWV (mm)")
        axs[1].set_ylabel("PWV (mm)"); axs[1].legend(fontsize=8)
    for a in axs:
        for t, lab, cor in marcos:
            a.axvline(pd.to_datetime(t), color=cor, lw=1.3, alpha=0.7)
        for ev in eventos:
            a.axvline(pd.to_datetime(ev[0]), color="green", lw=2, ls="--")
    axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %Hh"))
    axs[0].set_title("Cadeia GNSS: TEC (ionosfera) + PWV (troposfera) vs. marcos solares e torós")
    plt.tight_layout(); plt.savefig(saida, dpi=150)
    print("Figura salva:", saida)

MARCOS = [
    ("2024-05-08 22:36", "CME lançado", "orange"),
    ("2024-05-10 17:05", "CME chega (SSC)", "red"),
    ("2024-05-11 03:00", "GLE74", "blue"),
]

if __name__ == "__main__":
    print(f"Caixa: {ALVO_BOX}\nEvento: {JANELA_EVENTO}")
    try:
        tec = baixar_tec_embrace(JANELA_EVENTO["ini"], JANELA_EVENTO["fim"], ALVO_BOX)
        tec = anomalia_tec(tec)
        ctrls = []
        for j in JANELAS_CONTROLE:
            c = baixar_tec_embrace(j["ini"], j["fim"], ALVO_BOX)
            ctrls.append(anomalia_tec(c))
        comparar_evento_controle(tec, ctrls)
        plotar(tec, MARCOS, EVENTOS_TORO)
        # exporta p/ a pilha do 09 (camada região F):
        tec[["tempo", "tec_anom"]].to_csv("anomalia_tec_evento.csv", index=False)
        print("CSV p/ o 09 salvo: anomalia_tec_evento.csv "
              "(use: python 09_coluna_jz.py --tec anomalia_tec_evento.csv)")
    except NotImplementedError as e:
        print("\n!! PASSO MANUAL NECESSÁRIO:", e)
        print("   1) Vá ao portal EMBRACE, baixe o TECMAP do período.")
        print("   2) Aponte LER_TEC_LOCAL para o arquivo e rode de novo.")
    except Exception as e:
        print("!! Rode na sua máquina (internet + dados EMBRACE/RBMC):", e)
