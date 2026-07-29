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

```
clima_espacial_amas/
├── scripts/      todo o codigo .py (os do evento do Toro com prefixo toro_)
│   └── antigos/  versoes superadas, mantidas por referencia
├── notebooks/    nb01..nb04, interativos, abrem sobre dados ja baixados
├── tools/        nb_limpa.py, concat_nc.py, migrar.py
├── dados/        ENTRADAS: tudo que veio de fora
│   ├── era5/ cams/ merra2/ goes/ goesp/ tec/ gnss/ geomag/ magnet/
│   ├── muons/ nmdb/ geo/ indices/
│   ├── jz/       series dos magnetometros (versionadas)
│   ├── amas/ magnetometros_2023/ magnetometros_2024/
│   └── cache_abi/
├── resultados/   SAIDAS: tudo que os scripts produzem
│   ├── *.csv     tabelas derivadas (versionadas)
│   ├── fig_*.png figuras
│   ├── rosenfeld_celulas/ graficos/ graficos_estacoes/ saidas_toro/
│   └── logs/
└── docs/         guias, fundamentacao teorica, fontes dos dados
```

O criterio da separacao e a **origem**: em `dados/` fica o que foi baixado de um
servico externo (ERA5, CAMS, GOES, MERRA-2, Kp/Dst do GFZ e do WDC Kyoto); em
`resultados/` fica exclusivamente o que algum script escreveu. Os scripts de
download aceitam `--datadir` (padrao `dados`) e `--outdir` (padrao `resultados`).

## Dados

**Os dados brutos não estão neste repositório** — são mais de 6 GB (ERA5, CAMS, GOES-16,
MERRA-2) e todos são reproduzíveis pelos scripts acima. O que está versionado são as
**tabelas derivadas** em `resultados/*.csv` (~2,7 MB), suficientes para refazer as séries
e as figuras sem baixar nada:

- `dados/jz/rede_completa_14_estacoes_currents_2024.csv` — Jz da rede de 14
  magnetômetros, 2024 inteiro, passo de 15 min (é entrada, não resultado)
- `cams_aod_diario_*.csv` — AOD e fumaça (orgânico + black carbon) por região e janela
- `era5_diario_*.csv`, `meteo_diario_*.csv`, `meteo_horario_*.csv` — meteorologia
- `glm_flashes_rs_*.csv` — flashes por dia
- `topo_nuvem_dia_noite.csv` — métricas de topo por onda
- `traj_3d.csv`, `traj_isentropico.csv`, `trajetorias_rs.csv` — trajetórias
- `dados/indices/kp_dst_2024.csv` — índices geomagnéticos, baixados do GFZ e do WDC Kyoto
- `tabela_diaria_integrada_2024.csv` — tabela integrada diária

Detalhes de origem e credenciais em `docs/LEIA-ME_dados.md` e `docs/FONTES_DADOS.md`.

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

Rode sempre a partir da raiz do projeto (`python scripts/01_...py`); os notebooks
se reposicionam sozinhos na raiz pela primeira célula.

Ordem sugerida: `15` (inventário, para ver o que já existe) → `01` e `14` (ERA5) →
`02` (CAMS) → `11` (GLM) → `12` e `13` (GOES-16) → `09` (trajetórias). Depois abra os
notebooks, que leem as saídas.

Os scripts 12 e 13 baixam muitas imagens de satélite e são os mais demorados — rode-os
separado, não junto com a inspeção interativa.

## Licença

MIT, ver `LICENSE`. Os dados de origem seguem as licenças de ECMWF/Copernicus, NOAA e NASA.
