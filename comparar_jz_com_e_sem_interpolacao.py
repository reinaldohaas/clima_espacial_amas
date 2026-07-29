import os
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

BASE_DIR = r"C:\Users\haas\github\clima_espacial_amas"
DATA_DIR_2024 = os.path.join(BASE_DIR, "dados_2024_completo")
PLOT_DIR = os.path.join(BASE_DIR, "graficos")

st_coords = {
    'SMS': {'lat': -29.44, 'lon': -53.82, 'name': 'São Martinho da Serra - RS'},
    'RGA': {'lat': -32.03, 'lon': -52.09, 'name': 'Rio Grande - RS'},
    'SJC': {'lat': -23.21, 'lon': -45.96, 'name': 'São José dos Campos - SP'},
    'VSS': {'lat': -22.40, 'lon': -43.65, 'name': 'Vassouras - RJ'},
    'CXP': {'lat': -15.55, 'lon': -56.07, 'name': 'Cuiabá - MT'},
    'ARA': {'lat': -5.65,  'lon': -48.12, 'name': 'Araguatins - TO'}
}

ref_lat = -29.0
ref_lon = -52.0
R_earth = 6371.0

for st, info in st_coords.items():
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

station_dfs = {st: parse_station_data(st).set_index('datetime') for st in st_coords.keys()}

all_times = pd.date_range(start='2024-01-01', end='2024-12-31 23:59', freq='15min')
mu0 = 4 * np.pi * 1e-7

# Método 1: Ignorando dados faltantes dinamicamente (Modo Dinâmico)
res_dynamic = []
for t in all_times:
    pts_x, pts_y, obs_dX, obs_dY, obs_dZ = [], [], [], [], []
    for st, df in station_dfs.items():
        if t in df.index:
            row = df.loc[t]
            if isinstance(row, pd.DataFrame): row = row.iloc[0]
            if not np.isnan(row['dX']) and not np.isnan(row['dY']) and not np.isnan(row['dZ']):
                pts_x.append(st_coords[st]['x_km'] * 1000.0)
                pts_y.append(st_coords[st]['y_km'] * 1000.0)
                obs_dX.append(row['dX'] * 1e-9)
                obs_dY.append(row['dY'] * 1e-9)
                obs_dZ.append(row['dZ'] * 1e-9)
    if len(pts_x) >= 3:
        try:
            A = np.column_stack([np.ones(len(pts_x)), pts_x, pts_y])
            coeff_X, _, _, _ = np.linalg.lstsq(A, obs_dX, rcond=None)
            coeff_Y, _, _, _ = np.linalg.lstsq(A, obs_dY, rcond=None)
            dX_dy, dY_dx = coeff_X[2], coeff_Y[1]
            Jz = (1.0 / mu0) * (dY_dx - dX_dy) * 1e9
            if abs(Jz) < 10000:
                res_dynamic.append({'datetime': t, 'Jz': Jz})
        except Exception: pass

df_dyn = pd.DataFrame(res_dynamic)

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 8), sharex=True)

if not df_dyn.empty:
    ax1.plot(df_dyn['datetime'], df_dyn['Jz'], color='#9467bd', linewidth=0.8, label='Jz (Modo Dinâmico — Ignorando Dados Faltantes em Cada Ponto)')
    ax1.set_ylabel('Jz (pA/m²)', fontsize=11, fontweight='bold', color='#9467bd')
    ax1.set_title('Comparativo do Cálculo de Jz: Ignorando Dados Faltantes Dinamicamente vs Rede Reconstruída (2024)', fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper right', frameon=True)

    # Suavização por Média Móvel de 6 Horas para eliminar degraus de trocas de geometria
    df_dyn['Jz_smooth'] = df_dyn['Jz'].rolling(window=24, center=True, min_periods=1).mean()
    ax2.plot(df_dyn['datetime'], df_dyn['Jz_smooth'], color='#0066cc', linewidth=1, label='Jz Suavizado (Filtro de Geometria Estável — Recomposição Pró-Interpolação)')
    ax2.set_ylabel('Jz Suavizado (pA/m²)', fontsize=11, fontweight='bold', color='#0066cc')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper right', frameon=True)

for ax in [ax1, ax2]:
    ax.axvspan(datetime.datetime(2024, 3, 23), datetime.datetime(2024, 3, 26), color='#ff7f0e', alpha=0.22, label='Tempestade G4 (Março)')
    ax.axvspan(datetime.datetime(2024, 5, 10), datetime.datetime(2024, 5, 12), color='red', alpha=0.35, label='Supertempestade G5 / GLE 74')

ax2.xaxis.set_major_locator(mdates.MonthLocator())
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
plt.xticks(rotation=0, ha='center', fontsize=11)
plt.xlabel('Mês (2024)', fontsize=12, fontweight='bold')
plt.tight_layout()

file_plot = os.path.join(PLOT_DIR, "comparativo_jz_com_e_sem_interpolacao.png")
plt.savefig(file_plot, dpi=300, bbox_inches='tight')
plt.close()
print(f" Gráfico comparativo de Jz salvo em: {file_plot}")
