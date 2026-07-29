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

# Configuração dos diretórios
BASE_DIR = r"C:\Users\haas\github\clima_espacial_amas"
DATA_DIR = os.path.join(BASE_DIR, "dados")
PLOT_DIR = os.path.join(BASE_DIR, "graficos")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

print("=========================================================================")
print("  PROCESSAMENTO E ANÁLISE COMPLETA: ABRIL E MAIO DE 2024")
print("  Estações: Vassouras (VSS), São Martinho da Serra (SMS), Caxias do Sul (RSCL)")
print("=========================================================================\n")

# Intervalo total: 01 de Abril de 2024 a 31 de Maio de 2024
start_date = datetime.date(2024, 4, 1)
end_date = datetime.date(2024, 5, 31)
num_days = (end_date - start_date).days + 1
date_list = [start_date + datetime.timedelta(days=i) for i in range(num_days)]

# Função auxiliar para download concorrente
def download_file(url, filepath):
    if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
        return
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as response:
            content = response.read().decode('utf-8', errors='ignore')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
    except Exception:
        pass

# Lista de tarefas para download
tasks = []

# 1. Magnetômetros VSS, SMS, CXP, EUS
stations = ['VSS', 'SMS', 'CXP', 'EUS']
for st in stations:
    for dt in date_list:
        month_str = dt.strftime("%b").lower() # apr, may
        day_str = dt.strftime("%d")
        filename = f"{st.lower()}{day_str}{month_str}.24m"
        url = f"https://embracedata.inpe.br/magnetometer/{st}/2024/{filename}"
        filepath = os.path.join(DATA_DIR, filename)
        tasks.append((url, filepath))

# 2. GTEX TEC para Caxias do Sul / Bento Gonçalves (rscl)
for dt in date_list:
    doy = dt.timetuple().tm_yday
    doy_str = f"{doy:03d}"
    filename = f"rscl{doy_str}0.24_TEC"
    url = f"https://embracedata.inpe.br/gtex/2024/{doy_str}/{filename}"
    filepath = os.path.join(DATA_DIR, filename)
    tasks.append((url, filepath))

# 3. Índice KSA
for dt in date_list:
    dt_str = dt.strftime("%Y-%m-%d")
    filename = f"ksa_{dt_str}.txt"
    url = f"https://embracedata.inpe.br/ksa/2024/{dt_str}.txt"
    filepath = os.path.join(DATA_DIR, filename)
    tasks.append((url, filepath))

print(f" Baixando {len(tasks)} arquivos do repositório EMBRACE/INPE em paralelo...")
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
    executor.map(lambda t: download_file(t[0], t[1]), tasks)

print(" Download dos arquivos concluído.\n")

# ---------------------------------------------------------
# PARSER E LIMPEZA DE DADOS
# ---------------------------------------------------------

# Função para inserir NaNs nas lacunas temporais (> 5 minutos)
def insert_time_gaps(df, max_gap_minutes=5):
    if df.empty:
        return df
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
        df_gaps = pd.DataFrame(new_rows)
        df = pd.concat([df, df_gaps]).sort_values('datetime').reset_index(drop=True)
    return df

# A) Magnetômetros
def parse_magnetometer(st_name, min_h=10000, max_h=25000):
    records = []
    for dt in date_list:
        month_str = dt.strftime("%b").lower()
        day_str = dt.strftime("%d")
        filename = f"{st_name.lower()}{day_str}{month_str}.24m"
        filepath = os.path.join(DATA_DIR, filename)
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
                            z_val = float(parts[7])
                            # Filtrar valores fora de variação física realista
                            if min_h <= h_val <= max_h:
                                dt_obj = datetime.datetime(y, m, d, hh, mm)
                                records.append({'datetime': dt_obj, 'H': h_val, 'Z': z_val})
                        except ValueError:
                            continue
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.drop_duplicates('datetime')
        # Filtro adicional de mediana para remover picos espúrios isolados em SMS
        if st_name == 'SMS':
            df['H_median'] = df['H'].rolling(window=15, center=True, min_periods=1).median()
            df = df[abs(df['H'] - df['H_median']) < 250].drop(columns=['H_median'])
        df = insert_time_gaps(df, max_gap_minutes=10)
    return df

