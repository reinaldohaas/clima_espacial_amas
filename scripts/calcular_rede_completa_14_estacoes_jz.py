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
DATA_DIR_2024 = os.path.join(BASE_DIR, "dados/magnetometros_2024")
PLOT_DIR = os.path.join(BASE_DIR, "resultados/graficos")

os.makedirs(DATA_DIR_2024, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

print("=========================================================================")
print("  INVERSÃO ESPACIAL COMPLETA: TODAS AS 14 ESTAÇÕES ATIVAS DO BRASIL (2024)")
print("  Cálculo de J (Jx, Jy, Jz) por Mínimos Quadrados com Overdetermination Máxima")
print("=========================================================================\n")

# Coordenadas de TODAS as 14 estações com dados ativos em 2024
all_14_coords = {
    'ARA': {'lat': -5.65,  'lon': -48.12, 'name': 'Araguatins - TO'},
    'EUS': {'lat': -3.89,  'lon': -38.43, 'name': 'Eusébio - CE'},
    'SLZ': {'lat': -2.53,  'lon': -44.30, 'name': 'São Luís - MA'},
    'STM': {'lat': -2.43,  'lon': -54.71, 'name': 'Santarém - PA'},
    'PVE': {'lat': -8.76,  'lon': -63.90, 'name': 'Porto Velho - RO'},
    'CXP': {'lat': -15.55, 'lon': -56.07, 'name': 'Cuiabá - MT'},
    'JAT': {'lat': -17.88, 'lon': -51.72, 'name': 'Jataí - GO'},
    'TCM': {'lat': -23.63, 'lon': -55.02, 'name': 'Tacuru - MS'},
    'SJC': {'lat': -23.21, 'lon': -45.96, 'name': 'São José dos Campos - SP'},
    'VSS': {'lat': -22.40, 'lon': -43.65, 'name': 'Vassouras - RJ'},
    'MED': {'lat': -25.30, 'lon': -54.11, 'name': 'Medianeira - PR'},
    'SMS': {'lat': -29.44, 'lon': -53.82, 'name': 'São Martinho da Serra - RS'},
    'RGA': {'lat': -32.03, 'lon': -52.09, 'name': 'Rio Grande - RS'},
    'CHI': {'lat': -33.69, 'lon': -53.46, 'name': 'Chuí - RS'}
}

ref_lat = -20.0
ref_lon = -50.0
R_earth = 6371.0

for st, info in all_14_coords.items():
    dlat = np.radians(info['lat'] - ref_lat)
    dlon = np.radians(info['lon'] - ref_lon)
    info['x_km'] = R_earth * dlon * np.cos(np.radians(ref_lat))
    info['y_km'] = R_earth * dlat

start_date = datetime.date(2024, 1, 1)
end_date = datetime.date(2024, 12, 31)
num_days = (end_date - start_date).days + 1
date_list = [start_date + datetime.timedelta(days=i) for i in range(num_days)]

def parse_station_data(st_name):
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
                            z_val = float(parts[7])
                            d_val = float(parts[5]) if len(parts) > 5 else 0.0
                            if 10000 <= h_val <= 35000:
                                dt_obj = datetime.datetime(y, m, d, hh, mm)
                                d_rad = np.radians(d_val)
                                x_val = h_val * np.cos(d_rad)
                                y_val = h_val * np.sin(d_rad)
                                recs.append({'datetime': dt_obj, 'X': x_val, 'Y': y_val, 'Z': z_val, 'H': h_val})
                        except ValueError:
                            continue
    df = pd.DataFrame(recs)
    if not df.empty:
        df = df.drop_duplicates('datetime').sort_values('datetime').reset_index(drop=True)
        df['X_base'] = df['X'].rolling(window=1440, center=True, min_periods=60).median()
        df['Y_base'] = df['Y'].rolling(window=1440, center=True, min_periods=60).median()
        df['Z_base'] = df['Z'].rolling(window=1440, center=True, min_periods=60).median()
        df['dX'] = df['X'] - df['X_base']
        df['dY'] = df['Y'] - df['Y_base']
        df['dZ'] = df['Z'] - df['Z_base']
    return df

print(" Carregando dados de TODAS as 14 estações ativas...")
station_dfs = {}
for st in all_14_coords.keys():
    df = parse_station_data(st)
    if not df.empty:
        station_dfs[st] = df.set_index('datetime')
        print(f"  [+] Estação {st} ({all_14_coords[st]['name']}): {len(df)} pontos carregados")

all_times = pd.date_range(start='2024-01-01', end='2024-12-31 23:59', freq='15min')
mu0 = 4 * np.pi * 1e-7

current_results_14 = []

print("\n Calculando a inversão de gradientes espaciais com TODAS as 14 estações simultaneamente...")
for t in all_times:
    pts_x, pts_y, obs_dX, obs_dY, obs_dZ = [], [], [], [], []
    
    for st, df in station_dfs.items():
        if t in df.index:
            row = df.loc[t]
            if isinstance(row, pd.DataFrame): row = row.iloc[0]
            if not np.isnan(row['dX']) and not np.isnan(row['dY']) and not np.isnan(row['dZ']):
                pts_x.append(all_14_coords[st]['x_km'] * 1000.0)
                pts_y.append(all_14_coords[st]['y_km'] * 1000.0)
                obs_dX.append(row['dX'] * 1e-9)
                obs_dY.append(row['dY'] * 1e-9)
                obs_dZ.append(row['dZ'] * 1e-9)
                
    if len(pts_x) >= 3:
        try:
            A = np.column_stack([np.ones(len(pts_x)), pts_x, pts_y])
            coeff_Z, _, _, _ = np.linalg.lstsq(A, obs_dZ, rcond=None)
            dZ_dx, dZ_dy = coeff_Z[1], coeff_Z[2]
            
            coeff_X, _, _, _ = np.linalg.lstsq(A, obs_dX, rcond=None)
            coeff_Y, _, _, _ = np.linalg.lstsq(A, obs_dY, rcond=None)
            dX_dy, dY_dx = coeff_X[2], coeff_Y[1]
            
            Jx = (1.0 / mu0) * dZ_dy * 1e6
            Jy = -(1.0 / mu0) * dZ_dx * 1e6
            Jz = (1.0 / mu0) * (dY_dx - dX_dy) * 1e9
            
            if abs(Jx) < 500 and abs(Jy) < 500 and abs(Jz) < 10000:
                current_results_14.append({
                    'datetime': t,
                    'Jx_muA_m2': Jx,
                    'Jy_muA_m2': Jy,
                    'Jz_pA_m2': Jz,
                    'J_horiz_mag': np.sqrt(Jx**2 + Jy**2),
                    'n_stations_active': len(pts_x)
                })
        except Exception:
            continue

df_J14 = pd.DataFrame(current_results_14)
if not df_J14.empty:
    df_J14 = df_J14.sort_values('datetime').reset_index(drop=True)
    csv_out = os.path.join(BASE_DIR, "dados/jz/rede_completa_14_estacoes_currents_2024.csv")
    df_J14.to_csv(csv_out, index=False)
    print(f" Inversão concluída com sucesso! {len(df_J14)} pontos de corrente J calculados com as 14 estações.")
    print(f" Tabela salva em: {csv_out}")

# ---------------------------------------------------------
# PLOTAGEM DO PAINEL DA REDE COMPLETA DE 14 ESTAÇÕES
# ---------------------------------------------------------
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 12), sharex=True)

