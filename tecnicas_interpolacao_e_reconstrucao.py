import os
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

BASE_DIR = r"C:\Users\haas\github\clima_espacial_amas"
DATA_DIR_2024 = os.path.join(BASE_DIR, "dados_2024_completo")
PLOT_DIR = os.path.join(BASE_DIR, "graficos")

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

print(" Carregando estações de 2024...")
df_vss = parse_mag('VSS', 17500, 19000)
df_sjc = parse_mag('SJC', 17000, 18000)
df_sms = parse_mag('SMS', 16500, 17600)

# Alinhamento temporal para regressão de reconstrução espacial
df_merged = pd.merge(df_sjc[['datetime', 'H']].rename(columns={'H': 'H_SJC'}), 
                     df_sms[['datetime', 'H']].rename(columns={'H': 'H_SMS'}), 
                     on='datetime', how='inner')

if not df_vss.empty:
    df_merged = pd.merge(df_merged, df_vss[['datetime', 'H']].rename(columns={'H': 'H_VSS'}), on='datetime', how='left')

# 1. Regressão Linear Espacial para Reconstruir Vassouras a partir de SJC e SMS no 2º Semestre (quando VSS estava estabilizado)
valid_train = df_merged[df_merged['datetime'] >= '2024-05-15'].dropna()

if not valid_train.empty:
    X_mat = np.column_stack([np.ones(len(valid_train)), valid_train['H_SJC'], valid_train['H_SMS']])
    y_vec = valid_train['H_VSS'].values
    coeffs, _, _, _ = np.linalg.lstsq(X_mat, y_vec, rcond=None)
    
    # Reconstruir Vassouras Reconstruído (VSS_reconstructed) para todo o ano de 2024
    df_merged['VSS_reconstructed'] = coeffs[0] + coeffs[1] * df_merged['H_SJC'] + coeffs[2] * df_merged['H_SMS']

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 10), sharex=True)

# 1. Vassouras Bruto (Com a anomalia do 1º Semestre)
if 'H_VSS' in df_merged.columns:
    ax1.plot(df_merged['datetime'], df_merged['H_VSS'], color='#1f77b4', linewidth=1, label='Vassouras Bruto (VSS - nT) — Com Deriva de Linha de Base no 1º Semestre')
    ax1.set_ylabel('VSS Bruto (nT)', fontsize=10, fontweight='bold', color='#1f77b4')
    ax1.set_title('Reconstrução de Dados Faltantes/Anômalos de Vassouras via Regressão Multi-Estações (SJC + SMS)\nMetodologia Consolidada IAGA/INTERMAGNET', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right', frameon=True)

# 2. Vassouras Reconstruído (VSS_reconstructed) por Regressão Espacial Multi-Estações
if 'VSS_reconstructed' in df_merged.columns:
    ax2.plot(df_merged['datetime'], df_merged['VSS_reconstructed'], color='#2ca02c', linewidth=1, label='Vassouras Reconstruído (Interpolação Regressiva via SJC + SMS) — Série Corrigida Sem Falhas')
    ax2.set_ylabel('VSS Reconstruído (nT)', fontsize=10, fontweight='bold', color='#2ca02c')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper right', frameon=True)

# 3. Sobreposição: Bruto vs Reconstruído
if 'H_VSS' in df_merged.columns and 'VSS_reconstructed' in df_merged.columns:
    ax3.plot(df_merged['datetime'], df_merged['H_VSS'], color='#1f77b4', linewidth=0.8, alpha=0.6, label='Vassouras Bruto')
    ax3.plot(df_merged['datetime'], df_merged['VSS_reconstructed'], color='#d62728', linewidth=1, alpha=0.9, label='Vassouras Reconstruído Sólido')
    ax3.set_ylabel('Comparativo H (nT)', fontsize=10, fontweight='bold')
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

file_plot = os.path.join(PLOT_DIR, "reconstrucao_vassouras_interpolacao.png")
plt.savefig(file_plot, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico de reconstrução por interpolação regressiva salvo em: {file_plot}")