print(" Processando magnetômetros...")
df_vss = parse_magnetometer('VSS', min_h=17500, max_h=19000)
df_sms = parse_magnetometer('SMS', min_h=16500, max_h=17600)
df_cxp = parse_magnetometer('CXP', min_h=18000, max_h=21000)
df_eus = parse_magnetometer('EUS', min_h=23000, max_h=27000)

print(f"  Vassouras (VSS): {len(df_vss)} pontos")
print(f"  São Martinho da Serra (SMS): {len(df_sms)} pontos (filtrados)")
print(f"  Cuiabá (CXP): {len(df_cxp)} pontos")

# B) GTEX TEC para Caxias do Sul / Bento Gonçalves (rscl)
print(" Processando GTEX TEC de Caxias do Sul / Bento Gonçalves (RSCL)...")
tec_records = []
for dt in date_list:
    doy = dt.timetuple().tm_yday
    doy_str = f"{doy:03d}"
    filename = f"rscl{doy_str}0.24_TEC"
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            current_dt = None
            for line in lines:
                if line.startswith(' 24 ') or line.startswith('24 '):
                    parts = line.split()
                    if len(parts) >= 6:
                        try:
                            yy, mm, dd, hh, min_val = int(parts[0])+2000, int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                            sec_val = int(float(parts[5]))
                            current_dt = datetime.datetime(yy, mm, dd, hh, min_val, sec_val)
                        except Exception:
                            current_dt = None
                elif current_dt and len(line.strip()) > 20:
                    parts = line.split()
                    if len(parts) >= 4 and parts[1] == '0':
                        try:
                            val = float(parts[0])
                            if 0 < val < 250:
                                tec_records.append({'datetime': current_dt, 'TEC': val})
                        except Exception:
                            pass

df_tec = pd.DataFrame(tec_records)
if not df_tec.empty:
    df_tec = df_tec.groupby('datetime')['TEC'].mean().reset_index()
    # Reamostragem para médias de 15 minutos para suavizar e limpar o gráfico
    df_tec = df_tec.set_index('datetime').resample('15min').mean().reset_index()
    df_tec = insert_time_gaps(df_tec, max_gap_minutes=60)
print(f"  GTEX RSCL (Caxias do Sul): {len(df_tec)} registros de TEC carregados.")

# C) Índice KSA
print(" Processando Índice Geomagnético KSA...")
ksa_records = []
for dt in date_list:
    dt_str = dt.strftime("%Y-%m-%d")
    filename = f"ksa_{dt_str}.txt"
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        dt_obj = datetime.datetime.fromisoformat(parts[0])
                        k_str = parts[1]
                        k_num = float(k_str[0])
                        if len(k_str) > 1:
                            if k_str[1] == '+': k_num += 0.33
                            elif k_str[1] == '-': k_num -= 0.33
                        ksa_records.append({'datetime': dt_obj, 'K_index': k_num, 'K_str': k_str})
                    except Exception:
                        continue

df_ksa = pd.DataFrame(ksa_records)
if not df_ksa.empty:
    df_ksa = df_ksa.sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True)
print(f"  Índice KSA: {len(df_ksa)} registros.")

# ---------------------------------------------------------
# GERAÇÃO DOS GRÁFICOS ANALÍTICOS (SERIES COMPLETA ABRIL/MAIO 2024)
# ---------------------------------------------------------
print("\n Gerando gráficos comparativos limpos de Abril e Maio de 2024...")

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

# ---------------------------------------------------------
# GRÁFICO 1: COMPARATIVO MULTI-ESTAÇÕES DE MAGNETÔMETROS
# ---------------------------------------------------------
fig1, (ax_vss, ax_sms, ax_cxp) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

# Vassouras - RJ (Referência Nacional Limpa)
if not df_vss.empty:
    ax_vss.plot(df_vss['datetime'], df_vss['H'], color='#1f77b4', linewidth=1.2, label='Magnetômetro VSS (Vassouras - RJ) [Referência Nacional]')
    ax_vss.set_ylabel('VSS H (nT)', fontsize=11, fontweight='bold', color='#1f77b4')
    ax_vss.set_title('Comparativo da Rede de Magnetômetros no Brasil — Abril e Maio de 2024\n(Destaque para o início das chuvas no RS e a Supertempestade GLE 74 de 10-11/Maio)', fontsize=13, fontweight='bold', pad=12)
    ax_vss.grid(True, linestyle='--', alpha=0.6)
    ax_vss.legend(loc='upper left', frameon=True)
    ax_vss.axvspan(datetime.datetime(2024, 5, 10, 12), datetime.datetime(2024, 5, 12, 12), color='red', alpha=0.18, label='GLE 74 / Tempestade G5')

