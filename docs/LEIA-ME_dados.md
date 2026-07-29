# Aquisição de AOD, água supercongelada, VPI e IVT — teste da hipótese eletro-microfísica

Objetivo: trazer as variáveis que faltam para testar, com dados independentes, o mecanismo
das Seções 5–9 do documento de fundamentação (anti-varredura + fumaça → seca + VPI; e o caso RS).

## O que cada variável testa
- **AOD 550 nm (total e de fumaça = orgânico + carbono negro)** — carga de aerossol/fumaça. Proxy da Via 3.
- **Água líquida supercongelada (SLW)** — água retida na nuvem a T<0 °C sem virar chuva. Assinatura direta do Estado A (condensa, não precipita).
- **VPI de baixos níveis (850/700 hPa)** — a anomalia ciclônica gerada pelo calor latente sem chuva.
- **IVT** — o corredor de umidade (rio atmosférico / SALLJ) que abastece a Serra Gaúcha.

## Como rodar (dois caminhos)
**Caminho A — você roda aí (recomendado; igual ao Kp/Dst).**
1. `pip install "cdsapi>=0.7.2" xarray netCDF4 numpy pandas scipy matplotlib`
2. Credenciais:
   - ERA5 → `~/.cdsapirc` com `url: https://cds.climate.copernicus.eu/api` e sua `key` (perfil CDS).
   - CAMS (AOD) → conta no **ADS** (`https://ads.atmosphere.copernicus.eu/`); use a key do ADS.
     (Se usar os dois, rode o passo 01 com o .cdsapirc do CDS e o passo 02 com o do ADS,
      ou passe `key=`/`url=` direto no `cdsapi.Client(...)`.)
3. Rodar primeiro a janela do RS (rápida), depois o ano:
   ```
   python 01_baixar_era5_vpi_slw_ivt.py --modo rs
   python 02_baixar_cams_aod.py            --modo rs
   python 01_baixar_era5_vpi_slw_ivt.py --modo ano
   python 02_baixar_cams_aod.py            --modo ano
   python 03_processar_e_correlacionar.py
   ```
4. Me devolva os CSVs de `resultados/` (era5_diario_*, cams_aod_diario_*, tabela_diaria_integrada_2024.csv)
   e as figuras. Eu faço a análise conjunta e incorporo ao documento.

**Caminho B — eu rodo aqui.** Os servidores do Copernicus/NASA estão acessíveis deste ambiente;
o que falta é a chave. Se preferir, me passe a forma de autenticar (não cole segredos no chat sem necessidade —
podemos combinar um jeito seguro) e eu executo os quatro passos.

## Domínios (edite em DOMINIOS nos scripts se quiser)
- `brasil`: N6 O-74 S-34 L-34 (rede de magnetômetros) — para o teste anual AOD×Jz.
- `rs`: N-27 O-58 S-34 L-49 — para VPI/IVT/SLW do evento da enchente.

## Opcional — aerossol por LIDAR (estrutura vertical)
Para saber **em que altura** está a fumaça (onde o Jz cruza a camada), o próximo passo é
CALIPSO/CALIOP (extinção de aerossol e máscara de tipo "smoke"). É mais pesado (grânulos orbitais HDF).
Se quiser, escrevo o `04_baixar_calipso.py`; ele é útil sobretudo para o caso RS e para setembro.

## Notas
- Passo 01 usa integrais verticais de fluxo de vapor do ERA5 (IVT direto) e integra clwc onde 235<T<273 K (SLW).
- VPI do ERA5 vem em K m² kg⁻¹ s⁻¹; o script converte para PVU (×1e6). No HS, ciclônico = VPI negativa.
- Se algum nome de variável do netCDF vier diferente (o CDS mudou short-names algumas vezes), me avise o erro que ajusto.
