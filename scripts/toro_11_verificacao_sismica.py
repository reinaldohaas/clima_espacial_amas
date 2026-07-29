#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
11_verificacao_sismica.py
=========================
VERIFICAÇÃO SÍSMICA DE EVENTOS CANDIDATOS — catálogo RSBR/USP (FDSN).

Protocolo: todo relato de estrondo/tremor associado a um sítio candidato
deve ser confrontado com o catálogo do Centro de Sismologia da USP
(moho.iag.usp.br/fdsnws/event/1/query), extraindo tempo de origem UTC,
epicentro, profundidade e magnitude.

TRÊS RESSALVAS OBRIGATÓRIAS (aplicadas evento a evento):
  (i)   magnitudes preliminares diferem das revisadas — a magnitude aqui é
        a do catálogo no momento da consulta; confirmar no boletim revisado;
  (ii)  com estações a >70 km, a incerteza de localização é de 7-14 km e a
        profundidade tipicamente NÃO é constrangida (fixada — aparece 0.0);
  (iii) desmonte de rocha em mineração produz sinal semelhante — excluir
        por consulta a lavras ativas (SIGMINE/ANM) dentro da elipse de
        incerteza e por registro de fogo.

UM EVENTO NÃO DISCRIMINADO NÃO CONSTITUI EVIDÊNCIA.

Uso:
  python 11_verificacao_sismica.py                       # 27/04-15/05, corredor
  python 11_verificacao_sismica.py --ini 2024-05-12 --fim 2024-05-14
  python 11_verificacao_sismica.py --relatos relatos.csv # confronta relatos
  python 11_verificacao_sismica.py --sem-sigmine         # pula ANM (offline)

relatos.csv (opcional): colunas  quando_local,lat,lon,descricao
  ex.: 2024-05-13 03:05,-29.21,-51.15,"estrondo ouvido em Caxias"
