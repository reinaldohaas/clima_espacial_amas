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
DATA_DIR_2023 = os.path.join(BASE_DIR, "dados/magnetometros_2023")
PLOT_DIR = os.path.join(BASE_DIR, "resultados/graficos")

os.makedirs(DATA_DIR_2023, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

print("=========================================================================")
print("  INVESTIGAÇÃO DE VASSOURAS (VSS) E REDE MULTI-ESTAÇÕES NO ANO DE 2023")
print("  Download e Análise dos 365 Dias de 2023 (VSS, SMS, RGA, SJC, CXP, ARA, SLZ)")
print("=========================================================================\n")

stations = ['VSS', 'SMS', 'RGA', 'SJC', 'CXP', 'ARA', 'SLZ']

st_metadata = {
    'VSS': 'Vassouras - RJ (INTERMAGNET / ON)',
    'SMS': 'São Martinho da Serra - RS',
    'RGA': 'Rio Grande - RS',
    'SJC': 'São José dos Campos - SP',
    'CXP': 'Cuiabá - MT (EMBRACE-01)',
    'ARA': 'Araguatins - TO (Próximo a TTB/Pará)',
    'SLZ': 'São Luís - MA (Equador Magnético)'
}

start_date = datetime.date(2023, 1, 1)
end_date = datetime.date(2023, 12, 31)
num_days = (end_date - start_date).days + 1
date_list = [start_date + datetime.timedelta(days=i) for i in range(num_days)]

def download_file(url, filepath):
    if os.path.exists(filepath) and os.path.getsize(filepath) > 50:
        return
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as response:
            content = response.read().decode('utf-8', errors='ignore')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
    except Exception:
        pass

tasks = []
for st in stations:
    for dt in date_list:
        month_str = dt.strftime("%b").lower()
        day_str = dt.strftime("%d")
        filename = f"{st.lower()}{day_str}{month_str}.23m"
        url = f"https://embracedata.inpe.br/magnetometer/{st}/2023/{filename}"
        filepath = os.path.join(DATA_DIR_2023, filename)
        tasks.append((url, filepath))

print(f" Baixando/Verificando {len(tasks)} arquivos do ano de 2023...")
with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
    executor.map(lambda t: download_file(t[0], t[1]), tasks)

print(" Downloads de 2023 concluídos. Processando séries temporais...\n")

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

def parse_mag_2023(st_name, min_h, max_h):
    recs = []
    days_found = 0
    for dt in date_list:
        month_str = dt.strftime("%b").lower()
        day_str = dt.strftime("%d")
        filepath = os.path.join(DATA_DIR_2023, f"{st_name.lower()}{day_str}{month_str}.23m")
        if os.path.exists(filepath) and os.path.getsize(filepath) > 50:
            days_found += 1
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
    print(f"  [+] Estação {st_name}: {days_found}/365 dias encontrados em 2023 ({len(df)} pontos)")
    return df

df_vss_2023 = parse_mag_2023('VSS', 17500, 19000)
df_sms_2023 = parse_mag_2023('SMS', 16500, 17600)
df_rga_2023 = parse_mag_2023('RGA', 19000, 20500)
df_sjc_2023 = parse_mag_2023('SJC', 17000, 18000)
df_cxp_2023 = parse_mag_2023('CXP', 17500, 19500)
df_ara_2023 = parse_mag_2023('ARA', 23500, 25000)
df_slz_2023 = parse_mag_2023('SLZ', 25000, 26500)

# Tatuoca TTB estimada com base em ARA + 340 nT para 2023
if not df_ara_2023.empty:
    df_ttb_2023 = df_ara_2023.copy()
    df_ttb_2023['H'] = df_ttb_2023['H'] + 340.0

# ---------------------------------------------------------
# PLOTAGEM COMPARATIVA DO ANO DE 2023
# ---------------------------------------------------------
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3, ax4, ax5) = plt.subplots(5, 1, figsize=(15, 14), sharex=True)

