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
PLOT_DIR = os.path.join(BASE_DIR, "resultados/graficos")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

print("=========================================================================")
print("  CÁLCULO DA REDE MULTI-ESTAÇÕES DE DENSIDADE DE CORRENTE J (Jx, Jy, Jz)")
print("  Inversão de Gradientes Espaciais — Ano de 2024")
print("=========================================================================\n")

# Estações selecionadas com alta qualidade e ampla cobertura em 2024
st_coords = {
    'SMS': {'lat': -29.44, 'lon': -53.82, 'name': 'São Martinho da Serra - RS'},
    'RGA': {'lat': -32.03, 'lon': -52.09, 'name': 'Rio Grande - RS'},
    'SJC': {'lat': -23.21, 'lon': -45.96, 'name': 'São José dos Campos - SP'},
    'VSS': {'lat': -22.40, 'lon': -43.65, 'name': 'Vassouras - RJ'},
    'CXP': {'lat': -15.55, 'lon': -56.07, 'name': 'Cuiabá - MT'},
    'ARA': {'lat': -5.65,  'lon': -48.12, 'name': 'Araguatins - TO'}
}

# Converter coordenadas para km em relação ao centro da rede (RS / Sul)
ref_lat = -29.0
ref_lon = -52.0
R_earth = 6371.0 # km

for st, info in st_coords.items():
    dlat = np.radians(info['lat'] - ref_lat)
    dlon = np.radians(info['lon'] - ref_lon)
    info['x_km'] = R_earth * dlon * np.cos(np.radians(ref_lat)) # Leste
    info['y_km'] = R_earth * dlat # Norte

start_date = datetime.date(2024, 1, 1)
end_date = datetime.date(2024, 12, 31)
num_days = (end_date - start_date).days + 1
date_list = [start_date + datetime.timedelta(days=i) for i in range(num_days)]

def parse_station_data(st_name):
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
                            h_val = float(parts[6]) # H
                            z_val = float(parts[7]) # Z
                            d_val = float(parts[5]) if len(parts) > 5 else 0.0 # Declinação D
                            if 10000 <= h_val <= 35000:
                                dt_obj = datetime.datetime(y, m, d, hh, mm)
                                # Componentes X (Norte) e Y (Leste)
                                d_rad = np.radians(d_val)
                                x_val = h_val * np.cos(d_rad)
                                y_val = h_val * np.sin(d_rad)
                                recs.append({'datetime': dt_obj, 'X': x_val, 'Y': y_val, 'Z': z_val, 'H': h_val})
                        except ValueError:
                            continue
    df = pd.DataFrame(recs)
    if not df.empty:
        df = df.drop_duplicates('datetime').sort_values('datetime').reset_index(drop=True)
        # Obter anomalia/perturbação ΔX, ΔY, ΔZ em relação à mediana móvel diária
        df['X_base'] = df['X'].rolling(window=1440, center=True, min_periods=60).median()
        df['Y_base'] = df['Y'].rolling(window=1440, center=True, min_periods=60).median()
        df['Z_base'] = df['Z'].rolling(window=1440, center=True, min_periods=60).median()
        df['dX'] = df['X'] - df['X_base']
        df['dY'] = df['Y'] - df['Y_base']
        df['dZ'] = df['Z'] - df['Z_base']
    return df

print(" Carregando e alinhando dados da rede multi-estações...")
station_dfs = {}
for st in st_coords.keys():
    df = parse_station_data(st)
    if not df.empty:
        station_dfs[st] = df.set_index('datetime')
        print(f"  [+] {st} ({st_coords[st]['name']}): {len(df)} pontos")

# Criar índice temporal unificado (resolução de 15 minutos para estabilidade espacial)
all_times = pd.date_range(start='2024-01-01', end='2024-12-31 23:59', freq='15min')

current_results = []
mu0 = 4 * np.pi * 1e-7 # H/m

