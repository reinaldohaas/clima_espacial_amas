# GUIA DOS SCRIPTS — quem faz o quê

Pipeline do caso EOCE Taquari-Antas (chuvas 27/04–03/05/2024).
Para rodar tudo de uma vez: `python rodar_tudo.py` (veja flags no fim).

| Script | O que faz | Baixa de | Saída principal |
|---|---|---|---|
| `00_caso.py` | CONFIG CENTRAL: períodos, datas, marcos, rio real (geojson), caixas, pastas padronizadas. Todos importam daqui. | — | (módulo) |
| `01_series_espaciais.py` | TODAS as séries espaciais num só script: GCR multi-estação (NMDB), Kp (GFZ), Dst (Kyoto), AE e Ey (OMNI), prótons (evento), TEC/IONEX com anomalia e teste evento×controle. CACHE PRIMEIRO — só baixa o que falta. Inclui múons de São Martinho (GMDN — medida local do RS, corrigido e SEM correção de pressão), GCR bruto×corrigido e ZTD/PWV GNSS (NGL, estação RBMC via `--gnss`). Gera timeline, multi-rigidez (+FD no corte do RS), TEC, GCR sem correção, ZTD e as duas colunas do Jz. Substitui os antigos 01/03/09/12 (em `scripts_antigos/`). | NMDB, GFZ, Kyoto, OMNIWeb, EMBRACE, Shinshu/GMDN, NGL (só se faltar cache) | `resultados/series_espaciais/*.png`, `anomalia_tec.csv` |
| `02_rosenfeld_goes16.py` | Motor GOES-16: download ABI (cache `dados_goes/`), recorte, curva r_e(T)/BTD dia-noite, mapa de topo. Usado pelo 04/05/07. | AWS S3 | figuras + funções |
| `04_diagnostico_sondagem_satelite.py` | POR DATA: sondagens (skew-T + índices) + Rosenfeld/BTD + timeline + TEC; relatório .md com tudo | Wyoming, S3, NMDB | `saida_<nome>/relatorio_*.md`, `curva_*.csv` |
| `05_serie_alvo.py` | SÉRIE no alvo: Tmin do topo/cobertura fria hora a hora + mapa IR municipal por cena (acha a "hora ótima") | S3 | `serie_*.csv/png`, `ir_*.png` |
| `06_compara_curvas.py` | Sobrepõe curvas r_e(T) de vários casos (usa os `curva_*.csv` do 04); separa regime dia/noite | — | `comparacao_curvas.png` |
| `07_colapso_topo.py` | DETECTOR DE COLAPSO (candidato a toró): topo esquentando >12 K/10 min; mapa de frequência + distância ao rio; recorte grande p/ anti-varredura | S3 | `colapsos_*.csv`, `freq_colapso_*.png`, `recortes_sudeste/*.npz` |
| `08_cicatrizes_sentinel2.py` | CICATRIZES: NDVI antes×depois no Sentinel-2, cor verdadeira, % por distância ao rio | AWS/EarthSearch | `saida_cicatrizes_*/…png/tif` |
| `10_vpi_era5.py` | VPI (vorticidade potencial isentrópica) ERA5: intrusão estratosférica, tropopausa dinâmica, dia a dia | CDS (chave) | `saida_VPI/vpi_*.png` |
| `11_verificacao_sismica.py` | VERIFICAÇÃO SÍSMICA: confronta relatos de estrondo/tremor com o catálogo RSBR/USP (FDSN); aplica as 3 ressalvas (mag preliminar≠revisada, incerteza 7–14 km/prof. fixada, exclusão de desmonte via SIGMINE/ANM). Evento não discriminado ≠ evidência. | moho.iag.usp.br, geo.anm.gov.br | `resultados/sismica/serie/eventos_sismicos.csv`, `relatorio_sismica.md` |
| `13_limpar_projeto.py` | LIMPEZA segura: lista (dry-run) e, com `--confirmar`, apaga temporários, duplicatas e gráficos supersedidos. Nunca toca em `dados_*`, controles ou docs. | — | (remoções) |

## Estrutura de pastas (desde jul/2026)

- **raiz** — só scripts (`00`–`13`, `rodar_tudo.py`), `README.md`, este guia e `anomalia_tec_evento.csv` (consumido pelo 09).
- **`docs/`** — README.docx, contextos, prompt LLM; `docs/propostas/` (MR/CPAM v1–v4); documentos técnicos.
- **`dados_*/`** — caches persistentes (GOES, TEC/IONEX, ERA5, geo, NMDB, geomagnético). NÃO apagar.
- **`resultados/solar_espacial_desde0104/`** — gráficos de atividade solar/espacial desde 01/04 (script 12).
- **`resultados/evento_desde2704/`** — saídas de satélite/diagnóstico do evento desde 27/04 (ex-`saida_*`: EOCE, toró, VPI, cicatrizes, cheia 12/mai).
- **`resultados/controles/`** — baselines de março/2024 (dias comuns sem FD e sem toró). Manter.
- **`resultados/sismica/`** — verificação sísmica (script 11), KML, relatos.

## Ordem lógica

1. **Contexto**: `01` (solar) + `09` (coluna geomagnética) + `10` (dinâmica).
2. **Achar o evento**: `05` (série → horas frias) → `07` (colapsos, onde/quando).
3. **Microfísica**: `04` nas datas/horas achadas → `06` (comparação entre casos).
4. **Ionosfera**: `03` (TEC) → alimenta `09`.
5. **Impacto no chão**: `08` (cicatrizes, antes ~22/04 × depois 03–09/05).

## Convenções

- Caches persistentes: `dados_goes/`, `dados_tec/`, `dados_era5/`, `dados_geo/`.
- O rio real: `dados_geo/rio_taquari_antas.geojson` (via `00_caso.carregar_rio`).
- Nada roda no chat da Anthropic (rede restrita) — rode na sua máquina.

## rodar_tudo.py

```bash
python rodar_tudo.py              # cadeia completa, janelas 27/04-03/05
python rodar_tudo.py --listar     # só mostra o que faria
python rodar_tudo.py --so 05 07   # roda só os passos escolhidos
python rodar_tudo.py --pular 08 10  # pula Sentinel-2 e ERA5
python rodar_tudo.py --completo   # 07 no período de chuva inteiro (pesado!)
```
