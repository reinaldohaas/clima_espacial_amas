#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rodar_tudo.py
=============
BATCH: roda a cadeia completa do caso EOCE (chuvas 27/04-03/05/2024).

Passos (--listar mostra sem rodar; --so/-s escolhe; --pular exclui):
  01  séries espaciais unificadas (GCR+Kp+Dst+AE+Ey+TEC)     [leve]
  04  sondagens + Rosenfeld/BTD nas 7 datas de chuva         [PESADO: GOES]
  05  série no alvo + mapas IR municipais (27/04-04/05)      [PESADO: GOES]
  07  colapsos de topo na noite do toró (01-02/05)           [PESADO: GOES]
      (--completo estende ao período de chuva inteiro, passo 30 min)
  08  cicatrizes Sentinel-2 (antes ~22/04 x depois 03-09/05) [PESADO: S2]
  10  VPI ERA5 dias de chuva + 12/05 (precisa chave CDS)     [moderado]
  11  verificação sísmica RSBR/USP + SIGMINE (27/04-15/05)   [leve]

Cada passo continua mesmo se o anterior falhar; o resumo final diz o que
deu certo. Log completo em resultados/log_rodada.txt.
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parents[1]
PY = sys.executable

def montar_passos(a):
    datas_chuva = ["2024-04-27", "2024-04-28", "2024-04-29", "2024-04-30",
                   "2024-05-01", "2024-05-02", "2024-05-03"]
    passos = [
        ("01", "Séries espaciais unificadas (GCR+Kp+Dst+AE+Ey+TEC)",
         [PY, "toro_01_series_espaciais.py"]),
        ("04", "Sondagens + Rosenfeld/BTD nas datas de chuva",
         [PY, "toro_04_diagnostico_sondagem_satelite.py",
          "--datas", *datas_chuva,
          "--nome", "EOCE_27abr-03mai",
          "--goes-horas", "06:00", "15:00", "21:00",
          "--sem-timeline", "--sem-tec"]),   # 01 e 03 já rodam sozinhos
        ("05", "Série no alvo + mapas IR (27/04-04/05)",
         [PY, "toro_05_serie_alvo.py",
          "--ini", "2024-04-27 00:00", "--fim", "2024-05-04 00:00",
          "--nome", "EOCE_27abr-03mai"]),
        ("07", "Colapsos de topo — noite do toró",
         [PY, "toro_07_colapso_topo.py",
          "--ini", "2024-05-01 18:00", "--fim", "2024-05-03 06:00",
          "--nome", "EOCE_toro"] if not a.completo else
         [PY, "toro_07_colapso_topo.py",
          "--ini", "2024-04-27 00:00", "--fim", "2024-05-04 00:00",
          "--passo-min", "30", "--nome", "EOCE_27abr-03mai"]),
        ("08", "Cicatrizes Sentinel-2 (antes ~22/04 x depois 03-09/05)",
         [PY, "toro_08_cicatrizes_sentinel2.py",
          "--antes-ini", "2024-04-12", "--antes-fim", "2024-04-26",
          "--depois-ini", "2024-05-03", "--depois-fim", "2024-05-09",
          "--nome", "cicatrizes_EOCE_27abr-03mai"]),
        ("10", "VPI ERA5 (dias de chuva + 12/05 p/ comparação)",
         [PY, "toro_10_vpi_era5.py",
          "--datas", *datas_chuva, "2024-05-12",
          "--horas", "00", "12", "--nome", "VPI_EOCE"]),
        ("11", "Verificação sísmica RSBR/USP + SIGMINE",
         [PY, "toro_11_verificacao_sismica.py",
          "--ini", "2024-04-27", "--fim", "2024-05-15"]),
    ]
    return passos

def cmd_09():
    cmd = [PY, "09_coluna_jz.py", "--ini", "2024-04-20", "--fim", "2024-05-16"]
    tec = AQUI / "anomalia_tec_evento.csv"
    if tec.exists():
        cmd += ["--tec", str(tec)]
    return cmd

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("--listar", action="store_true", help="mostra e sai")
    ap.add_argument("--so", nargs="+", default=None,
                    help="roda só estes passos (ex.: --so 05 07)")
    ap.add_argument("--pular", nargs="+", default=[],
                    help="pula estes passos (ex.: --pular 08 10)")
    ap.add_argument("--completo", action="store_true",
                    help="07 no período de chuva inteiro (MUITO pesado)")
    a = ap.parse_args()

    passos = montar_passos(a)
    if a.listar:
        for pid, desc, cmd in passos:
            c = cmd or cmd_09()
            print(f"[{pid}] {desc}\n     {' '.join(c[1:])}")
        return

    (AQUI / "resultados").mkdir(exist_ok=True)
    log = (AQUI / "resultados" / "log_rodada.txt").open("a", encoding="utf-8")
    log.write(f"\n===== RODADA {datetime.now():%Y-%m-%d %H:%M} =====\n")

    resumo = []
    for pid, desc, cmd in passos:
        if a.so and pid not in a.so:
            continue
        if pid in a.pular:
            resumo.append((pid, desc, "PULADO", 0))
            continue
        if cmd is None:
            cmd = cmd_09()
        print(f"\n{'='*70}\n[{pid}] {desc}\n{'='*70}")
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=AQUI, text=True,
                               capture_output=True, timeout=4 * 3600)
            dt = time.time() - t0
            log.write(f"\n--- [{pid}] {desc} ({dt:.0f}s) ---\n")
            log.write(r.stdout + "\n" + r.stderr + "\n")
            print(r.stdout[-2000:])
            if r.returncode == 0:
                resumo.append((pid, desc, "OK", dt))
            else:
                print(r.stderr[-1500:])
                resumo.append((pid, desc, "FALHOU", dt))
        except subprocess.TimeoutExpired:
            resumo.append((pid, desc, "TIMEOUT 4h", time.time() - t0))
        except Exception as e:
            resumo.append((pid, desc, f"ERRO: {e}", time.time() - t0))
    log.close()

    print(f"\n{'='*70}\nRESUMO DA RODADA\n{'='*70}")
    for pid, desc, st, dt in resumo:
        print(f"  [{pid}] {st:12s} {dt/60:6.1f} min  {desc}")
    print("\nLog completo: resultados/log_rodada.txt")

if __name__ == "__main__":
    main()
