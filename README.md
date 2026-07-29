# clima_espacial_amas

Corrente vertical do circuito elétrico atmosférico global (**Jz**), **fumaça** e as
**enchentes do Rio Grande do Sul de maio de 2024**.

Código de análise do projeto AMAS (rede de 14 magnetômetros no Brasil). A pergunta é se
Jz e a carga de aerossol de queimada **modulam** a microfísica das tempestades que
produziram o evento — pela via eletro-microfísica descrita por Brian Tinsley. A hipótese
é de **modulação, não de causa**: a meteorologia (ENSO, MJO, Atlântico) explica o evento;
o que se investiga aqui é um efeito de segunda ordem sobre a eficiência de precipitação.

> **Trabalho em andamento.** As conclusões abaixo são o estado atual da análise, com os
> caveats explicitados. Nada aqui está publicado nem revisado por pares.

---

## O evento: um trem de ondas, não dois pulsos

A divisão em ondas veio dos próprios dados (IVT + flashes GLM + Jz), não de uma escolha
a priori. Definida em `ondas_config.py` — é o único lugar a editar se as janelas mudarem.

| Onda | Período | Caráter | Flashes (GLM) | Jz_rms | IVT máx |
|------|---------|---------|---------------|--------|---------|
| **O0** | 27–30 abr | Surto de umidade, pré-condicionamento | a caracterizar | — | — |
| **O1** | 01–04 mai | Os toros: muito eletrificado | ~575 mil | ~30 | — |
| **O2** | 06–08 mai | 2º surto elétrico | ~949 mil | ~32 | 691 |
| **O3** | 10–13 mai | A cheia: regime estratiforme | ~33 mil | moderado | — |

## Resultado central: dualidade de regime

Duas linhas de evidência independentes separam as ondas eletrificadas da onda da cheia:

- **Raios e Jz** ligam em O1/O2 (convecção profunda com graupel) e desligam em O3.
- **Topo de nuvem** (GOES-16, métricas de 24 h cobrindo dia e noite): O1/O2 com topos de
  −80 a −89 °C, alta fração abaixo de −60 °C e *overshooting*; O3 quente, estratiforme,
  quase sem *overshooting*.
- **Estrutura vertical da vorticidade potencial**: núcleo ciclônico em baixos níveis nos
  toros; em níveis médios (700–600 hPa) na cheia — sistema estratiforme elevado,
  compatível com vórtice de Rossby diabático.
- **Trajetórias** (isentrópicas, 14 dias): as massas de ar que chegam ao RS **não vêm da
  Amazônia**; espiralam sobre o centro-sul e recolhem a fumaça acumulada no corredor.

## Caveats que não devem ser omitidos

- **A AOD de maio é pequena em valor absoluto (~0,06).** O que se analisa é a **anomalia
  relativa** dentro do próprio mês — nos dias das ondas ela está acima da linha de base
  local. Descartar a fumaça de maio por ser "pequena" é ler a variável errada.
- **O pico gigante de setembro/2024 não é contra-exemplo.** É plausível que aquela carga
  de aerossol esteja reforçando a seca amazônica — o lado "seca" da resposta
  não-monotônica de Tinsley, portanto consistente com o mecanismo, não contra ele.
- **A seca amazônica de 2024** é explicada por El Niño defasado (memória de solo e oceano)
  somado ao Atlântico Norte tropical recorde. Controlar ONI, TNA e MJO.
- **Dst não é Jz.** Dst é corrente de anel na magnetosfera; Jz é corrente vertical local.
  Dst alto com Jz baixo em O3 não indica falha de magnetômetro.
- **O coeficiente 0,85** é o coeficiente padronizado da interação AOD×Jz na janela do RS
  (n≈36 dias, R²≈0,38). **Não é "85%"** e **não generaliza** para o 2º semestre, onde o
  resultado é nulo.
- A AOD é coluna total. Falta refinar para aerossol de modo fino/absorvente e um proxy de
  CCN próximo à base da nuvem.

---

## Estrutura

### Aquisição e processamento (rodam por linha de comando)

