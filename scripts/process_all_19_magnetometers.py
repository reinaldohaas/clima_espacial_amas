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
PLOT_DIR = os.path.join(BASE_DIR, "resultados/graficos_estacoes")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

print("=========================================================================")
print("  VARREDURA E ANÁLISE INDIVIDUAL DE TODAS AS 19 ESTAÇÕES GEOMAGNÉTICAS (2024)")
print("  Repositório EMBRACE/INPE — 01/Jan/2024 a 31/Dez/2024")
print("=========================================================================\n")

stations = [
    'ALF', 'ARA', 'CAR', 'CBA', 'CHI', 'CXP', 'EUS', 'JAT', 
    'MAN', 'MED', 'PAL', 'PVE', 'RGA', 'SJC', 'SLZ', 'SMS', 
    'STM', 'TCM', 'VSS'
]

st_metadata = {
    'ALF': 'Alta Floresta - MT',
    'ARA': 'Araguatins - TO',
    'CAR': 'Carauari - AM',
    'CBA': 'Cuiabá - MT',
    'CHI': 'Chuí - RS',
    'CXP': 'Cuiabá - MT (EMBRACE-01)',
    'EUS': 'Eusébio - CE',
    'JAT': 'Jataí - GO',
    'MAN': 'Manaus - AM',
    'MED': 'Medianeira - PR',
    'PAL': 'Palmas - TO',
    'PVE': 'Porto Velho - RO',
    'RGA': 'Rio Grande - RS / ARG',
    'SJC': 'São José dos Campos - SP',
    'SLZ': 'São Luís - MA',
    'SMS': 'São Martinho da Serra - RS',
    'STM': 'Santarém - PA',
    'TCM': 'Tacuru - MS',
    'VSS': 'Vassouras - RJ (INTERMAGNET)'
}

start_date = datetime.date(2024, 1, 1)
end_date = datetime.date(2024, 12, 31)
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
        filename = f"{st.lower()}{day_str}{month_str}.24m"
        url = f"https://embracedata.inpe.br/magnetometer/{st}/2024/{filename}"
        filepath = os.path.join(DATA_DIR, filename)
        tasks.append((url, filepath))

print(f" Verificando {len(tasks)} arquivos das 19 estações em paralelo...")
with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
    executor.map(lambda t: download_file(t[0], t[1]), tasks)

print(" Download/Verificação concluídos. Processando cada estação individualmente...\n")

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

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

summary_stats = []

for st in stations:
    st_name_full = st_metadata.get(st, st)
    recs = []
    days_found = 0
    
    for dt in date_list:
        month_str = dt.strftime("%b").lower()
        day_str = dt.strftime("%d")
        filepath = os.path.join(DATA_DIR, f"{st.lower()}{day_str}{month_str}.24m")
        if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
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
                            z_val = float(parts[7])
                            if 10000 <= h_val <= 35000:
                                dt_obj = datetime.datetime(y, m, d, hh, mm)
                                recs.append({'datetime': dt_obj, 'H': h_val, 'Z': z_val})
                        except ValueError:
                            continue

    df = pd.DataFrame(recs)
    
    if not df.empty and len(df) > 100:
        df = df.drop_duplicates('datetime').sort_values('datetime').reset_index(drop=True)
        
        # Filtro de picos espúrios por mediana móvel
        df['H_median'] = df['H'].rolling(window=21, center=True, min_periods=1).median()
        df = df[abs(df['H'] - df['H_median']) < 350].drop(columns=['H_median'])
        
        df['dH_dt'] = df['H'].diff()
        df['dH_dt'] = np.where(abs(df['dH_dt']) < 80, df['dH_dt'], np.nan)
        
        df_clean = insert_time_gaps(df, max_gap_minutes=60)
        
        points_count = len(df)
        h_mean = df['H'].mean()
        h_min = df['H'].min()
        h_max = df['H'].max()
        coverage_pct = (days_found / 366.0) * 100
        
        summary_stats.append({
            'Estação': st,
            'Nome / Localização': st_name_full,
            'Dias Com Dados': days_found,
            'Cobertura (%)': f"{coverage_pct:.1f}%",
            'Total Pontos': points_count,
            'H Médio (nT)': f"{h_mean:.1f}",
            'H Mín (nT)': f"{h_min:.1f}",
            'H Máx (nT)': f"{h_max:.1f}"
        })
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
        
        ax1.plot(df_clean['datetime'], df_clean['H'], color='#1f77b4', linewidth=1, label=f'Campo H (nT) — {st_name_full}')
        ax1.set_ylabel('H (nT)', fontsize=11, fontweight='bold', color='#1f77b4')
        ax1.set_title(f'Série Temporal Geomagnética 2024 — Estação {st} ({st_name_full})\nCobertura: {days_found}/366 dias ({coverage_pct:.1f}%)', fontsize=13, fontweight='bold', pad=12)
        ax1.grid(True, linestyle='--', alpha=0.6)
        ax1.legend(loc='upper right', frameon=True)
        
        ax2.plot(df_clean['datetime'], df_clean['dH_dt'], color='#d62728', linewidth=0.8, alpha=0.85, label='dH/dt (nT/min) — Taxa de Variação (GIC Proxy)')
        ax2.set_ylabel('dH/dt (nT/min)', fontsize=11, fontweight='bold', color='#d62728')
        ax2.grid(True, linestyle='--', alpha=0.6)
        ax2.legend(loc='upper right', frameon=True)
        
        for ax in [ax1, ax2]:
            ax.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.22, label='Tempestade G4 (23-25/Mar)')
            ax.axvspan(datetime.datetime(2024, 4, 19), datetime.datetime(2024, 4, 21), color='#e377c2', alpha=0.25)
            ax.axvspan(datetime.datetime(2024, 4, 27), datetime.datetime(2024, 5, 15), color='#0066cc', alpha=0.2, label='Chuvas RS')
            ax.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35, label='Supertempestade G5 / GLE 74')
            
        ax2.xaxis.set_major_locator(mdates.MonthLocator())
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
        plt.xticks(rotation=0, ha='center', fontsize=11)
        plt.xlabel('Mês (2024)', fontsize=12, fontweight='bold')
        plt.tight_layout()
        
        plot_path = os.path.join(PLOT_DIR, f"estacao_{st}_ano_2024.png")
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  [+] {st} ({st_name_full}): {days_found} dias ({coverage_pct:.1f}%) -> Gráfico salvo.")
    else:
        coverage_pct = (days_found / 366.0) * 100
        summary_stats.append({
            'Estação': st,
            'Nome / Localização': st_name_full,
            'Dias Com Dados': days_found,
            'Cobertura (%)': f"{coverage_pct:.1f}%",
            'Total Pontos': 0,
            'H Médio (nT)': "N/A",
            'H Mín (nT)': "N/A",
            'H Máx (nT)': "N/A"
        })
        print(f"  [-] {st} ({st_name_full}): Sem dados suficientes ({days_found} arquivos).")

df_summary = pd.DataFrame(summary_stats)
summary_csv = os.path.join(BASE_DIR, "dados/jz/resumo_cobertura_19_estacoes_2024.csv")
df_summary.to_csv(summary_csv, index=False, encoding='utf-8-sig')

print("\n=========================================================================")
print(f"  VARREDURA CONCLUÍDA! Relatório salvo em: {summary_csv}")
print("=========================================================================")
print(df_summary.to_string(index=False))
