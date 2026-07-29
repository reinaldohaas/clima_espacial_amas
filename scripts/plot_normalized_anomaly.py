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

def insert_time_gaps(df, max_gap_minutes=30):
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

def parse_mag_normalized(st_name, min_h, max_h):
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
        df = df.drop_duplicates('datetime')
        if st_name in ['SMS', 'MED']:
            df['H_median'] = df['H'].rolling(window=15, center=True, min_periods=1).median()
            df = df[abs(df['H'] - df['H_median']) < 250].drop(columns=['H_median'])
        
        # Subtrair baseline diária/quiet-day para obter Perturbação Delta_H (nT)
        df['baseline'] = df['H'].rolling(window=1440, center=True, min_periods=60).median()
        df['Delta_H'] = df['H'] - df['baseline']
        df = insert_time_gaps(df, max_gap_minutes=60)
    return df

df_vss = parse_mag_normalized('VSS', 17500, 19000)
df_sms = parse_mag_normalized('SMS', 16500, 17600)
df_med = parse_mag_normalized('MED', 17000, 19000)

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, ax = plt.subplots(figsize=(15, 7))

if not df_vss.empty:
    ax.plot(df_vss['datetime'], df_vss['Delta_H'], color='#1f77b4', linewidth=1, alpha=0.8, label='Vassouras (VSS/RJ) — ΔH (nT)')
if not df_med.empty:
    ax.plot(df_med['datetime'], df_med['Delta_H'], color='#ff7f0e', linewidth=1, alpha=0.8, label='Medianeira (MED/PR) — ΔH (nT)')
if not df_sms.empty:
    ax.plot(df_sms['datetime'], df_sms['Delta_H'], color='#2ca02c', linewidth=1, alpha=0.85, label='São Martinho da Serra (SMS/RS) — ΔH (nT)')

ax.set_ylabel('Perturbação Magnética ΔH (nT)', fontsize=12, fontweight='bold')
ax.set_title('Perturbação Magnética Normalizada (ΔH = H - Baseline Quiet-Day) em 2024\n(Demonstrando que, ao remover o valor absoluto regional, o sinal da tempestade é IDÊNTICO)', fontsize=13, fontweight='bold', pad=12)

ax.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.22, label='Tempestade G4 (Março)')
ax.axvspan(datetime.datetime(2024, 4, 19), datetime.datetime(2024, 4, 21), color='#e377c2', alpha=0.25, label='Perturbação KSA>=5 (Abril)')
ax.axvspan(datetime.datetime(2024, 4, 27), datetime.datetime(2024, 5, 15), color='#0066cc', alpha=0.2, label='Chuvas RS')
ax.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35, label='Supertempestade G5 (Maio)')

ax.legend(loc='lower left', frameon=True, fontsize=10)
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.tight_layout()

file_plot = os.path.join(PLOT_DIR, "perturbacao_magnetica_normalizada_delta_H_2024.png")
plt.savefig(file_plot, dpi=300, bbox_inches='tight')
plt.close()
print(f"Gráfico de perturbação normalizada ΔH salvo em: {file_plot}")
