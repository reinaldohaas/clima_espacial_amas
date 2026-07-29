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

vss_records = []
for dt in date_list:
    month_str = dt.strftime("%b").lower()
    day_str = dt.strftime("%d")
    filepath = os.path.join(DATA_DIR, f"vss{day_str}{month_str}.24m")
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
                            vss_records.append({'datetime': dt_obj, 'date': dt, 'H': h_val})
                    except ValueError:
                        continue

df_vss = pd.DataFrame(vss_records)
if not df_vss.empty:
    df_vss = df_vss.drop_duplicates('datetime').sort_values('datetime').reset_index(drop=True)
    
    # Calcular amplitude diária (H_max - H_min) para demonstrar a variação diurna Sq
    daily_amplitude = df_vss.groupby('date')['H'].agg(lambda x: x.max() - x.min()).reset_index()
    daily_amplitude['datetime'] = pd.to_datetime(daily_amplitude['date'])

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 9), sharex=True)

# Painel 1: Campo H em Vassouras (VSS/RJ) com os degraus de tempestades
ax1.plot(df_vss['datetime'], df_vss['H'], color='#1f77b4', linewidth=1, label='Campo Magnético H (nT) — Vassouras (VSS/RJ)')
ax1.set_ylabel('VSS H (nT)', fontsize=11, fontweight='bold', color='#1f77b4')
ax1.set_title('Análise Detalhada do Comportamento de Vassouras (VSS/RJ) em 2024\n(Por que as variações diminuem e a baseline muda após Maio de 2024?)', fontsize=13, fontweight='bold', pad=12)
ax1.grid(True, linestyle='--', alpha=0.6)

# Destaques das tempestades que causaram as quedas de baseline
ax1.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.25, label='1ª Queda: Tempestade G4 (23-25/Março)')
ax1.axvspan(datetime.datetime(2024, 4, 19), datetime.datetime(2024, 4, 21), color='#e377c2', alpha=0.25, label='2ª Queda: Perturbação G3 (19-21/Abril)')
ax1.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35, label='3ª Queda Máxima: Supertempestade G5 / GLE 74 (10-11/Maio)')
ax1.legend(loc='upper right', frameon=True, fontsize=10)

# Painel 2: Amplitude Diária (H_max - H_min) — Sistema Sq e Mudança Sazonal
if not daily_amplitude.empty:
    ax2.plot(daily_amplitude['datetime'], daily_amplitude['H'], color='#d62728', linewidth=1.2, label='Amplitude Diária Diurna (H_max - H_min) em VSS')
    ax2.set_ylabel('Amplitude Diária (nT)', fontsize=11, fontweight='bold', color='#d62728')
    ax2.grid(True, linestyle='--', alpha=0.6)
    
    # Sombreamentos
    ax2.axvspan(datetime.datetime(2024, 1, 1), datetime.datetime(2024, 4, 30), color='orange', alpha=0.12, label='Verão/Outono: Maior Ionização e Amplitude Sq Diurna')
    ax2.axvspan(datetime.datetime(2024, 5, 1), datetime.datetime(2024, 8, 31), color='blue', alpha=0.1, label='Inverno: Menor Ionização Ionosférica (Curva Diurna Mais Estável)')
    ax2.legend(loc='upper right', frameon=True, fontsize=10)

ax2.xaxis.set_major_locator(mdates.MonthLocator())
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.xlabel('Mês (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot = os.path.join(PLOT_DIR, "explicacao_vassouras_variacao_2024.png")
plt.savefig(file_plot, dpi=300, bbox_inches='tight')
plt.close()
print(f"Gráfico explicativo de Vassouras salvo em: {file_plot}")