# São Martinho da Serra - RS (Filtrado e Limpo)
if not df_sms.empty:
    ax_sms.plot(df_sms['datetime'], df_sms['H'], color='#2ca02c', linewidth=1.2, label='Magnetômetro SMS (São Martinho da Serra - RS) [Próximo a Bento Gonçalves]')
    ax_sms.set_ylabel('SMS H (nT)', fontsize=11, fontweight='bold', color='#2ca02c')
    ax_sms.grid(True, linestyle='--', alpha=0.6)
    ax_sms.legend(loc='upper left', frameon=True)
    ax_sms.axvspan(datetime.datetime(2024, 5, 10, 12), datetime.datetime(2024, 5, 12, 12), color='red', alpha=0.18)

# Cuiabá - MT (CXP)
if not df_cxp.empty:
    ax_cxp.plot(df_cxp['datetime'], df_cxp['H'], color='#ff7f0e', linewidth=1.2, label='Magnetômetro CXP (Cuiabá - MT)')
    ax_cxp.set_ylabel('CXP H (nT)', fontsize=11, fontweight='bold', color='#ff7f0e')
    ax_cxp.grid(True, linestyle='--', alpha=0.6)
    ax_cxp.legend(loc='upper left', frameon=True)
    ax_cxp.axvspan(datetime.datetime(2024, 5, 10, 12), datetime.datetime(2024, 5, 12, 12), color='red', alpha=0.18)