| Script | O que faz |
|--------|-----------|
| `01_baixar_era5_vpi_slw_ivt.py` | ERA5 em níveis de pressão → VPI multi-nível, água líquida super-resfriada, IVT, precipitação |
| `02_baixar_cams_aod.py` | CAMS EAC4 (ADS) → AOD total, orgânico, black carbon, fumaça |
| `06_altura_fumaca_merra2.py` | MERRA-2, altura da camada de fumaça (baixa-1-apaga-1) |
| `09_trajetorias_3d_isentropico.py` | Retro-trajetórias 3D e isentrópicas, semeadas por nível de VPI |
| `11_glm_relampagos.py` | Flashes GOES-16 GLM por dia (bucket público na AWS) |
| `12_topo_nuvem_dia_noite.py` | Métricas de topo de nuvem por onda, 24 h, resolvendo dia e noite |
| `13_rosenfeld_celulas.py` | Análise de Rosenfeld por célula: núcleo a −55 °C, entorno até −10 °C, frente × traseira pelo movimento |
| `14_baixar_meteo.py` | ERA5 single-level: MSLP, T2m, orvalho, vento 10 m, CAPE, CIN, TCWV, precipitação, K, Total Totals, IVT |
| `15_inventario_dados.py` | Varre as pastas e monta a tabela do que existe: variável, datas, níveis, grade |

### Notebooks interativos (abrem sobre dados já baixados, sem download)

| Notebook | O que mostra |
|----------|--------------|
| `nb01_series_ondas.ipynb` | Séries de Jz, raios, IVT, VPI e fumaça com as faixas das ondas e defasagem |
| `nb02_satelite_animacao.ipynb` | Animação GOES-16 nos 16 canais ABI, com GLM sobreposto, exporta GIF |
| `nb03_celulas_rosenfeld.ipynb` | Saídas do script 13: r_e(T) frente × traseira, imagens, tabela |
| `nb04_vpi.ipynb` | VPI interativa: variável × nível × tempo, superfície isentrópica, e uma aba de **qualidade da interpolação** (grade nativa × suavizada, corte vertical com os níveis reais) |

### Apoio

- `ondas_config.py` — define as ondas O0–O3, a caixa de análise (lat −36..−25, lon −60..−47)
  e as cidades de referência. **Editar as ondas só aqui.**
- `viz_helpers.py` — navegação GOES-16 ABI, downloader com cache, leitores, séries e os
  helpers de mapa. Todo mapa é criado por `novo_mapa()`, que devolve um `GeoAxes` do
  cartopy já com costa, fronteiras, estados, cidades e grade; `mapa_ref()` **levanta
  `TypeError`** se receber um eixo comum, em vez de falhar em silêncio.
- `tools/nb_limpa.py` — filtro que remove as saídas dos notebooks nos commits.

---

## Dados

**Os dados brutos não estão neste repositório** — são mais de 6 GB (ERA5, CAMS, GOES-16,
MERRA-2) e todos são reproduzíveis pelos scripts acima. O que está versionado são as
**tabelas derivadas** em `resultados/*.csv` (~2,7 MB), suficientes para refazer as séries
e as figuras sem baixar nada:

- `rede_completa_14_estacoes_currents_2024.csv` — Jz da rede de 14 magnetômetros, 2024
  inteiro, passo de 15 min
- `cams_aod_diario_*.csv` — AOD e fumaça (orgânico + black carbon) por região e janela
- `era5_diario_*.csv`, `meteo_diario_*.csv`, `meteo_horario_*.csv` — meteorologia
- `glm_flashes_rs_*.csv` — flashes por dia
- `topo_nuvem_dia_noite.csv` — métricas de topo por onda
- `traj_3d.csv`, `traj_isentropico.csv`, `trajetorias_rs.csv` — trajetórias
- `kp_dst_2024.csv` — índices geomagnéticos
- `tabela_diaria_integrada_2024.csv` — tabela integrada diária

Detalhes de origem e credenciais em `LEIA-ME_dados.md`.

### Credenciais necessárias para rebaixar

- **ERA5** (scripts 01, 14): conta no CDS, `~/.cdsapirc`
- **CAMS** (script 02): conta no ADS, `~/.cdsapirc` apontando para o ADS
- **MERRA-2, CALIPSO, MODIS** (02b, 06, 07): conta Earthdata, `~/.netrc` via `earthaccess`
- **GOES-16** (11, 12, 13, nb02): bucket público, acesso anônimo, sem credencial

Nenhuma credencial é lida do repositório — todas vêm do diretório do usuário.

## Instalação

```
conda env create -f environment.yml
conda activate amas
```

Depois, para que o git guarde os notebooks sem as saídas:

```
git config filter.nbclean.clean "python tools/nb_limpa.py"
```

## Reproduzir

Ordem sugerida: `15` (inventário, para ver o que já existe) → `01` e `14` (ERA5) →
`02` (CAMS) → `11` (GLM) → `12` e `13` (GOES-16) → `09` (trajetórias). Depois abra os
notebooks, que leem as saídas.

Os scripts 12 e 13 baixam muitas imagens de satélite e são os mais demorados — rode-os
separado, não junto com a inspeção interativa.

## Licença

MIT, ver `LICENSE`. Os dados de origem seguem as licenças de ECMWF/Copernicus, NOAA e NASA.
