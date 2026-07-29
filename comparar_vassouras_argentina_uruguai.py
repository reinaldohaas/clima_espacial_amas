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

BASE_DIR = r"C:\Users\haas\github\clima_espacial_amas"
DATA_DIR_2023 = os.path.join(BASE_DIR, "dados_2023_completo")
DATA_DIR_2024 = os.path.join(BASE_DIR, "dados_2024_completo")
PLOT_DIR = os.path.join(BASE_DIR, "graficos")

os.makedirs(DATA_DIR_2023, exist_ok=True)
os.makedirs(DATA_DIR_2024, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

print("=========================================================================")
print("  COMPARATIVO DE VASSOURAS (VSS) COM AS ESTAÇÕES DAS FRONTEIRAS DE")
print("  ARGENTINA E URUGUAI (RGA, CHI, SMS, MED) — 2023 & 2024")
print("=========================================================================\n")

stations = ['VSS', 'RGA', 'CHI', 'SMS', 'MED', 'SJC']

def insert_time_gaps(df, max_gap_minutes=60):
    if df.empty: return df
    df = df.sort_values('datetime').reset_index(drop=True)
    time_diffs = df['datetime'].diff()
    gap_indices = df.index[time_diffs > datetime.timedelta(minutes=max_gap_minutes)].tolist()
    new_rows = []
    for idx in gap_indices:
        prev_dt = df.loc[idx - 1, 'datetime']
        gap_dt = prev_dt + datetime.timedelta(minutes=1)
        row = {col: np.nan for col in df.columns}
        row['datetime'] = gap_dt
        new_rows.append(row)
    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)]).sort_values('datetime').reset_index(drop=True)
    return df

def parse_station_year(st_name, year_str, data_dir, ext, min_h, max_h):
    recs = []
    num_days = 366 if year_str == '2024' else 365
    start_dt = datetime.date(int(year_str), 1, 1)
    d_list = [start_dt + datetime.timedelta(days=i) for i in range(num_days)]
    
    for dt in d_list:
        month_str = dt.strftime("%b").lower()
        day_str = dt.strftime("%d")
        filepath = os.path.join(data_dir, f"{st_name.lower()}{day_str}{month_str}.{ext}")
        if os.path.exists(filepath) and os.path.getsize(filepath) > 50:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('#') or 'DD MM YYYY' in line or 'EMBRACE' in line or not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) >= 8:
                        try:
                            d, m, y, hh, mm = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                            h_val = float(parts[6])
                            if min_h <= h_val <= max_h:
                                dt_obj = datetime.datetime(y, m, d, hh, mm)
                                recs.append({'datetime': dt_obj, 'H': h_val})
                        except ValueError:
                            continue
    df = pd.DataFrame(recs)
    if not df.empty:
        df = df.drop_duplicates('datetime').sort_values('datetime').reset_index(drop=True)
        df['H_median'] = df['H'].rolling(window=15, center=True, min_periods=1).median()
        df = df[abs(df['H'] - df['H_median']) < 250].drop(columns=['H_median'])
        df = insert_time_gaps(df, max_gap_minutes=60)
    return df

print(" Carregando dados de 2023...")
df_vss_23 = parse_station_year('VSS', '2023', DATA_DIR_2023, '23m', 17500, 19000)
df_rga_23 = parse_station_year('RGA', '2023', DATA_DIR_2023, '23m', 19000, 20500)
df_chi_23 = parse_station_year('CHI', '2023', DATA_DIR_2023, '23m', 18800, 20000)
df_sms_23 = parse_station_year('SMS', '2023', DATA_DIR_2023, '23m', 16500, 17600)

print(" Carregando dados de 2024...")
df_vss_24 = parse_station_year('VSS', '2024', DATA_DIR_2024, '24m', 17500, 19000)
df_rga_24 = parse_station_year('RGA', '2024', DATA_DIR_2024, '24m', 19000, 20500)
df_chi_24 = parse_station_year('CHI', '2024', DATA_DIR_2024, '24m', 18800, 20000)
df_sms_24 = parse_station_year('SMS', '2024', DATA_DIR_2024, '24m', 16500, 17600)

# Estimativa representativa de Pilar / Tucumán (Argentina) com base em RGA/SMS
# Tucumán (TUC) fica a Lat -26.85°, Lon -65.23° (Argentina)
# Pilar (PIL) fica a Lat -31.67°, Lon -63.88° (Córdoba, Argentina)
# Baseline típica de H em Pilar/Tucumán = ~19.800 nT a 21.000 nT

# ---------------------------------------------------------
# PLOTAGEM COMPARATIVA 2024: VASSOURAS VS ARGENTINA / URUGUAI
# ---------------------------------------------------------
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 12), sharex=True)

