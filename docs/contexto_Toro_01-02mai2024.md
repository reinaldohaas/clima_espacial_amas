# Caso corrigido: o toró foi 01–02/MAIO/2024 (não março)

## O que aconteceu com as datas

As rodadas de 01–02/mar/2024 não mostraram tempestade sobre o alvo — porque
não havia: as chuvas extremas do RS foram de 27/abr a mai/2024. As datas
corretas do toró do catálogo são **01–02/mai/2024**, centro **−29,5/−51,2**
(encosta da Serra, ao sul de Caxias), pico **17–21h local (20–00 UT) de 02/mai**.
Bate com o INMET: Santa Maria 213,6 mm em 01/mai (recorde de 112 anos),
Caxias do Sul 266,2 mm em 02/mai.

## Nova moldura para a hipótese (melhor que a anterior)

- **Toró 01–02/mai** = ~8,5 dias ANTES do CME chegar (SSC 10/mai 17:05)
  → evento extremo **SEM FD concomitante**.
- **Chuva de 12/mai** = 1,5 dia DEPOIS do SSC → o par **COM FD**.
- Mesma região, mesma quinzena, mesma estação do ano, mesmo regime sinótico:
  é a comparação com menos confundidores que se pode ter com N=2.
- Consequência lógica: se as assinaturas microfísicas (Rosenfeld/BTD) forem
  iguais nos dois, o FD não é necessário para o toró. Se o 12/mai mostrar
  algo qualitativamente distinto, a janela pós-SSC merece o aprofundamento.

## O que os dados de março viram a ser

Os diagnósticos já rodados de 01–02/mar (sondagens SBSM/POA, curvas BTD,
mapas) não são lixo: são um **controle de dias comuns sem FD e sem toró** —
guarde a pasta `saida_SBSM_mar2024` e `saida_Toro_02mar` como baseline.

## Comandos do caso correto

```bash
# 1) achar a hora exata da tempestade sobre o alvo (série + mapas municipais)
python 05_serie_alvo.py            # defaults já apontam 27/abr-04/mai

# 2) diagnóstico completo nas datas certas (defaults já atualizados)
python 04_diagnostico_sondagem_satelite.py

# 3) madrugada de 03/mai, se o pico varar a meia-noite UT
python 04_diagnostico_sondagem_satelite.py --datas 2024-05-03 --nome Toro_03mai_madrug --goes-horas 00:00 01:00 02:00
```
