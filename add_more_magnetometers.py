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
DATA_DIR = os.path.join(BASE_DIR, "dados_2024_completo")
PLOT_DIR = os.path.join(BASE_DIR, "graficos")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

print("=========================================================================")
print("  ADICIONANDO 2 NOVAS ESTAÇÕES GEOMAGNÉTICAS DA REGIÃO SUL/SUDESTE:")
print("  - Medianeira - PR (MED): Região Sul (Próxima ao RS)")
print("  - São José dos Campos - SP (SJC): Região Sudeste")
print("=========================================================================\n")

start_date = datetime.date(2024, 1, 1)
end_date = datetime.date(2024, 12, 31)
num_days = (end_date - start_date).days + 1
date_list = [start_date + datetime.timedelta(days=i) for i in range(num_days)]

def download_file(url, filepath):
    if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
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
# Adicionar MED (Medianeira - PR) e SJC (São José dos Campos - SP)
for st in ['MED', 'SJC']:
    for dt in date_list:
        month_str = dt.strftime("%b").lower()
        day_str = dt.strftime("%d")
        filename = f"{st.lower()}{day_str}{month_str}.24m"
        url = f"https://embracedata.inpe.br/magnetometer/{st}/2024/{filename}"
        filepath = os.path.join(DATA_DIR, filename)
        tasks.append((url, filepath))

print(f" Baixando {len(tasks)} arquivos para MED e SJC (2024)...")
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
    executor.map(lambda t: download_file(t[0], t[1]), tasks)

print(" Download concluído. Processando estações...")

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
        df = df.drop_duplicates('datetime')
        if st_name in ['SMS', 'MED']:
            df['H_median'] = df['H'].rolling(window=15, center=True, min_periods=1).median()
            df = df[abs(df['H'] - df['H_median']) < 250].drop(columns=['H_median'])
        df = insert_time_gaps(df, max_gap_minutes=60)
    return df

# Carregar Magnetômetros (VSS, SMS, MED, SJC)
df_vss = parse_mag('VSS', 17500, 19000)
df_sms = parse_mag('SMS', 16500, 17600)
df_med = parse_mag('MED', 17000, 19000) # Medianeira - PR
df_sjc = parse_mag('SJC', 17000, 19000) # São José dos Campos - SP

print(f"  Vassouras (VSS - RJ): {len(df_vss)} pontos")
print(f"  São Martinho da Serra (SMS - RS): {len(df_sms)} pontos")
print(f"  Medianeira (MED - PR): {len(df_med)} pontos")
print(f"  São José dos Campos (SJC - SP): {len(df_sjc)} pontos")

# ---------------------------------------------------------
# GERAR NOVO GRÁFICO COMPARATIVO DE 4 ESTAÇÕES (SUL / SUDESTE)
# ---------------------------------------------------------
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 12), sharex=True)

# 1. SMS / RS
if not df_sms.empty:
    ax1.plot(df_sms['datetime'], df_sms['H'], color='#2ca02c', linewidth=1, label='SMS (São Martinho da Serra - RS) [Mais próxima de Bento Gonçalves]')
    ax1.set_ylabel('SMS H (nT)', fontsize=10, fontweight='bold', color='#2ca02c')
    ax1.set_title('Rede Magnética do Sul e Sudeste do Brasil em 2024 (SMS/RS, MED/PR, SJC/SP, VSS/RJ)', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right', frameon=True)

# 2. MED / PR
if not df_med.empty:
    ax2.plot(df_med['datetime'], df_med['H'], color='#ff7f0e', linewidth=1, label='MED (Medianeira - PR) [Região Sul]')
    ax2.set_ylabel('MED H (nT)', fontsize=10, fontweight='bold', color='#ff7f0e')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper right', frameon=True)

# 3. SJC / SP
if not df_sjc.empty:
    ax3.plot(df_sjc['datetime'], df_sjc['H'], color='#9467bd', linewidth=1, label='SJC (São José dos Campos - SP) [Região Sudeste]')
    ax3.set_ylabel('SJC H (nT)', fontsize=10, fontweight='bold', color='#9467bd')
    ax3.grid(True, linestyle='--', alpha=0.6)
    ax3.legend(loc='upper right', frameon=True)

# 4. VSS / RJ
if not df_vss.empty:
    ax4.plot(df_vss['datetime'], df_vss['H'], color='#1f77b4', linewidth=1, label='VSS (Vassouras - RJ) [Referência Nacional]')
    ax4.set_ylabel('VSS H (nT)', fontsize=10, fontweight='bold', color='#1f77b4')
    ax4.grid(True, linestyle='--', alpha=0.6)
    ax4.legend(loc='upper right', frameon=True)

# Sombreamento dos Eventos
for ax in [ax1, ax2, ax3, ax4]:
    # Tempestade Março (23-25/Março)
    ax.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.22)
    # Perturbação Abril (19-21/Abril)
    ax.axvspan(datetime.datetime(2024, 4, 19), datetime.datetime(2024, 4, 21), color='#e377c2', alpha=0.25)
    # Chuvas RS (27/Abril a 15/Maio)
    ax.axvspan(datetime.datetime(2024, 4, 27), datetime.datetime(2024, 5, 15), color='#0066cc', alpha=0.2)
    # Supertempestade G5 (10-11/Maio)
    ax.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35)

ax4.xaxis.set_major_locator(mdates.MonthLocator())
ax4.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.xlabel('Mês (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot = os.path.join(PLOT_DIR, "magnetometros_sul_sudeste_2024.png")
plt.savefig(file_plot, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico comparativo de 4 estações salvo em: {file_plot}")