print("\n Calculando a inversão de gradientes espaciais para o vetor de densidade de corrente J(t)...")
for t in all_times:
    pts_x = []
    pts_y = []
    obs_dX = []
    obs_dY = []
    obs_dZ = []
    
    for st, df in station_dfs.items():
        if t in df.index:
            row = df.loc[t]
            if isinstance(row, pd.DataFrame): row = row.iloc[0]
            if not np.isnan(row['dX']) and not np.isnan(row['dY']) and not np.isnan(row['dZ']):
                pts_x.append(st_coords[st]['x_km'] * 1000.0) # metros
                pts_y.append(st_coords[st]['y_km'] * 1000.0) # metros
                obs_dX.append(row['dX'] * 1e-9) # Tesla
                obs_dY.append(row['dY'] * 1e-9) # Tesla
                obs_dZ.append(row['dZ'] * 1e-9) # Tesla
                
    # Necessário pelo menos 3 estações ativas simultaneamente
    if len(pts_x) >= 3:
        try:
            # Matriz de design para ajuste planar (Gradient matrix)
            # ΔZ = Z0 + dZ/dx * x + dZ/dy * y
            # ΔX = X0 + dX/dx * x + dX/dy * y
            # ΔY = Y0 + dY/dx * x + dY/dy * y
            A = np.column_stack([np.ones(len(pts_x)), pts_x, pts_y])
            
            # Resolver mínimos quadrados para dZ/dx e dZ/dy
            coeff_Z, _, _, _ = np.linalg.lstsq(A, obs_dZ, rcond=None)
            dZ_dx = coeff_Z[1] # T/m
            dZ_dy = coeff_Z[2] # T/m
            
            # Resolver mínimos quadrados para dX/dy e dY/dx
            coeff_X, _, _, _ = np.linalg.lstsq(A, obs_dX, rcond=None)
            coeff_Y, _, _, _ = np.linalg.lstsq(A, obs_dY, rcond=None)
            dX_dy = coeff_X[2] # T/m
            dY_dx = coeff_Y[1] # T/m
            
            # Lei de Ampère para componentes da densidade de corrente equivalente:
            # Jx = (1/mu0) * dZ/dy
            # Jy = -(1/mu0) * dZ/dx
            # Jz = (1/mu0) * (dY/dx - dX/dy)  (Proxy vertical)
            
            Jx = (1.0 / mu0) * dZ_dy * 1e6 # \mu A / m^2
            Jy = -(1.0 / mu0) * dZ_dx * 1e6 # \mu A / m^2
            Jz = (1.0 / mu0) * (dY_dx - dX_dy) * 1e9 # pA / m^2 ou nA / m^2
            
            # Limpeza de outliers numéricos de matrizes mal-condicionadas
            if abs(Jx) < 500 and abs(Jy) < 500 and abs(Jz) < 10000:
                current_results.append({
                    'datetime': t,
                    'Jx_muA_m2': Jx,
                    'Jy_muA_m2': Jy,
                    'Jz_pA_m2': Jz,
                    'J_horiz_mag': np.sqrt(Jx**2 + Jy**2),
                    'n_stations': len(pts_x)
                })
        except Exception:
            continue

df_J = pd.DataFrame(current_results)
if not df_J.empty:
    df_J = df_J.sort_values('datetime').reset_index(drop=True)
    csv_out = os.path.join(BASE_DIR, "dados/jz/rede_multiestacoes_currents_2024.csv")
    df_J.to_csv(csv_out, index=False)
    print(f" Cátculos concluídos com sucesso! {len(df_J)} pontos de corrente J calculados.")
    print(f" Tabela salva em: {csv_out}")

# ---------------------------------------------------------
# GERAÇÃO DOS GRÁFICOS DO VETOR J EM 2024
# ---------------------------------------------------------
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 11), sharex=True)

if not df_J.empty:
    # 1. Magnitude da Corrente Horizontal Equivalente J_horiz (muA/m^2)
    ax1.plot(df_J['datetime'], df_J['J_horiz_mag'], color='#1f77b4', linewidth=1, label='Magnitude da Corrente Horizontal J_horiz (μA/m²)')
    ax1.set_ylabel('J_horiz (μA/m²)', fontsize=11, fontweight='bold', color='#1f77b4')
    ax1.set_title('Densidade de Corrente Elétrica Equivalente J(t) Calculada via Rede Multi-Estações em 2024\n(Inversão dos Gradientes Espaciais: SMS, RGA, SJC, VSS, CXP, ARA)', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right', frameon=True)
    
    # 2. Componentes Horizontais Jx (Leste) e Jy (Norte)
    ax2.plot(df_J['datetime'], df_J['Jx_muA_m2'], color='#ff7f0e', linewidth=0.9, alpha=0.85, label='Jx (Componente Leste - μA/m²)')
    ax2.plot(df_J['datetime'], df_J['Jy_muA_m2'], color='#2ca02c', linewidth=0.9, alpha=0.85, label='Jy (Componente Norte - μA/m²)')
    ax2.set_ylabel('Jx, Jy (μA/m²)', fontsize=11, fontweight='bold')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper right', frameon=True)
    
    # 3. Componente Vertical Proxy Jz (pA/m^2 ou nA/m^2)
    ax3.plot(df_J['datetime'], df_J['Jz_pA_m2'], color='#9467bd', linewidth=0.8, alpha=0.85, label='Jz (Densidade de Corrente Vertical Atmosférica - pA/m²)')
    ax3.set_ylabel('Jz (pA/m²)', fontsize=11, fontweight='bold', color='#9467bd')
    ax3.grid(True, linestyle='--', alpha=0.6)
    ax3.legend(loc='upper right', frameon=True)

# Sombreamento dos eventos de 2024
for ax in [ax1, ax2, ax3]:
    ax.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.22, label='Tempestade G4 (Março)')
    ax.axvspan(datetime.datetime(2024, 4, 19), datetime.datetime(2024, 4, 21), color='#e377c2', alpha=0.25)
    ax.axvspan(datetime.datetime(2024, 4, 27), datetime.datetime(2024, 5, 15), color='#0066cc', alpha=0.2, label='Chuvas RS')
    ax.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35, label='Supertempestade G5 / GLE 74')

ax3.xaxis.set_major_locator(mdates.MonthLocator())
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.xlabel('Mês (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot = os.path.join(PLOT_DIR, "rede_multiestacoes_jz_2024.png")
plt.savefig(file_plot, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico da rede multi-estações J(t) salvo em: {file_plot}")
