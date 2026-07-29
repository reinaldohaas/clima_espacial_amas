# Prompt para nova sessão — projeto Eventos_toro

> Cole o texto abaixo na primeira mensagem de uma nova sessão do Claude
> (Cowork), com a pasta `Eventos_toro` conectada.

---

Estou continuando o projeto **Eventos_toro** (pasta conectada). Leia primeiro
`GUIA_SCRIPTS.md` e `docs/documento_tecnico_evento.docx` antes de mexer em
qualquer coisa.

## REGRAS INEGOCIÁVEIS DESTA SESSÃO

1. **TUDO roda na MINHA máquina.** Você edita e cria código; EU executo os
   scripts e colo a saída aqui. Não tente rodar downloads pesados nem
   consultas de dados no seu ambiente — sua rede é restrita e o resultado não
   fica comigo. Só use seu ambiente para: checar sintaxe (`py_compile`),
   testes com dados sintéticos e leitura de arquivos que já estão na pasta.
2. **Código e dados são LOCAIS e PERMANECEM locais.** Todo script novo vai
   para a raiz do projeto; todo dado vai para os caches (`dados_*`); toda
   figura/resultado vai para `resultados/<módulo>/`. Nada em pastas
   temporárias suas.
3. **CACHE PRIMEIRO, sempre.** Nenhuma função baixa o que já existe em
   `dados_*`. Quem baixar algo novo, grava no cache na hora. NUNCA apague ou
   rebaixe um cache.
4. **NUNCA sobrescreva resultado bom com resultado vazio/falho.** Padrão do
   projeto: se uma consulta voltar vazia e a saída anterior tiver conteúdo,
   manter a anterior e avisar (veja o `--sobrescrever` do script 11).
5. **Exclusões só via `13_limpar_projeto.py`** (dry-run por padrão), e só eu
   executo com `--confirmar`.
6. **Honestidade estatística** (regra do README): todo diagnóstico compara
   evento × controle; relato sem contraparte instrumental não é evidência;
   extrapolações são declaradas como tais.

## ESTADO ATUAL (jul/2026)

- Pipeline: `00_caso.py` (config central) · `01_series_espaciais.py` (TODAS as
  séries espaciais: GCR/NMDB, múons São Martinho/GMDN, Kp, Dst, AE, Ey,
  prótons GOES/NCEI, TEC/IONEX, ZTD GNSS/NGL — substitui os antigos
  01/03/09/12, hoje em `scripts_antigos/`) · `02` GOES · `04` sondagens
  multi-estação (SBSM/SBPA/SBFI, parâmetros de gelo, skew-T completo) ·
  `05-08` evento · `10` VPI · `11` verificação sísmica · `13` limpeza.
- Caches vivos: `dados_goes`, `dados_tec`, `dados_era5`, `dados_nmdb`,
  `dados_geomag`, `dados_muons`, `dados_goesp`, `dados_gnss`,
  `dados_sondagens`, `dados_geo`.
- Resultados-chave já estabelecidos: toró de 02 UT 03/05/2024 ocorreu com a
  coluna eletrodinâmica CALMA; única perturbação de coluna inteira =
  Gannon 10–13/05 (Kp 9, Dst −406, FD local múons SMS = 5,3%); 4 sismos
  mR 2,2–2,4 em 13/05 (madrugada), interpretação hidrológica, formalmente
  NÃO DISCRIMINADOS de desmonte (falta registro de fogo).
- Bugs conhecidos já corrigidos (não reintroduzir): FDSN da USP retorna vazio
  se `endtime` tiver hora ≠ 00:00:00; NumPy 2 não tem `np.trapz`; sondagens
  Wyoming vêm com pressões duplicadas.

## PENDÊNCIAS (escolho eu a ordem)

- Boletim sísmico revisado da USP + registro de fogo das pedreiras.
- Formas de onda contínuas RSBR nas horas dos relatos de som (sub-limiar).
- VLF/SAVNET (região D); IONEX de abril completo; ZTD NGL da POAL (validar).
- Comparação microfísica 01–03/05 × 12/05 (scripts 04/06) — o teste decisivo.

Comece me perguntando o que quero atacar hoje. Não refaça nada que já existe.
