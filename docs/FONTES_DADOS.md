# FONTES DE DADOS — projeto Eventos_toro

Toda fonte de onde os scripts baixam dado, com URL, formato e ressalvas de acesso.
Regra do projeto: **cache primeiro** — cada série é lida do cache (`dados_*/`) e só o que
falta é baixado; nada é apagado ou rebaixado. Portal-chave brasileiro: **https://embracedata.inpe.br/**

## 1. Raio cósmico e múons

| Dado | Fonte | URL | Formato / notas |
|---|---|---|---|
| GCR nêutrons (OULU, IRK3, MXCO, JBGO, KERG, JUNG1) | **NMDB NEST** | https://www.nmdb.eu/nest/ | `draw_graph.php` ascii. `corr_for_efficiency` (tabchoice=revori) **já vem em %**, não é contagem. Citar NMDB e o PI de cada estação. |
| Múons São Martinho da Serra (RS) | **GMDN / Shinshu Univ.** | http://cosray.shinshu-u.ac.jp/crest/DB/Public/Archives/GMDN/ | Canal vertical, 1 h, corrigido de pressão. Citar GMDN — hdl.handle.net/10091/0002001448 |

## 2. Geomagnetismo e vento solar

| Dado | Fonte | URL | Formato / notas |
|---|---|---|---|
| Kp | **GFZ Potsdam** | https://kp.gfz-potsdam.de/ | JSON. CC BY 4.0 |
| Dst, AE | **WDC Kyoto** | https://wdc.kugi.kyoto-u.ac.jp/ | HTML mensal (final/provisional/realtime) |
| Ey (=−V×Bz), AE | **NASA/SPDF OMNIWeb** | https://omniweb.gsfc.nasa.gov/ | OMNI2 horário |
| Prótons >10 MeV | **GOES-16 SGPS L2 — NOAA/NCEI** | https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/goes16/l2/data/sgps-l2-avg5m/ | netCDF diário |
| ΔH magnetômetro São Martinho (SMS) | **Embrace MagNet / INPE** | https://embracedata.inpe.br/magnetometer/ | Diário 1 min (`sms<DD><mmm>.<YY>m`), H na col 7. **Tem buracos em maio/2024 (~10–13/05).** |
| ΔH magnetômetro Vassouras (VSS) | **INTERMAGNET** (GIN Edimburgo/BGS) | https://imag-data.bgs.ac.uk/GIN_V1/ · https://intermagnet.org/ | IAGA-2002 via serviço REST |

## 3. Ionosfera

| Dado | Fonte | URL | Formato / notas |
|---|---|---|---|
| TEC / IONEX (caixa AMAS/RS) | **EMBRACE / INPE** | https://embracedata.inpe.br/ionex/ | IONEX diário (`INPE...I`) |

## 4. GNSS troposférico (ZTD / PWV)

| Dado | Fonte | URL | Formato / notas |
|---|---|---|---|
| ZTD (proxy de PWV) | **Nevada Geodetic Laboratory (NGL)** | https://geodesy.unr.edu/gps_timeseries/trop/ | **Só https** (http:80 dá timeout). SMAR e várias RBMC **não têm** produto `.trop.zip`. |
| Alternativas BR (pendente) | **IBGE/RBMC** · **PWV EMBRACE** | https://www.ibge.gov.br/geociencias/ · https://embracedata.inpe.br/ | RBMC tem SMAR (Santa Maria), mas sem trop no NGL |

## 5. Satélite e meteorologia (scripts 02/04/05/07/08/10)

| Dado | Fonte | URL | Formato / notas |
|---|---|---|---|
| GOES-16 ABI (topo de nuvem, r_e(T), BTD) | **AWS S3 — NOAA GOES-16** | s3://noaa-goes16 · https://noaa-goes16.s3.amazonaws.com | netCDF ABI L1b/L2 |
| Radiossondagens (SBSM/SBPA/SBFI, skew-T) | **Univ. of Wyoming** | https://weather.uwyo.edu/upperair/sounding.html | Ressalva: pressões duplicadas |
| Cicatrizes (NDVI Sentinel-2) | **AWS / Earth Search (Element84)** | https://earth-search.aws.element84.com/v1 | STAC / COG |
| VPI (vorticidade potencial isentrópica) | **Copernicus CDS — ERA5** | https://cds.climate.copernicus.eu/ | Requer chave CDS |

## 6. Sismologia e mineração (script 11)

| Dado | Fonte | URL | Formato / notas |
|---|---|---|---|
| Catálogo/formas de onda sísmicas | **RSBR / Centro de Sismologia USP** (FDSN) | http://moho.iag.usp.br | Ressalva: `endtime` com hora ≠ 00:00:00 retorna vazio |
| Lavras ativas (discriminação de desmonte) | **SIGMINE / ANM** | https://geo.anm.gov.br | Concessões/licenciamento |

## Ressalvas de acesso já mapeadas (ver memória do projeto)

- **NMDB eficiência já vem em %** — não converter nem cortar por MAD (apagaria o Forbush).
- **NGL só por https**; SMAR/RBMC sem produto troposférico.
- **SMS (Embrace) tem buracos em maio/2024**; VSS (INTERMAGNET) entra como referência robusta.
- **Wyoming**: pressões duplicadas. **FDSN USP**: `endtime` precisa hora 00:00:00. **NumPy 2**: sem `np.trapz`.
