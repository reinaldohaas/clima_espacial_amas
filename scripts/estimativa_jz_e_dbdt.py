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
DATA_DIR = os.path.join(BASE_DIR, "dados/magnetometros_2024")
PLOT_DIR = os.path.join(BASE_DIR, "resultados/graficos")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

print("=========================================================================")
print("  ESTIMATIVA DE Jz, dB/dt E CORRENTES INDUZIDAS EM VASSOURAS E REDE SUL")
print("=========================================================================\n")

start_date = datetime.date(2024, 1, 1)
end_date = datetime.date(2024, 12, 31)
num_days = (end_date - start_date).days + 1
date_list = [start_date + datetime.timedelta(days=i) for i in range(num_days)]

def parse_mag_full(st_name, min_h, max_h):
    recs = []
    for dt in date_list:
        month_str = dt.strftime("%b").lower()
        day_str = dt.strftime("%d")
        filepath = os.path.join(DATA_DIR, f"{st_name.lower()}{day_str}{month_str}.24m")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('#') or 'DD MM YYYY' in line or 'EMBRACE' in line or not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) >= 8:
                        try:
                            d, m, y, hh, mm = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                            h_val = float(parts[6]) # H (nT)
                            z_val = float(parts[7]) # Z (nT)
                            if min_h <= h_val <= max_h:
                                dt_obj = datetime.datetime(y, m, d, hh, mm)
                                recs.append({'datetime': dt_obj, 'H': h_val, 'Z': z_val})
                        except ValueError:
                            continue
    df = pd.DataFrame(recs)
    if not df.empty:
        df = df.drop_duplicates('datetime').sort_values('datetime').reset_index(drop=True)
        # Derivada temporal dB/dt (nT/min)
        df['dH_dt'] = df['H'].diff()
        df['dZ_dt'] = df['Z'].diff()
        # Filtro de picos irreais de variação mecânica (> 50 nT/min)
        df['dH_dt'] = np.where(abs(df['dH_dt']) < 80, df['dH_dt'], np.nan)
        df['dZ_dt'] = np.where(abs(df['dZ_dt']) < 80, df['dZ_dt'], np.nan)
    return df

df_vss = parse_mag_full('VSS', 17500, 19000)
df_sms = parse_mag_full('SMS', 16500, 17600)

print(f"  Vassouras (VSS): {len(df_vss)} pontos")
print(f"  São Martinho da Serra (SMS): {len(df_sms)} pontos")

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 10), sharex=True)

# Painel 1: Campo H em Vassouras (VSS/RJ)
if not df_vss.empty:
    ax1.plot(df_vss['datetime'], df_vss['H'], color='#1f77b4', linewidth=1, label='Campo H (nT) - Vassouras (VSS/RJ)')
    ax1.set_ylabel('H (nT)', fontsize=11, fontweight='bold', color='#1f77b4')
    ax1.set_title('Estimativa de Variabilidade dB/dt e Correntes Induzidas (GIC / Proxy J) em 2024\nObservatório de Vassouras (VSS/RJ)', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right', frameon=True)

# Painel 2: Taxa de Variação dH/dt (nT/min) - Indicador de Corrente Induzida Horizontal
if not df_vss.empty:
    ax2.plot(df_vss['datetime'], df_vss['dH_dt'], color='#d62728', linewidth=0.8, alpha=0.85, label='dH/dt (nT/min) - Vassouras (Proxy de Corrente Induzida GIC)')
    ax2.set_ylabel('dH/dt (nT/min)', fontsize=11, fontweight='bold', color='#d62728')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper right', frameon=True)

# Painel 3: Taxa de Variação Vertical dZ/dt (nT/min) - Indicador de Variação Vertical
if not df_vss.empty:
    ax3.plot(df_vss['datetime'], df_vss['dZ_dt'], color='#9467bd', linewidth=0.8, alpha=0.85, label='dZ/dt (nT/min) - Vassouras (Variação da Componente Vertical Z)')
    ax3.set_ylabel('dZ/dt (nT/min)', fontsize=11, fontweight='bold', color='#9467bd')
    ax3.grid(True, linestyle='--', alpha=0.6)
    ax3.legend(loc='upper right', frameon=True)

# Sombreamento dos eventos
for ax in [ax1, ax2, ax3]:
    ax.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.22, label='Tempestade G4 (Março)')
    ax.axvspan(datetime.datetime(2024, 4, 19), datetime.datetime(2024, 4, 21), color='#e377c2', alpha=0.25)
    ax.axvspan(datetime.datetime(2024, 4, 27), datetime.datetime(2024, 5, 15), color='#0066cc', alpha=0.2, label='Chuvas RS')
    ax.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35, label='Supertempestade G5 (Maio)')

ax3.xaxis.set_major_locator(mdates.MonthLocator())
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.xlabel('Mês (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot = os.path.join(PLOT_DIR, "estimativa_jz_dbdt_vassouras_2024.png")
plt.savefig(file_plot, dpi=300, bbox_inches='tight')
plt.close()
print(f"Gráfico de dH/dt e dZ/dt em Vassouras salvo em: {file_plot}")
