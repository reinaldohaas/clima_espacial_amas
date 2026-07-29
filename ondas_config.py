# -*- coding: utf-8 -*-
"""
ondas_config.py — Definição ÚNICA das ondas do evento RS 2024 e da caixa de análise.
   Editar SÓ AQUI: os scripts 11/12/13 leem daqui. Cada onda = (data_inicial, data_final) inclusive.

   Divisão orientada pelos dados (IVT + raios GLM + Jz), 24/abr–15/mai:
     O0 = surto de umidade de fins de abril (pré-condicionamento; raios de abril ainda pendentes)
     O1 = os toros (01–02/mai o pico); muito eletrificado, Jz alto
     O2 = 2º surto elétrico (maior total de raios; IVT máx em 08/mai); ainda não caracterizado
     O3 = a cheia; baixo Jz, poucos raios — regime estratiforme (COM Forbush decrease)
"""
ONDAS = {
    "O0_precond_27-30abr": ("2024-04-27", "2024-04-30"),
    "O1_toros_01-04mai":   ("2024-05-01", "2024-05-04"),
    "O2_surto_06-08mai":   ("2024-05-06", "2024-05-08"),
    "O3_cheia_10-13mai":   ("2024-05-10", "2024-05-13"),
}

# caixa RS + entorno alargado (o O2 saía pela borda sul): latmin,latmax,lonmin,lonmax
CAIXA = dict(latmin=-36.0, latmax=-25.0, lonmin=-60.0, lonmax=-47.0)

# cidades de referência p/ os mapas (lat, lon) — usadas quando não há cartopy
CIDADES = {"Porto Alegre":(-30.03,-51.23),"Florianópolis":(-27.60,-48.55),
           "Curitiba":(-25.43,-49.27),"Montevidéu":(-34.90,-56.16),
           "Buenos Aires":(-34.61,-58.38),"Uruguaiana":(-29.75,-57.09)}

def carrega():
    """Atalho para os scripts: retorna (ONDAS, CAIXA)."""
    return ONDAS, CAIXA
