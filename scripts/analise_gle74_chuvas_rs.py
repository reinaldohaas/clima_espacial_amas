import os
import sys
import datetime
import urllib.request
import re
import concurrent.futures
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Configuração de diretórios
BASE_DIR = r"C:\Users\haas\github\clima_espacial_amas"
DATA_DIR = os.path.join(BASE_DIR, "dados")
PLOT_DIR = os.path.join(BASE_DIR, "resultados/graficos")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

print(f"Diretório base: {BASE_DIR}")
print(f"Diretório de dados: {DATA_DIR}")
print(f"Diretório de gráficos: {PLOT_DIR}\n")

# Estação mais próxima de Bento Gonçalves - RS: São Martinho da Serra (SMS - RS)
# Coordenadas Bento Gonçalves: -29.17° S, -51.52° W
# Coordenadas Observatório SMS (INPE): -29.44° S, -53.82° W (~200 km)

start_date = datetime.date(2024, 4, 15)
end_date = datetime.date(2024, 5, 25)
num_days = (end_date - start_date).days + 1
date_list = [start_date + datetime.timedelta(days=i) for i in range(num_days)]

def download_file(url, filepath):
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read().decode('utf-8', errors='ignore')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
    except Exception:
        pass

tasks = []

# A) Magnetômetro SMS
for dt in date_list:
    month_str = dt.strftime("%b").lower()
    day_str = dt.strftime("%d")
    filename = f"sms{day_str}{month_str}.24m"
    url = f"https://embracedata.inpe.br/magnetometer/SMS/2024/{filename}"
    filepath = os.path.join(DATA_DIR, filename)
    tasks.append((url, filepath))

# B) Índice KSA
for dt in date_list:
    dt_str = dt.strftime("%Y-%m-%d")
    filename = f"ksa_{dt_str}.txt"
    url = f"https://embracedata.inpe.br/ksa/2024/{dt_str}.txt"
    filepath = os.path.join(DATA_DIR, filename)
    tasks.append((url, filepath))

# C) GOES-16
goes_dates = [datetime.date(2024, 5, d) for d in range(8, 16)]
for dt in goes_dates:
    dt_str = dt.strftime("%Y%m%d")
    filename = f"{dt_str}_Gr_xr_1m.txt"
    url = f"https://embracedata.inpe.br/goes/GOES-16/2024/{filename}"
    filepath = os.path.join(DATA_DIR, filename)
    tasks.append((url, filepath))

print(f"Baixando {len(tasks)} arquivos em paralelo do EMBRACE/INPE...")
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
    executor.map(lambda t: download_file(t[0], t[1]), tasks)

print("Download concluído. Processando dados...")

# Carregar Magnetômetro SMS
sms_mag_data = []
for dt in date_list:
    month_str = dt.strftime("%b").lower()
    day_str = dt.strftime("%d")
    filename = f"sms{day_str}{month_str}.24m"
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or 'DD MM YYYY' in line or 'SAO MARTINHO' in line or not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 8:
                    try:
                        d, m, y, hh, mm = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                        h_val = float(parts[6])
                        z_val = float(parts[7])
                        f_val = float(parts[9]) if len(parts) > 9 else np.nan
                        dt_obj = datetime.datetime(y, m, d, hh, mm)
                        sms_mag_data.append({'datetime': dt_obj, 'H_nT': h_val, 'Z_nT': z_val, 'F_nT': f_val})
                    except ValueError:
                        continue

df_mag = pd.DataFrame(sms_mag_data)
if not df_mag.empty:
    df_mag = df_mag.sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True)

# Carregar KSA
ksa_data = []
for dt in date_list:
    dt_str = dt.strftime("%Y-%m-%d")
    filename = f"ksa_{dt_str}.txt"
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        dt_obj = datetime.datetime.fromisoformat(parts[0])
                        k_str = parts[1]
                        k_num = float(k_str[0])
                        if len(k_str) > 1:
                            if k_str[1] == '+': k_num += 0.33
                            elif k_str[1] == '-': k_num -= 0.33
                        ksa_data.append({'datetime': dt_obj, 'K_index': k_num, 'K_str': k_str})
                    except Exception:
                        continue

df_ksa = pd.DataFrame(ksa_data)
if not df_ksa.empty:
    df_ksa = df_ksa.sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True)

print(f"Registros carregados: Magnetômetro SMS = {len(df_mag)}, Índice KSA = {len(df_ksa)}")

# ---------------------------------------------------------
# GERAÇÃO DOS GRÁFICOS
# ---------------------------------------------------------
print("Gerando gráficos...")

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

color_mag = '#1f77b4'

