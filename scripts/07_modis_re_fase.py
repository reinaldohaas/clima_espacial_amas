#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
07 — MODIS L3 diário (MOD08_D3/MYD08_D3): raio efetivo de gotícula + fase/topo da nuvem.
   Duas medidas centrais:
     (a) raio efetivo de gotícula LÍQUIDA — teste direto das "gotas pequenas" (Twomey/anti-varredura);
     (b) fração de fase GELO + temperatura do topo — separador do REGIME graupel/fase mista vs nuvem quente,
         que a Seção 2.4 mostrou ser o que define R (nuvem passiva vs eletricamente ativa).

Pré-req:
   pip install earthaccess numpy pandas
   conda install -c conda-forge pyhdf        # HDF4 do MODIS L3 (no miniforge)
   # conta Earthdata (mesma do 02b/06); no 1o uso earthaccess grava ~/.netrc

Uso:
   python 07_modis_re_fase.py --ini 2024-09-01 --fim 2024-09-30 --caixa fogo --sat aqua
   python 07_modis_re_fase.py --ini 2024-05-01 --fim 2024-05-15 --caixa rs   --sat aqua
Saída: resultados/modis_re_fase_<caixa>_<sat>_<ini>_<fim>.csv
   colunas: re_liq_um, re_ice_um, ctt_K, frac_gelo  (média diária na caixa)
"""
import argparse, os, glob, numpy as np, pandas as pd
try:
    import earthaccess
except ImportError:
    raise SystemExit("pip install earthaccess")
try:
    from pyhdf.SD import SD, SDC
except ImportError:
    raise SystemExit("conda install -c conda-forge pyhdf  (HDF4 do MODIS)")

CAIXAS={"brasil":(-34,6,-74,-34),"fogo":(-20,2,-70,-50),
        "rio_invisivel":(-22,-8,-63,-50),"sudeste":(-25,-14,-55,-43),"rs":(-34,-27,-58,-49)}
SHORT={"aqua":"MYD08_D3","terra":"MOD08_D3"}
# substrings dos SDS que queremos (o nome exato varia com a coleção)
ALVO={"re_liq_um":["Cloud_Effective_Radius_Liquid_Mean"],
      "re_ice_um":["Cloud_Effective_Radius_Ice_Mean"],
      "ctt_K":["Cloud_Top_Temperature_Mean","Cloud_Top_Temperature_Day_Mean"],
      "frac_gelo":["Cloud_Retrieval_Fraction_Ice","Ice_Cloud_Fraction","Cloud_Phase_Optical_Properties_Fraction_Ice"]}

LATS=90-0.5-np.arange(180); LONS=-179.5+np.arange(360)     # grade 1° do MOD08_D3

def le_sds(hdf, nomes):
    disp={s:s for s in hdf.datasets()}
    for cand in nomes:
        if cand in disp:
            sds=hdf.select(cand); a=sds.attributes()
            d=sds[:].astype(float)
            fv=a.get("_FillValue");
            if fv is not None: d[d==fv]=np.nan
            sf=a.get("scale_factor",1.0); off=a.get("add_offset",0.0)
            return sf*(d-off), cand           # convenção MODIS L3: valor = scale*(bruto - offset)
    return None,None

def caixa_media(d, box):
    la0,la1,lo0,lo1=box
    mlat=(LATS>=la0)&(LATS<=la1); mlon=(LONS>=lo0)&(LONS<=lo1)
    sub=d[np.ix_(mlat,mlon)]
    return np.nanmean(sub) if np.isfinite(sub).any() else np.nan

def data_do_nome(base):
    # MOD08_D3.A2024245.061.*.hdf -> ano 2024, dia juliano 245
    tok=[t for t in base.split(".") if t.startswith("A") and t[1:].isdigit()]
    if not tok: return pd.NaT
    yj=tok[0][1:]; return pd.to_datetime(yj[:4]+"-"+yj[4:],format="%Y-%j")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ini",required=True); ap.add_argument("--fim",required=True)
    ap.add_argument("--caixa",choices=list(CAIXAS),default="fogo")
    ap.add_argument("--sat",choices=list(SHORT),default="aqua"); ap.add_argument("--outdir",default="resultados")
    a=ap.parse_args(); os.makedirs(a.outdir,exist_ok=True); box=CAIXAS[a.caixa]
    earthaccess.login(persist=True)
    res=earthaccess.search_data(short_name=SHORT[a.sat],temporal=(a.ini,a.fim))
    if not res: raise SystemExit(f"Nenhum grânulo {SHORT[a.sat]} — verifique acesso/datas.")
    print(f"{len(res)} arquivos diários; baixando...")
    files=earthaccess.download(res,f"{a.outdir}/_modis_tmp")
    usados={}; linhas=[]
    for f in files:
        f=str(f)
        if not f.endswith(".hdf"): continue
        try: hdf=SD(f,SDC.READ)
        except Exception as e: print("  abrir falhou",os.path.basename(f),str(e)[:60]); continue
        row={"data":data_do_nome(os.path.basename(f))}
        for k,nomes in ALVO.items():
            d,usou=le_sds(hdf,nomes)
            if d is not None: row[k]=caixa_media(d,box); usados[k]=usou
        hdf.end(); linhas.append(row)
    df=pd.DataFrame(linhas).dropna(subset=["data"]).set_index("data").sort_index()
    out=f"{a.outdir}/modis_re_fase_{a.caixa}_{a.sat}_{a.ini}_{a.fim}.csv"; df.to_csv(out)
    print("SDS usados:",usados)
    print(f"-> {out} ({len(df)} dias)")
    # análise rápida se houver AOD (fogo) e Jz
    try:
        aod=pd.read_csv(f"{a.outdir}/cams_aod_diario_{a.caixa}_seca.csv",parse_dates=["data"]).set_index("data").aod550_fumaca
        jz=pd.read_csv("dados/jz/rede_completa_14_estacoes_currents_2024.csv",parse_dates=["datetime"]).set_index("datetime").sort_index()
        jz=jz.loc[~((jz.index.hour==0)&(jz.index.minute==0))].resample("1D").agg(Jz=("Jz_pA_m2",lambda s:np.sqrt((s**2).mean()))).Jz
        M=pd.concat([df.re_liq_um.rename("re"),aod.rename("AOD"),jz],axis=1).dropna()
        if len(M)>8:
            print("\n[teste rápido] corr(re_liq, AOD)=%.2f (Twomey: esperado NEGATIVO)"%M.re.corr(M.AOD))
            print("             corr(re_liq, Jz)=%.2f"%M.re.corr(M.Jz))
        if "frac_gelo" in df:
            print("             fração de dias 'fase mista' (frac_gelo>0.5): %.0f%%"%(100*(df.frac_gelo>0.5).mean()))
    except Exception as e:
        print("(análise rápida pulada:",str(e)[:80],")")

if __name__=="__main__":
    main()
