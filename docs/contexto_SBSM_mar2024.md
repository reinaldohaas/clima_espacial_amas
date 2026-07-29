# Caso 01–02/mar/2024 — Santa Maria (SBSM/83937): contexto verificado

## Por que este caso importa para a hipótese

01–02/mar/2024 é **evento de toró do catálogo** — mas não há evento solar
relevante nessas datas. O grande evento de março foi **23–24/mar**: flare
X1.1 (AR3614, 23/mar 01:33 UT) + halo-CME ~1470 km/s → tempestade **G4** e
Forbush decrease em 24/mar (análises preliminares da rede SEVAN e estudos do
ciclo 25 no arXiv). Ou seja: é um **toró SEM FD** (~22 dias antes do FD do
mês) — exatamente o "evento extremo SEM Forbush associado" que o item 2 da
disciplina metodológica do README exige. A comparação com o 12/mai (toró COM
FD) é o teste: assinaturas microfísicas iguais = a microfísica não discrimina
o gatilho solar; diferentes = vale aprofundar.

Também não confundir com a catástrofe do RS: as chuvas extremas foram
**27/abr–mai/2024** (Santa Maria registrou 213,6 mm em 01/mai, recorde de
112 anos — INMET). Março/2024 não aparece nos levantamentos como evento maior.

## Leitura esperada

- Assinatura Rosenfeld/índices de 01–02/mar IGUAL à do 12/mai (toró com FD)
  → a microfísica não discrimina o gatilho solar (evidência contra).
- Assinatura claramente diferente → vale aprofundar a hipótese.
- Adicione as datas ao `EVENTOS_TORO` do script 01 (com hora UT do pico de
  chuva, dos pluviômetros INMET de Santa Maria) para a fase ficar registrada.

## Como rodar o diagnóstico

```bash
pip install siphon metpy pandas numpy matplotlib goes2go xarray pyproj netcdf4
python 04_diagnostico_sondagem_satelite.py            # sondagens + Rosenfeld
python 04_diagnostico_sondagem_satelite.py --sem-goes # só sondagens (rápido)
```

Saída: `saida_SBSM_mar2024/` com skew-Ts, curvas r_e(T) e
`relatorio_SBSM_mar2024.md` preenchido com os índices.

Atenção: sondagens de SBSM às vezes só existem em 12Z (00Z falha com
frequência); o script apenas registra a falha e segue.

## Fontes do contexto

- FD/G4 de 24/mar/2024: arxiv.org/pdf/2506.17917 (SEVAN, "largest FD in 20
  years" — análise preliminar) e arxiv.org/pdf/2601.19289 (atividade do ciclo 25).
- Chuvas RS abril–maio/2024 e recorde de Santa Maria: portal.inmet.gov.br
  (nota "Inundação histórica no Rio Grande do Sul completa um ano").