ax_cxp.xaxis.set_major_locator(mdates.DayLocator(interval=5))
ax_cxp.xaxis.set_major_formatter(mdates.DateFormatter('%d/%b'))
plt.xticks(rotation=45, ha='right', fontsize=10)
plt.xlabel('Data (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot1 = os.path.join(PLOT_DIR, "comparativo_magnetometros_abril_maio_2024.png")
plt.savefig(file_plot1, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico 1 salvo: {file_plot1}")

# ---------------------------------------------------------
# GRÁFICO 2: GTEX TEC (IONOSFERA EM CAXIAS DO SUL / BENTO GONÇALVES - RS)
# ---------------------------------------------------------
fig2, ax_tec = plt.subplots(figsize=(14, 6))

if not df_tec.empty:
    ax_tec.plot(df_tec['datetime'], df_tec['TEC'], color='#9467bd', linewidth=1.2, label='Conteúdo Total de Elétrons (TEC - GTEX) em Caxias do Sul / Bento Gonçalves (RSCL)')
    ax_tec.set_ylabel('TEC (TECU = 10^16 el/m²)', fontsize=11, fontweight='bold', color='#9467bd')
    ax_tec.set_title('Serie Temporal Ionosférica (TEC - GTEX INPE) na Serra Gaúcha — Abril e Maio de 2024\nEstação RSCL (Caxias do Sul - RS, Vizinha a Bento Gonçalves)', fontsize=13, fontweight='bold', pad=12)
    ax_tec.grid(True, linestyle='--', alpha=0.6)
    
    # Destacar pico das chuvas no RS e tempestade solar GLE 74
    ax_tec.axvspan(datetime.datetime(2024, 4, 27), datetime.datetime(2024, 5, 5), color='#0066cc', alpha=0.2, label='Pico Principal das Chuvas no RS (27/Abr - 05/Mai)')
    ax_tec.axvspan(datetime.datetime(2024, 5, 10, 12), datetime.datetime(2024, 5, 12, 12), color='red', alpha=0.25, label='GLE 74 & Depressão Ionosférica (10-12/Mai)')
    ax_tec.legend(loc='upper left', frameon=True, fontsize=10)

ax_tec.xaxis.set_major_locator(mdates.DayLocator(interval=4))
ax_tec.xaxis.set_major_formatter(mdates.DateFormatter('%d/%b'))
plt.xticks(rotation=45, ha='right', fontsize=10)
plt.xlabel('Data (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot2 = os.path.join(PLOT_DIR, "gtex_tec_serra_gaucha_abril_maio_2024.png")
plt.savefig(file_plot2, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico 2 salvo: {file_plot2}")

# ---------------------------------------------------------
# GRÁFICO 3: PAINEL INTEGRADO (MAGNETÔMETRO + GTEX TEC + ÍNDICE KSA + EVENTOS RS)
# ---------------------------------------------------------
fig3, (ax_p1, ax_p2, ax_p3, ax_p4) = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

# P1: Magnetômetro VSS (Referência Nacional Limpa)
if not df_vss.empty:
    ax_p1.plot(df_vss['datetime'], df_vss['H'], color='#1f77b4', linewidth=1.2, label='Campo Magnético H (nT) - Vassouras (VSS/RJ)')
    ax_p1.set_ylabel('H (nT)', fontsize=10, fontweight='bold', color='#1f77b4')
    ax_p1.set_title('Painel Integrado Clima Espacial & Eventos no RS (Abril e Maio de 2024)', fontsize=13, fontweight='bold', pad=10)
    ax_p1.grid(True, linestyle='--', alpha=0.6)
    ax_p1.legend(loc='upper left', frameon=True)

# P2: Ionosfera TEC RSCL (Caxias do Sul / Bento Gonçalves)
if not df_tec.empty:
    ax_p2.plot(df_tec['datetime'], df_tec['TEC'], color='#9467bd', linewidth=1.2, label='Ionosfera TEC (RSCL - Caxias do Sul / Bento Gonçalves)')
    ax_p2.set_ylabel('TEC (TECU)', fontsize=10, fontweight='bold', color='#9467bd')
    ax_p2.grid(True, linestyle='--', alpha=0.6)
    ax_p2.legend(loc='upper left', frameon=True)

# P3: Índice Geomagnético KSA
if not df_ksa.empty:
    colors_k = ['#2ca02c' if k < 5 else ('#ff7f0e' if k < 7 else '#d62728') for k in df_ksa['K_index']]
    ax_p3.bar(df_ksa['datetime'], df_ksa['K_index'], width=0.1, color=colors_k, alpha=0.85, label='Índice KSA (K-index América do Sul)')
    ax_p3.set_ylabel('KSA', fontsize=10, fontweight='bold')
    ax_p3.set_ylim(0, 9.5)
    ax_p3.axhline(5, color='orange', linestyle='--', linewidth=1)
    ax_p3.axhline(9, color='red', linestyle='--', linewidth=1.2, label='Tempestade G5 (K=9)')
    ax_p3.grid(True, linestyle='--', alpha=0.6)
    ax_p3.legend(loc='upper left', frameon=True)

# P4: Linha do Tempo dos Eventos
ax_p4.set_ylabel('Cronograma', fontsize=10, fontweight='bold')
ax_p4.axvspan(datetime.datetime(2024, 4, 27), datetime.datetime(2024, 5, 15), color='#0066cc', alpha=0.25, label='Período de Chuvas Extremas / Inundações no RS')
ax_p4.axvspan(datetime.datetime(2024, 4, 29), datetime.datetime(2024, 5, 3), color='#003399', alpha=0.35, label='Pico das Precipitações na Serra Gaúcha (Bento Gonçalves)')
ax_p4.axvspan(datetime.datetime(2024, 5, 10, 12), datetime.datetime(2024, 5, 12, 12), color='#cc0000', alpha=0.5, label='GLE 74 & Supertempestade Geomagnética G5 (10-11/Maio)')
ax_p4.set_yticks([])
ax_p4.legend(loc='upper left', frameon=True, fontsize=9)
ax_p4.grid(True, linestyle='--', alpha=0.6)

ax_p4.xaxis.set_major_locator(mdates.DayLocator(interval=4))
ax_p4.xaxis.set_major_formatter(mdates.DateFormatter('%d/%b'))
plt.xticks(rotation=45, ha='right', fontsize=10)
plt.xlabel('Data (Abril e Maio de 2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot3 = os.path.join(PLOT_DIR, "painel_integrado_rs_abril_maio_2024.png")
plt.savefig(file_plot3, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico 3 salvo: {file_plot3}\n")

print("=========================================================================")
print("  PROCESSAMENTO COMPLETO CONCLUÍDO COM SUCESSO!")
print("=========================================================================")