if not df_J14.empty:
    # 1. Número de Estações Ativas Simultaneamente por Época
    ax1.plot(df_J14['datetime'], df_J14['n_stations_active'], color='#2ca02c', linewidth=1, label='Número de Estações Ativas Simultaneamente (Máx 14)')
    ax1.set_ylabel('Nº Estações', fontsize=11, fontweight='bold', color='#2ca02c')
    ax1.set_title('Densidade de Corrente J (Jx, Jy, Jz) Usando TODAS as 14 Estações Ativas do Brasil em 2024\n(Inversão por Mínimos Quadrados com Máxima Cobertura Territorial)', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right', frameon=True)
    
    # 2. Magnitude J_horiz (muA/m^2)
    ax2.plot(df_J14['datetime'], df_J14['J_horiz_mag'], color='#1f77b4', linewidth=1, label='Magnitude J_horiz (μA/m²) — Rede Completa de 14 Estações')
    ax2.set_ylabel('J_horiz (μA/m²)', fontsize=11, fontweight='bold', color='#1f77b4')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper right', frameon=True)
    
    # 3. Componentes Jx e Jy
    ax3.plot(df_J14['datetime'], df_J14['Jx_muA_m2'], color='#ff7f0e', linewidth=0.9, alpha=0.85, label='Jx (Componente Leste - μA/m²)')
    ax3.plot(df_J14['datetime'], df_J14['Jy_muA_m2'], color='#d62728', linewidth=0.9, alpha=0.85, label='Jy (Componente Norte - μA/m²)')
    ax3.set_ylabel('Jx, Jy (μA/m²)', fontsize=11, fontweight='bold')
    ax3.grid(True, linestyle='--', alpha=0.6)
    ax3.legend(loc='upper right', frameon=True)
    
    # 4. Componente Vertical Jz (pA/m^2)
    ax4.plot(df_J14['datetime'], df_J14['Jz_pA_m2'], color='#9467bd', linewidth=0.8, alpha=0.85, label='Jz (Corrente Vertical - pA/m²) — Calculada com 14 Estações')
    ax4.set_ylabel('Jz (pA/m²)', fontsize=11, fontweight='bold', color='#9467bd')
    ax4.grid(True, linestyle='--', alpha=0.6)
    ax4.legend(loc='upper right', frameon=True)

for ax in [ax1, ax2, ax3, ax4]:
    ax.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.22, label='Tempestade G4 (Março)')
    ax.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35, label='Supertempestade G5 / GLE 74')

ax4.xaxis.set_major_locator(mdates.MonthLocator())
ax4.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.xlabel('Mês (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot_14 = os.path.join(PLOT_DIR, "rede_completa_14_estacoes_jz_2024.png")
plt.savefig(file_plot_14, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico da rede completa de 14 estações salvo em: {file_plot_14}")