Saída: resultados/sismica/serie/eventos_sismicos.csv + relatorio_sismica.md
"""

import argparse
import csv
import importlib.util
import io
import json
import pathlib
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

spec = importlib.util.spec_from_file_location(
    "caso", pathlib.Path(__file__).parent / "toro_00_caso.py")
caso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(caso)

FDSN = "https://moho.iag.usp.br/fdsnws/event/1/query"
SIGMINE = ("https://geo.anm.gov.br/arcgis/rest/services/SIGMINE/"
           "dados_anm/MapServer/0/query")
# fases da ANM que indicam lavra potencialmente ativa (com fogo)
FASES_LAVRA = ("CONCESSÃO DE LAVRA", "LAVRA GARIMPEIRA",
               "LICENCIAMENTO", "REGISTRO DE EXTRAÇÃO")
UTC_LOCAL = -3            # RS, sem horário de verão em 2024
INCERTEZA_KM = 14.0       # raio conservador da elipse (estações >70 km)
JANELA_FOGO = (9, 18)     # hora local típica de desmonte com explosivo
TOL_RELATO_MIN = 30       # casamento relato x origem (min)


def _http(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "eventos-toro/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def consulta_fdsn(ini, fim, bbox):
    """Consulta o catálogo USP (format=text). Retorna lista de dicts.
    ATENÇÃO (bug do servidor): endtime com HH:MM:SS != 00:00:00 retorna
    VAZIO silenciosamente — por isso usamos 00:00 do dia seguinte."""
    fim_mais1 = (datetime.fromisoformat(fim) + timedelta(days=1)
                 ).strftime("%Y-%m-%d")
    q = dict(starttime=f"{ini}T00:00:00", endtime=f"{fim_mais1}T00:00:00",
             minlongitude=bbox[0], minlatitude=bbox[1],
             maxlongitude=bbox[2], maxlatitude=bbox[3], format="text")
    url = FDSN + "?" + urllib.parse.urlencode(q)
    print(f">> FDSN: {url}")
    try:
        txt = _http(url)
    except Exception as e:
        raise SystemExit(f"!! Falha na consulta FDSN ({e}). "
                         "Sem catálogo não há verificação — aborto.")
    evs = []
    rd = csv.reader(io.StringIO(txt), delimiter="|")
    for row in rd:
        if not row or row[0].startswith("#") or len(row) < 14:
            continue
        evs.append(dict(
            id=row[0], t_utc=row[1][:23], lat=float(row[2]), lon=float(row[3]),
            prof_km=float(row[4]), autor=row[5], magtipo=row[9],
            mag=float(row[10]) if row[10] else float("nan"),
            local=row[12], tipo=row[13]))
    return evs


def lavras_na_elipse(lat, lon, raio_km, timeout=60):
    """SIGMINE/ANM: processos em fase de lavra num raio (m) do epicentro.
    Retorna (lista de dicts) ou None se o serviço falhar (≠ lista vazia!)."""
    fases = ",".join(f"'{f}'" for f in FASES_LAVRA)
    q = dict(geometry=f"{lon},{lat}", geometryType="esriGeometryPoint",
             inSR=4326, distance=int(raio_km * 1000), units="esriSRUnit_Meter",
             spatialRel="esriSpatialRelIntersects",
             where=f"FASE IN ({fases})",
             outFields="PROCESSO,NOME,SUBS,FASE,USO", returnGeometry="false",
             f="json")
    try:
        d = json.loads(_http(SIGMINE + "?" + urllib.parse.urlencode(q), timeout))
        if "error" in d:
            return None
        return [ft["attributes"] for ft in d.get("features", [])]
    except Exception:
        return None


def discriminar(ev, lavras, hora_local):
    """Aplica as ressalvas (ii) e (iii). Retorna (veredito, motivos[])."""
    motivos = []
    if ev["prof_km"] == 0.0:
        motivos.append("profundidade fixada (não constrangida)")
    motivos.append(f"incerteza de localização 7-{INCERTEZA_KM:.0f} km "
                   "(estações >70 km)")
    diurno = JANELA_FOGO[0] <= hora_local.hour < JANELA_FOGO[1]
    if lavras is None:
        motivos.append("SIGMINE indisponível — desmonte NÃO excluído")
        return "NÃO DISCRIMINADO", motivos
    if lavras:
        nomes = "; ".join(f"{l.get('NOME') or l.get('PROCESSO')} "
                          f"({l.get('FASE')}, {l.get('SUBS')})"
                          for l in lavras[:5])
        motivos.append(f"{len(lavras)} lavra(s) na elipse: {nomes}")
        if diurno:
            motivos.append(f"origem em horário típico de fogo "
                           f"({hora_local:%H:%M} local)")
            return "POSSÍVEL DESMONTE", motivos
        motivos.append(f"origem fora do horário típico de fogo "
                       f"({hora_local:%H:%M} local) — mas conferir "
                       "registro de fogo da(s) lavra(s)")
        return "NÃO DISCRIMINADO", motivos
    motivos.append("nenhuma lavra ativa na elipse de incerteza")
    return "TECTÔNICO PROVÁVEL", motivos


def carregar_relatos(arq):
    rel = []
    with open(arq, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rel.append(dict(
                quando=datetime.fromisoformat(row["quando_local"].strip()),
                lat=float(row["lat"]), lon=float(row["lon"]),
                desc=row.get("descricao", "").strip()))
    return rel


def main():
    ap = argparse.ArgumentParser(description="Verificação sísmica RSBR/USP")
    ap.add_argument("--ini", default="2024-04-27")
    ap.add_argument("--fim", default="2024-05-15")
    ap.add_argument("--folga-km", type=float, default=60.0,
                    help="folga do bbox em torno do rio (padrão 60 km — os "
                         "sismos de Caxias de 13/05 ficam a 26-32 km do rio; "
                         "25 km os deixava FORA da caixa)")
    ap.add_argument("--relatos", default=None,
                    help="CSV de relatos (quando_local,lat,lon,descricao)")
    ap.add_argument("--sem-sigmine", action="store_true",
                    help="não consulta a ANM (eventos ficam NÃO DISCRIMINADOS)")
    ap.add_argument("--sobrescrever", action="store_true",
                    help="permite substituir uma saída COM eventos por uma vazia")
    a = ap.parse_args()

    bbox = caso.bbox_corredor(a.folga_km)
    evs = consulta_fdsn(a.ini, a.fim, bbox)
    print(f">> {len(evs)} evento(s) no catálogo USP "
          f"{a.ini} a {a.fim}, bbox {[round(x, 2) for x in bbox]}")

    relatos = carregar_relatos(a.relatos) if a.relatos else []
    out = caso.pasta_saida("sismica")
    linhas_md = [
        "# Verificação sísmica — catálogo RSBR/USP (FDSN)",
        "",
        f"Período {a.ini} a {a.fim}; corredor Taquari-Antas "
        f"(folga {a.folga_km:.0f} km). Consulta: `{FDSN}`.",
        "",
        "**Ressalvas obrigatórias**: (i) magnitudes abaixo são as do catálogo "
        "no momento da consulta — preliminares diferem das revisadas, "
        "confirmar no boletim; (ii) com estações a >70 km a incerteza de "
        "localização é de 7-14 km e a profundidade tipicamente não é "
        "constrangida (fixada); (iii) desmonte de rocha produz sinal "
        "semelhante — exclusão via SIGMINE/ANM + registro de fogo. "
        "**Um evento não discriminado não constitui evidência.**",
        ""]

    csv_rows = []
    for ev in sorted(evs, key=lambda e: e["t_utc"]):
        t_utc = datetime.fromisoformat(ev["t_utc"])
        t_loc = t_utc + timedelta(hours=UTC_LOCAL)
        d_rio = caso.dist_km_ao_rio(ev["lat"], ev["lon"])
        lavras = (None if a.sem_sigmine else
                  lavras_na_elipse(ev["lat"], ev["lon"], INCERTEZA_KM))
        veredito, motivos = discriminar(ev, lavras, t_loc)

        casados = [r for r in relatos
                   if abs((r["quando"] - t_loc).total_seconds()) / 60
                   <= TOL_RELATO_MIN]

        print(f"\n[{ev['id']}] {ev['t_utc']} UTC ({t_loc:%d/%m %H:%M} local)")
        print(f"   {ev['local']} | {ev['lat']:.4f},{ev['lon']:.4f} | "
              f"prof {ev['prof_km']:.1f} km | {ev['magtipo']} {ev['mag']:.1f} "
              f"| {d_rio:.0f} km do rio")
        print(f"   VEREDITO: {veredito}")
        for m in motivos:
            print(f"     - {m}")
        for r in casados:
            print(f"   RELATO CASADO (±{TOL_RELATO_MIN} min): "
                  f"{r['quando']:%d/%m %H:%M} — {r['desc']}")

        linhas_md += [
            f"## {ev['id']} — {t_loc:%d/%m/%Y %H:%M} local "
            f"({ev['t_utc']} UTC)", "",
            f"- Epicentro: {ev['lat']:.4f}, {ev['lon']:.4f} "
            f"({ev['local']}); {d_rio:.0f} km do rio",
            f"- Profundidade: {ev['prof_km']:.1f} km"
            + (" **(fixada)**" if ev["prof_km"] == 0.0 else ""),
            f"- Magnitude (catálogo): {ev['magtipo']} {ev['mag']:.2f} "
            f"— sujeita a revisão",
            f"- **Veredito: {veredito}**"]
        linhas_md += [f"  - {m}" for m in motivos]
        linhas_md += [f"  - relato casado: {r['quando']:%d/%m %H:%M} — "
                      f"{r['desc']}" for r in casados] + [""]

        csv_rows.append([ev["id"], ev["t_utc"], f"{t_loc:%Y-%m-%d %H:%M}",
                         ev["lat"], ev["lon"], ev["prof_km"],
                         ev["prof_km"] == 0.0, ev["magtipo"],
                         round(ev["mag"], 2), ev["local"], round(d_rio, 1),
                         len(lavras) if lavras is not None else -1,
                         veredito, len(casados)])

    if relatos:
        orfaos = [r for r in relatos if not any(
            abs((r["quando"] - (datetime.fromisoformat(e["t_utc"])
                                + timedelta(hours=UTC_LOCAL))).total_seconds())
            / 60 <= TOL_RELATO_MIN for e in evs)]
        if orfaos:
            linhas_md += ["## Relatos SEM evento no catálogo", "",
                          "Sem origem sísmica catalogada em ±"
                          f"{TOL_RELATO_MIN} min — não constituem evidência "
                          "sísmica.", ""]
            linhas_md += [f"- {r['quando']:%d/%m %H:%M} — {r['desc']}"
                          for r in orfaos] + [""]

    if not evs:
        linhas_md += ["*Nenhum evento no catálogo para o período/região.*", ""]

    fcsv = out / "eventos_sismicos.csv"
    fmd_prev = out / "relatorio_sismica.md"
    if not evs and not a.sobrescrever and fcsv.exists():
        try:
            n_prev = sum(1 for _ in open(fcsv, encoding="utf-8")) - 1
        except Exception:
            n_prev = 0
        if n_prev > 0:
            print(f"\n!! Consulta retornou 0 eventos, mas a saída anterior tem "
                  f"{n_prev} evento(s). MANTENDO os arquivos antigos.\n"
                  "   (use --sobrescrever para substituir mesmo assim)")
            return
    with open(fcsv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "t_utc", "t_local", "lat", "lon", "prof_km",
                    "prof_fixada", "magtipo", "mag_catalogo", "local",
                    "dist_rio_km", "n_lavras_elipse(-1=indisp)",
                    "veredito", "n_relatos_casados"])
        w.writerows(csv_rows)
    fmd = out / "relatorio_sismica.md"
    fmd.write_text("\n".join(linhas_md), encoding="utf-8")
    print(f"\n>> Saídas: {fcsv}\n           {fmd}")


if __name__ == "__main__":
    main()
