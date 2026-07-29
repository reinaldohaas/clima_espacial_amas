# Toró × Gannon storm — análise em Python (para rodar no Cowork)

Dois scripts, duas perguntas diferentes. **Nenhum roda no chat da Anthropic**
(a rede lá só alcança PyPI/GitHub, não NOAA/Copernicus/Oulu). Rode na sua
máquina, dentro do repo, via Cowork ou terminal.

---

## `01_timeline_may2024.py` — a espinha temporal (COMECE POR AQUI)

**Pergunta:** onde caem os eventos de toró em relação aos marcos solares e ao
Forbush de maio/2024?

**O que faz:** baixa a contagem de raios cósmicos de Oulu/NMDB, marca os
eventos solares (datas verificadas), sobrepõe as SUAS datas de toró, e
calcula a "fase" de cada uma (antes do CME / durante o FD / depois).

**Você preenche:** a lista `EVENTOS_TORO` (datas, de preferência UT + lat/lon).

**Já sabemos (teste com as duas datas do RS):**
- Início das chuvas **28/abr** → **12,7 dias ANTES** do CME chegar. Solar NÃO
  é o gatilho do início.
- Cheia máxima **12/mai** → **1,5 dia DEPOIS** do CME chegar (SSC 10/mai 17:05).
  Essa janela é consistente com a hipótese — vale investigar a fundo.

**Dependências:** `pip install requests pandas matplotlib numpy`
Se o NMDB recusar (403/URL mudou), use a interface https://www.nmdb.eu/nest/
(estação OULU) e exporte o CSV manualmente, depois aponte o script pra ele.

---

## `02_rosenfeld_goes16.py` — microfísica da nuvem (SLW via Rosenfeld)

**Pergunta:** a nuvem do evento mostra a assinatura que o toró prevê — água
super-resfriada (SLW) persistente abaixo de −20 °C e glaciação abrupta?

**O que faz:** baixa GOES-16 ABI (bandas 3,9 / 10,3 / 0,64 µm), recorta o alvo,
monta a curva `r_e(T)` de Rosenfeld e diagnostica SLW/glaciação.

**Você preenche:** `ALVO` (lat/lon/raio) e `JANELA` (data/hora UT).

**Dependências:** `pip install goes2go xarray numpy matplotlib pyproj netcdf4`

### ⚠️ Limitação honesta que você PRECISA corrigir antes de publicar
O cálculo de `r_e` no esqueleto é um **proxy** (diferença 3,9−10,3 µm), não um
retrieval calibrado. Para resultado publicável, troque por um retrieval real
de `r_e` (ex.: `satpy` com o modificador de raio efetivo, ou o método
CAPPI/Rosenfeld com C05/1,6 µm ou C06/2,2 µm e correção da parte térmica da
3,9 µm). O esqueleto prova a lógica; o número final exige o retrieval certo.

---

## Disciplina metodológica (o que decide se isso é ciência)

1. **Caso-estudo ≠ prova.** Um evento (12/mai) que mostre SLW + timing com o CME
   ILUSTRA a hipótese. Não a comprova. N=1.

2. **Você precisa de CONTROLES.** Rode o Rosenfeld também em:
   - um dia calmo (sem evento solar) com chuva comum no RS;
   - um evento extremo SEM Forbush associado.
   Se a assinatura SLW/glaciação-abrupta só aparecer nos dias com FD, é sinal.
   Se aparecer em todos, não é.

3. **A prova real é estatística** (próximo script, a fazer): cruzar o catálogo
   de Forbush decreases (Oulu/IZMIRAN) com o catálogo de eventos extremos do
   sul do Brasil e testar concentração vs. acaso — baseline de **3,6%**
   (Love et al., fração de rotações com fluxo alto que geram evento extremo).

4. **Cuidado com o viés de confirmação.** Olhar só o dia da Gannon storm e
   "achar" um toró não vale. A linha do tempo (script 01) existe justamente
   para deixar os dados mostrarem o alinhamento — ou a falta dele.

---

## Ordem sugerida de trabalho no Cowork
1. Rodar `01` com suas datas de toró → ver a fase de cada uma.
2. Rodar `02` no evento de 12/mai → ver se há SLW/glaciação abrupta.
3. Rodar `02` nos CONTROLES (dia calmo, evento sem FD).
4. Se o padrão se sustentar, montar o teste estatístico (catálogos completos).

---

## `03_gnss_tec.py` — cadeia GNSS: ionosfera (TEC) + troposfera (PWV)

**Pergunta:** durante o evento, houve anomalia de ionização (TEC) sobre a AMAS
E anomalia de vapor (PWV) — e elas se destacam de dias-controle sem toró?

**O que faz:** baixa TEC do EMBRACE/INPE (mapas 10-min desde 2013), extrai a
média na caixa AMAS/RS, calcula a anomalia (removendo o ciclo diurno), e
**compara evento vs. controles**. Opcionalmente sobrepõe o PWV da RBMC.

**Mede as duas pontas da cadeia da sua hipótese:**
- TEC = ionização da coluna (lado solar/ionosférico — a "termalização").
- PWV = vapor d'água integrado (lado troposférico).
O MEIO (Jz → microfísica) continua sendo inferência (o elo contestado do Tinsley).

**Base observacional que sustenta a "termalização" (citar no artigo):**
Abdu et al. (2005), *J. Atmos. Solar-Terr. Phys.* 67:1643-1657 — ionização por
precipitação de partículas sobre a AMAS eleva a condutividade ionosférica,
operando até em condições calmas e intensificando em tempestades. Ou seja: o
seu elo "elétrons extra → mais ionização sobre a AMAS" é OBSERVADO, não conjectura.

### ⚠️ A armadilha específica do TEC (crítica)
A AMAS tem TEC anômalo **quase sempre** — é a natureza dela. Achar "TEC anômalo
no dia do toró" é quase garantido por acaso. Por isso o script SÓ conclui algo
comparando **evento vs. controle**. Se a anomalia do evento não se destacar
claramente dos dias-controle, **o TEC não discrimina o toró** — e isso é um
resultado honesto, não uma falha.

**Dados:** EMBRACE http://www2.inpe.br/climaespacial/portal/en/ (TEC/ROTI/S4);
RBMC/IBGE (RINEX → PWV via GAMIT/GipsyX, ou ZTD do IGS).

---

## Referências novas para o artigo (verificadas)
- Abdu, M.A. et al. (2005). Ionization/conductivity enhancement over the SAMA
  by particle precipitation. *JATP* 67, 1643-1657. [base da "termalização"]
- De Paula, E.R. et al. (2023). GNSS ionospheric monitoring networks in Brazil.
  *J. Aerosp. Technol. Manag.* 15, e0123. [descrição das redes RBMC/EMBRACE]
- International GLE Database — gle.oulu.fi [catálogo de GLEs]
- NMDB (www.nmdb.eu/nest) — neutron monitors [séries de raios cósmicos/Forbush]