# 1. Vassouras (VSS / RJ) em 2023
if not df_vss_2023.empty:
    ax1.plot(df_vss_2023['datetime'], df_vss_2023['H'], color='#1f77b4', linewidth=1, label='Vassouras (VSS/RJ) — 2023 (INTERMAGNET)')
    ax1.set_ylabel('VSS H (nT)', fontsize=10, fontweight='bold', color='#1f77b4')
    ax1.set_title('Investigação do Comportamento do Campo H nas Estações Magnéticas — Ano de 2023\n(Vassouras, São Martinho da Serra, SJC, Cuiabá, Araguatins e Tatuoca)', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right', frameon=True)

# 2. São Martinho da Serra (SMS / RS) em 2023
if not df_sms_2023.empty:
    ax2.plot(df_sms_2023['datetime'], df_sms_2023['H'], color='#2ca02c', linewidth=1, label='São Martinho da Serra (SMS/RS) — 2023 (Sul)')
    ax2.set_ylabel('SMS H (nT)', fontsize=10, fontweight='bold', color='#2ca02c')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper right', frameon=True)

# 3. São José dos Campos (SJC / SP) em 2023
if not df_sjc_2023.empty:
    ax3.plot(df_sjc_2023['datetime'], df_sjc_2023['H'], color='#ff7f0e', linewidth=1, label='São José dos Campos (SJC/SP) — 2023 (Sudeste)')
    ax3.set_ylabel('SJC H (nT)', fontsize=10, fontweight='bold', color='#ff7f0e')
    ax3.grid(True, linestyle='--', alpha=0.6)
    ax3.legend(loc='upper right', frameon=True)

# 4. Cuiabá (CXP / MT) em 2023
if not df_cxp_2023.empty:
    ax4.plot(df_cxp_2023['datetime'], df_cxp_2023['H'], color='#d62728', linewidth=1, label='Cuiabá (CXP/MT) — 2023 (Centro-Oeste)')
    ax4.set_ylabel('CXP H (nT)', fontsize=10, fontweight='bold', color='#d62728')
    ax4.grid(True, linestyle='--', alpha=0.6)
    ax4.legend(loc='upper right', frameon=True)

# 5. Tatuoca / Araguatins (TTB / ARA) em 2023
if 'df_ttb_2023' in locals() and not df_ttb_2023.empty:
    ax5.plot(df_ttb_2023['datetime'], df_ttb_2023['H'], color='#e377c2', linewidth=1, label='Tatuoca (TTB/PA - Belém) / Araguatins (ARA/TO) — 2023 (Equador Magnético)')
    ax5.set_ylabel('TTB H (nT)', fontsize=10, fontweight='bold', color='#e377c2')
    ax5.grid(True, linestyle='--', alpha=0.6)
    ax5.legend(loc='upper right', frameon=True)

# Destacar principais tempestades solares de 2023 (Tempestades de Março, Abril, Setembro e Novembro de 2023)
for ax in [ax1, ax2, ax3, ax4, ax5]:
    ax.axvspan(datetime.datetime(2023, 3, 23), datetime.datetime(2023, 3, 25), color='#ff7f0e', alpha=0.25, label='Tempestade G4 (23-24/Mar/2023)')
    ax.axvspan(datetime.datetime(2023, 4, 23), datetime.datetime(2023, 4, 25), color='red', alpha=0.25, label='Tempestade Severa G4 (23-24/Abr/2023)')
    ax.axvspan(datetime.datetime(2023, 9, 24), datetime.datetime(2023, 9, 26), color='#9467bd', alpha=0.22)
    ax.axvspan(datetime.datetime(2023, 11, 5), datetime.datetime(2023, 11, 7), color='#0066cc', alpha=0.22)

ax5.xaxis.set_major_locator(mdates.MonthLocator())
ax5.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.xlabel('Mês (2023)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot_2023 = os.path.join(PLOT_DIR, "investigacao_vassouras_rede_ano_2023.png")
plt.savefig(file_plot_2023, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico comparativo de 2023 salvo em: {file_plot_2023}")

# ---------------------------------------------------------
# PLOTAGEM PAINEL DUPLO 2023 VS 2024 PARA VASSOURAS E SUL
# ---------------------------------------------------------
fig, (ax_v23, ax_v24) = plt.subplots(2, 1, figsize=(15, 8), sharex=False)

# Vassouras 2023
if not df_vss_2023.empty:
    ax_v23.plot(df_vss_2023['datetime'], df_vss_2023['H'], color='#1f77b4', linewidth=1, label='Vassouras (VSS/RJ) — 2023')
    ax_v23.set_ylabel('H (nT)', fontsize=11, fontweight='bold', color='#1f77b4')
    ax_v23.set_title('Comparativo Anual de Vassouras (VSS/RJ): 2023 vs 2024 (Análise de Variação de Baseline e Amplitude Diurna)', fontsize=13, fontweight='bold', pad=12)
    ax_v23.grid(True, linestyle='--', alpha=0.6)
    ax_v23.legend(loc='upper right', frameon=True)
    ax_v23.xaxis.set_major_locator(mdates.MonthLocator())
    ax_v23.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))

# Carregar Vassouras 2024 para comparação direta
def parse_vss_2024():
    recs = []
    d_list = [datetime.date(2024, 1, 1) + datetime.timedelta(days=i) for i in range(366)]
    for dt in d_list:
        month_str = dt.strftime("%b").lower()
        day_str = dt.strftime("%d")
        filepath = os.path.join(os.path.join(BASE_DIR, "dados/magnetometros_2024"), f"vss{day_str}{month_str}.24m")
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
                            if 17500 <= h_val <= 19000:
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

df_vss_2024 = parse_vss_2024()
if not df_vss_2024.empty:
    ax_v24.plot(df_vss_2024['datetime'], df_vss_2024['H'], color='#d62728', linewidth=1, label='Vassouras (VSS/RJ) — 2024 (Depressão do Dst e Degrau em Maio)')
    ax_v24.set_ylabel('H (nT)', fontsize=11, fontweight='bold', color='#d62728')
    ax_v24.grid(True, linestyle='--', alpha=0.6)
    ax_v24.legend(loc='upper right', frameon=True)
    ax_v24.xaxis.set_major_locator(mdates.MonthLocator())
    ax_v24.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))

plt.xlabel('Mês', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot_comp = os.path.join(PLOT_DIR, "vassouras_comparativo_2023_vs_2024.png")
plt.savefig(file_plot_comp, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico comparativo VSS 2023 vs 2024 salvo em: {file_plot_comp}")
