import os
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

BASE_DIR = r"C:\Users\haas\github\clima_espacial_amas"
DATA_DIR_2024 = os.path.join(BASE_DIR, "dados/magnetometros_2024")
PLOT_DIR = os.path.join(BASE_DIR, "resultados/graficos")

start_date = datetime.date(2024, 1, 1)
end_date = datetime.date(2024, 12, 31)
num_days = (end_date - start_date).days + 1
date_list = [start_date + datetime.timedelta(days=i) for i in range(num_days)]

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

def parse_mag(st_name, min_h, max_h):
    recs = []
    for dt in date_list:
        month_str = dt.strftime("%b").lower()
        day_str = dt.strftime("%d")
        filepath = os.path.join(DATA_DIR_2024, f"{st_name.lower()}{day_str}{month_str}.24m")
        if os.path.exists(filepath):
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

df_vss = parse_mag('VSS', 17500, 19000)
df_sjc = parse_mag('SJC', 17000, 18000)
df_sms = parse_mag('SMS', 16500, 17600)

if not df_vss.empty:
    df_vss['H_base'] = df_vss['H'].rolling(window=1440, center=True, min_periods=60).median()
    df_vss['dH'] = df_vss['H'] - df_vss['H_base']

if not df_sjc.empty:
    df_sjc['H_base'] = df_sjc['H'].rolling(window=1440, center=True, min_periods=60).median()
    df_sjc['dH'] = df_sjc['H'] - df_sjc['H_base']

if not df_sms.empty:
    df_sms['H_base'] = df_sms['H'].rolling(window=1440, center=True, min_periods=60).median()
    df_sms['dH'] = df_sms['H'] - df_sms['H_base']

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 10), sharex=True)

# Painel 1: Dado Bruto de Vassouras com a Anomalia de Baseline no 1º Semestre
if not df_vss.empty:
    ax1.plot(df_vss['datetime'], df_vss['H'], color='#1f77b4', linewidth=1, label='Vassouras (VSS Bruto - nT) — Deriva de Linha de Base no 1º Semestre 2024')
    ax1.set_ylabel('VSS Bruto (nT)', fontsize=10, fontweight='bold', color='#1f77b4')
    ax1.set_title('Diagnóstico da Anomalia de Vassouras (VSS) e Soluções de Correção/Substituição (2024)', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right', frameon=True)

# Painel 2: Vassouras Corrigido por Anomalia ΔH = H - H_base (Efeito da Deriva Zerado!)
if not df_vss.empty:
    ax2.plot(df_vss['datetime'], df_vss['dH'], color='#0066cc', linewidth=1, label='Vassouras Corrigido (ΔH = H - H_base) — Sinal Limpo e Sem Deriva')
    ax2.set_ylabel('VSS ΔH (nT)', fontsize=10, fontweight='bold', color='#0066cc')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper right', frameon=True)

# Painel 3: Estação Alternativa São José dos Campos (SJC/SP) — A ~200 km de Vassouras!
if not df_sjc.empty:
    ax3.plot(df_sjc['datetime'], df_sjc['dH'], color='#ff7f0e', linewidth=1, label='São José dos Campos (SJC/SP - ΔH) — Substituta Perfeita no Sudeste (Sem Deriva)')
    ax3.set_ylabel('SJC ΔH (nT)', fontsize=10, fontweight='bold', color='#ff7f0e')
    ax3.grid(True, linestyle='--', alpha=0.6)
    ax3.legend(loc='upper right', frameon=True)

for ax in [ax1, ax2, ax3]:
    ax.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.22, label='Tempestade G4 (Março)')
    ax.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35, label='Supertempestade G5 / GLE 74')

ax3.xaxis.set_major_locator(mdates.MonthLocator())
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.xlabel('Mês (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot = os.path.join(PLOT_DIR, "diagnostico_e_solucao_vassouras_2024.png")
plt.savefig(file_plot, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico de diagnóstico e solução de Vassouras salvo em: {file_plot}")