# Painel 1
if not df_mag.empty:
    ax1.plot(df_mag['datetime'], df_mag['H_nT'], color=color_mag, linewidth=1.2, label='Campo Magnético H (nT) - SMS/RS')
    ax1.set_ylabel('Campo H (nT)', fontsize=11, fontweight='bold', color=color_mag)
    ax1.set_title('Análise Temporal: Tempestade Solar GLE 74 & Enchentes no RS (Abril/Maio 2024)\nObservatório Espacial de São Martinho da Serra - RS (Mais próximo de Bento Gonçalves)', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.axvspan(datetime.datetime(2024, 5, 10, 12, 0), datetime.datetime(2024, 5, 12, 12, 0), color='red', alpha=0.18, label='GLE 74 / Tempestade G5')
    ax1.legend(loc='upper left', frameon=True)

# Painel 2
if not df_ksa.empty:
    colors = ['#2ca02c' if k < 5 else ('#ff7f0e' if k < 7 else '#d62728') for k in df_ksa['K_index']]
    ax2.bar(df_ksa['datetime'], df_ksa['K_index'], width=0.1, color=colors, alpha=0.85, label='Índice KSA (América do Sul)')
    ax2.set_ylabel('Índice KSA', fontsize=11, fontweight='bold')
    ax2.set_ylim(0, 9.5)
    ax2.axhline(5, color='orange', linestyle='--', linewidth=1, label='Tempestade Geomagnética (K>=5)')
    ax2.axhline(9, color='red', linestyle='--', linewidth=1.5, label='Tempestade Extrema G5 (K=9)')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper left', frameon=True)

# Painel 3: Cronograma de Eventos
ax3.set_ylabel('Eventos RS 2024', fontsize=11, fontweight='bold')
ax3.axvspan(datetime.datetime(2024, 4, 27), datetime.datetime(2024, 5, 15), color='#0066cc', alpha=0.25, label='Período de Chuvas Intensas / Enchentes no RS')
ax3.axvspan(datetime.datetime(2024, 4, 29), datetime.datetime(2024, 5, 3), color='#003399', alpha=0.35, label='Pico das Precipitações na Serra Gaúcha (Bento Gonçalves)')
ax3.axvspan(datetime.datetime(2024, 5, 10, 18, 0), datetime.datetime(2024, 5, 12, 6, 0), color='#cc0000', alpha=0.5, label='Pico GLE 74 & Tempestade Geomagnética G5 (10-11/Maio)')

ax3.set_yticks([])
ax3.legend(loc='upper left', frameon=True, fontsize=10)
ax3.grid(True, linestyle='--', alpha=0.6)

ax3.xaxis.set_major_locator(mdates.DayLocator(interval=2))
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%d/%b'))
plt.xticks(rotation=45, ha='right', fontsize=10)
plt.xlabel('Data (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

plot_file1 = os.path.join(PLOT_DIR, "gle74_vs_chuvas_rs_2024.png")
plt.savefig(plot_file1, dpi=300, bbox_inches='tight')
plt.close()
print(f"Gráfico 1 salvo: {plot_file1}")

# Zoom GLE 74
fig2, (ax_g1, ax_g2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
df_mag_zoom = df_mag[(df_mag['datetime'] >= datetime.datetime(2024, 5, 8)) & (df_mag['datetime'] <= datetime.datetime(2024, 5, 15))]

if not df_mag_zoom.empty:
    ax_g1.plot(df_mag_zoom['datetime'], df_mag_zoom['H_nT'], color='#1f77b4', linewidth=1.5, label='Campo H (nT) em São Martinho da Serra/RS')
    ax_g1.set_ylabel('Campo H (nT)', fontsize=11, fontweight='bold', color='#1f77b4')
    ax_g1.set_title('Detalhamento da Tempestade Solar GLE 74 (08 a 15 de Maio de 2024)', fontsize=13, fontweight='bold', pad=12)
    ax_g1.grid(True, linestyle='--', alpha=0.6)
    ax_g1.axvspan(datetime.datetime(2024, 5, 10, 21, 0), datetime.datetime(2024, 5, 11, 18, 0), color='red', alpha=0.2, label='Intervalo da Tempestade Extrema G5 & GLE 74')
    ax_g1.legend(loc='lower left', frameon=True)

df_ksa_zoom = df_ksa[(df_ksa['datetime'] >= datetime.datetime(2024, 5, 8)) & (df_ksa['datetime'] <= datetime.datetime(2024, 5, 15))]
if not df_ksa_zoom.empty:
    colors_zoom = ['#2ca02c' if k < 5 else ('#ff7f0e' if k < 7 else '#d62728') for k in df_ksa_zoom['K_index']]
    ax_g2.bar(df_ksa_zoom['datetime'], df_ksa_zoom['K_index'], width=0.08, color=colors_zoom, alpha=0.85, label='Índice KSA (K-index RS/América do Sul)')
    ax_g2.set_ylabel('Índice KSA', fontsize=11, fontweight='bold')
    ax_g2.set_ylim(0, 9.5)
    ax_g2.axhline(9, color='red', linestyle='--', linewidth=1.5, label='Nível K=9 (Tempestade Geomagnética G5)')
    ax_g2.grid(True, linestyle='--', alpha=0.6)
    ax_g2.legend(loc='upper left', frameon=True)

ax_g2.xaxis.set_major_locator(mdates.HourLocator(interval=12))
ax_g2.xaxis.set_major_formatter(mdates.DateFormatter('%d/%b %H:00'))
plt.xticks(rotation=45, ha='right', fontsize=10)
plt.xlabel('Data / Hora UTC (Maio de 2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

plot_file2 = os.path.join(PLOT_DIR, "zoom_gle74_maio2024.png")
plt.savefig(plot_file2, dpi=300, bbox_inches='tight')
plt.close()
print(f"Gráfico 2 salvo: {plot_file2}")
print("\nProcesso concluído com sucesso!")
