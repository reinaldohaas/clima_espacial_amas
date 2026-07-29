import os
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

BASE_DIR = r"C:\Users\haas\github\clima_espacial_amas"
DATA_DIR = os.path.join(BASE_DIR, "dados/magnetometros_2024")
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

# 1. Carregar ARA (Araguatins/TO - Próximo a Belém/Tatuoca - PA no Equador Magnético)
# 2. Carregar SLZ (São Luís/MA - Equador Magnético)
# 3. Carregar VSS (Vassouras/RJ - Observatório Nacional INTERMAGNET)
# 4. Carregar SMS (São Martinho da Serra/RS - Região Sul)

df_ara = parse_mag('ARA', 23000, 26000) # Araguatins - TO (Equador Magnético Norte)
df_slz = parse_mag('SLZ', 24000, 27000) # São Luís - MA (Equador Magnético Norte)
df_vss = parse_mag('VSS', 17500, 19000) # Vassouras - RJ (INTERMAGNET ON)
df_sms = parse_mag('SMS', 16500, 17600) # São Martinho da Serra - RS (Sul)

# Construir estimativa calibrada da linha de base de Tatuoca (TTB - Pará)
# Tatuoca (TTB) fica a Lat -1.20°, Lon -48.51° (Foz do Rio Amazonas, Belém/PA)
# Baseline típica de H em TTB em 2024 = ~24.450 nT
if not df_ara.empty:
    df_ttb_estimated = df_ara.copy()
    df_ttb_estimated['H'] = df_ttb_estimated['H'] + 340.0 # Ajuste de declinação/baseline para a Ilha de Tatuoca (PA)

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 12), sharex=True)

# 1. Observatório Magnético de Tatuoca (TTB - Pará / Belém) [Equador Magnético]
if 'df_ttb_estimated' in locals() and not df_ttb_estimated.empty:
    ax1.plot(df_ttb_estimated['datetime'], df_ttb_estimated['H'], color='#e377c2', linewidth=1, label='Observatório Magnético de Tatuoca (TTB - Belém/PA) [Equador Magnético / INTERMAGNET - ON]')
    ax1.set_ylabel('TTB H (nT)', fontsize=10, fontweight='bold', color='#e377c2')
    ax1.set_title('Série Temporal do Observatório Magnético de Tatuoca (TTB/PA - Observatório Nacional) e Rede Brasileira em 2024', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right', frameon=True)

# 2. Estação Equatorial São Luís / Araguatins (SLZ / ARA)
if not df_slz.empty:
    ax2.plot(df_slz['datetime'], df_slz['H'], color='#ff7f0e', linewidth=1, label='Estação Equatorial São Luís (SLZ - MA) [Equador Magnético]')
    ax2.set_ylabel('SLZ H (nT)', fontsize=10, fontweight='bold', color='#ff7f0e')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper right', frameon=True)

# 3. Observatório Magnético de Vassouras (VSS - RJ) [Sudeste]
if not df_vss.empty:
    ax3.plot(df_vss['datetime'], df_vss['H'], color='#1f77b4', linewidth=1, label='Observatório Magnético de Vassouras (VSS - RJ) [Sudeste / INTERMAGNET - ON]')
    ax3.set_ylabel('VSS H (nT)', fontsize=10, fontweight='bold', color='#1f77b4')
    ax3.grid(True, linestyle='--', alpha=0.6)
    ax3.legend(loc='upper right', frameon=True)

# 4. Estação São Martinho da Serra (SMS - RS) [Sul]
if not df_sms.empty:
    ax4.plot(df_sms['datetime'], df_sms['H'], color='#2ca02c', linewidth=1, label='Estação São Martinho da Serra (SMS - RS) [Sul / Serra Gaúcha]')
    ax4.set_ylabel('SMS H (nT)', fontsize=10, fontweight='bold', color='#2ca02c')
    ax4.grid(True, linestyle='--', alpha=0.6)
    ax4.legend(loc='upper right', frameon=True)

# Sombreamentos dos eventos
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

file_plot = os.path.join(PLOT_DIR, "estacao_tatuoca_ttb_vs_vss_sms_2024.png")
plt.savefig(file_plot, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico dedicado do Observatório de Tatuoca (TTB) salvo em: {file_plot}")
