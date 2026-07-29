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

# Estações representativas do Perfil Latitudinal do Brasil em 2024:
# 1. SLZ (São Luís - MA) & ARA (Araguatins - TO) — Região Equatorial Norte (Próximas a Tatuoca / TTB-PA)
# 2. VSS (Vassouras - RJ) — Região Sudeste (INTERMAGNET ON)
# 3. SMS (São Martinho da Serra - RS) — Região Sul (AMAP)

df_slz = parse_mag('SLZ', 24000, 27000) # São Luís - MA (Equador Magnético)
df_ara = parse_mag('ARA', 23000, 26000) # Araguatins - TO (Norte)
df_vss = parse_mag('VSS', 17500, 19000) # Vassouras - RJ (INTERMAGNET ON)
df_sms = parse_mag('SMS', 16500, 17600) # São Martinho da Serra - RS (Sul)

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 12), sharex=True)

# 1. SLZ / Equador Magnético
if not df_slz.empty:
    ax1.plot(df_slz['datetime'], df_slz['H'], color='#e377c2', linewidth=1, label='SLZ (São Luís - MA) [Equador Magnético / Próximo a Tatuoca TTB-PA]')
    ax1.set_ylabel('SLZ H (nT)', fontsize=10, fontweight='bold', color='#e377c2')
    ax1.set_title('Perfil Latitudinal do Campo Magnético no Brasil — 2024 (Equador Magnético ao Sul)', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right', frameon=True)

# 2. ARA / Norte
if not df_ara.empty:
    ax2.plot(df_ara['datetime'], df_ara['H'], color='#ff7f0e', linewidth=1, label='ARA (Araguatins - TO) [Região Norte]')
    ax2.set_ylabel('ARA H (nT)', fontsize=10, fontweight='bold', color='#ff7f0e')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper right', frameon=True)

# 3. VSS / Sudeste
if not df_vss.empty:
    ax3.plot(df_vss['datetime'], df_vss['H'], color='#1f77b4', linewidth=1, label='VSS (Vassouras - RJ) [Sudeste — INTERMAGNET / Observatório Nacional]')
    ax3.set_ylabel('VSS H (nT)', fontsize=10, fontweight='bold', color='#1f77b4')
    ax3.grid(True, linestyle='--', alpha=0.6)
    ax3.legend(loc='upper right', frameon=True)

# 4. SMS / Sul
if not df_sms.empty:
    ax4.plot(df_sms['datetime'], df_sms['H'], color='#2ca02c', linewidth=1, label='SMS (São Martinho da Serra - RS) [Sul — Anomalia Magnética AMAP]')
    ax4.set_ylabel('SMS H (nT)', fontsize=10, fontweight='bold', color='#2ca02c')
    ax4.grid(True, linestyle='--', alpha=0.6)
    ax4.legend(loc='upper right', frameon=True)

# Sombreamento dos eventos de 2024
for ax in [ax1, ax2, ax3, ax4]:
    ax.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.22, label='Tempestade G4 (Março)')
    ax.axvspan(datetime.datetime(2024, 4, 19), datetime.datetime(2024, 4, 21), color='#e377c2', alpha=0.25)
    ax.axvspan(datetime.datetime(2024, 4, 27), datetime.datetime(2024, 5, 15), color='#0066cc', alpha=0.2, label='Chuvas RS')
    ax.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35, label='Supertempestade G5 / GLE 74')

ax4.xaxis.set_major_locator(mdates.MonthLocator())
ax4.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.xlabel('Mês (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot = os.path.join(PLOT_DIR, "perfil_latitudinal_equador_ao_sul_2024.png")
plt.savefig(file_plot, dpi=300, bbox_inches='tight')
plt.close()
print(f"Gráfico do perfil latitudinal Equador ao Sul salvo em: {file_plot}")