# 1. Vassouras (VSS / RJ) em 2024
if not df_vss_24.empty:
    ax1.plot(df_vss_24['datetime'], df_vss_24['H'], color='#1f77b4', linewidth=1, label='Vassouras (VSS - RJ) [Sudeste / INTERMAGNET - ON]')
    ax1.set_ylabel('VSS H (nT)', fontsize=10, fontweight='bold', color='#1f77b4')
    ax1.set_title('Comparativo de Vassouras (VSS) com as Estações das Fronteiras de Argentina e Uruguai (2024)', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right', frameon=True)

# 2. Rio Grande (RGA / Fronteira Argentina-Brasil) em 2024
if not df_rga_24.empty:
    ax2.plot(df_rga_24['datetime'], df_rga_24['H'], color='#d62728', linewidth=1, label='Rio Grande (RGA - RS) [Fronteira Argentina / Cone Sul]')
    ax2.set_ylabel('RGA H (nT)', fontsize=10, fontweight='bold', color='#d62728')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper right', frameon=True)

# 3. Chuí (CHI / Fronteira Uruguai-Brasil) em 2024
if not df_chi_24.empty:
    ax3.plot(df_chi_24['datetime'], df_chi_24['H'], color='#9467bd', linewidth=1, label='Chuí (CHI - RS) [Fronteira com Uruguai]')
    ax3.set_ylabel('CHI H (nT)', fontsize=10, fontweight='bold', color='#9467bd')
    ax3.grid(True, linestyle='--', alpha=0.6)
    ax3.legend(loc='upper right', frameon=True)

# 4. São Martinho da Serra (SMS / RS) em 2024
if not df_sms_24.empty:
    ax4.plot(df_sms_24['datetime'], df_sms_24['H'], color='#2ca02c', linewidth=1, label='São Martinho da Serra (SMS - RS) [Próximo a Bento Gonçalves]')
    ax4.set_ylabel('SMS H (nT)', fontsize=10, fontweight='bold', color='#2ca02c')
    ax4.grid(True, linestyle='--', alpha=0.6)
    ax4.legend(loc='upper right', frameon=True)

for ax in [ax1, ax2, ax3, ax4]:
    ax.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.22, label='Tempestade G4 (23-25/Mar)')
    ax.axvspan(datetime.datetime(2024, 4, 19), datetime.datetime(2024, 4, 21), color='#e377c2', alpha=0.25)
    ax.axvspan(datetime.datetime(2024, 4, 27), datetime.datetime(2024, 5, 15), color='#0066cc', alpha=0.2, label='Chuvas RS')
    ax.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35, label='Supertempestade G5 / GLE 74')

ax4.xaxis.set_major_locator(mdates.MonthLocator())
ax4.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.xlabel('Mês (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot_2024 = os.path.join(PLOT_DIR, "comparativo_vassouras_vs_fronteira_argentina_uruguai_2024.png")
plt.savefig(file_plot_2024, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico comparativo de 2024 salvo em: {file_plot_2024}")

# ---------------------------------------------------------
# PLOTAGEM NORMALIZADA ΔH DA FRONTEIRA ARGENTINA/URUGUAI VS VASSOURAS
# ---------------------------------------------------------
fig, ax = plt.subplots(figsize=(15, 6))

if not df_vss_24.empty:
    vss_base = df_vss_24['H'].rolling(window=1440, center=True, min_periods=60).median()
    vss_delta = df_vss_24['H'] - vss_base
    ax.plot(df_vss_24['datetime'], vss_delta, color='#1f77b4', linewidth=1, label='Vassouras (VSS/RJ) — ΔH (nT)')

if not df_rga_24.empty:
    rga_base = df_rga_24['H'].rolling(window=1440, center=True, min_periods=60).median()
    rga_delta = df_rga_24['H'] - rga_base
    ax.plot(df_rga_24['datetime'], rga_delta, color='#d62728', linewidth=0.9, alpha=0.85, label='Rio Grande / Fronteira Argentina (RGA) — ΔH (nT)')

if not df_sms_24.empty:
    sms_base = df_sms_24['H'].rolling(window=1440, center=True, min_periods=60).median()
    sms_delta = df_sms_24['H'] - sms_base
    ax.plot(df_sms_24['datetime'], sms_delta, color='#2ca02c', linewidth=0.9, alpha=0.85, label='São Martinho da Serra (SMS/RS) — ΔH (nT)')

ax.set_ylabel('Anomalia Magnética Normalizada ΔH (nT)', fontsize=11, fontweight='bold')
ax.set_title('Perturbação Magnética Normalizada ΔH (nT): Vassouras vs Fronteira Argentina/Uruguai (2024)\nProvação do Alinhamento Global da Corrente de Anel em Toda a América do Sul', fontsize=13, fontweight='bold', pad=12)
ax.grid(True, linestyle='--', alpha=0.6)
ax.legend(loc='upper right', frameon=True)

ax.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.22, label='Tempestade G4')
ax.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35, label='Supertempestade G5')

ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.xlabel('Mês (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot_delta = os.path.join(PLOT_DIR, "perturbacao_normalizada_vassouras_vs_argentina_2024.png")
plt.savefig(file_plot_delta, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico normalizado ΔH salvo em: {file_plot_delta}")
