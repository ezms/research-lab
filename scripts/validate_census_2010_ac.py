"""Valida o pipeline ponta a ponta do Census2010DataSource para AC."""

from pathlib import Path

import pandas as pd

from lab.enums.uf import UF
from lab.research.housing_reality.sources.census_2010 import Census2010DataSource

WORK_DIR = Path("data/census_2010")

# --- pipeline ---

source = Census2010DataSource(uf=UF.AC, work_dir=WORK_DIR)

print("=== identify ===")
identity = source.identify()
print(f"  {identity.name} {identity.version} — {identity.provider}")
print(f"  {identity.description}")

print("\n=== download ===")
zip_path = source.download()
print(f"  {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")

print("\n=== parse ===")
parsed = source.parse(zip_path)
for name, path in parsed.items():
    print(f"  {name}: {path}")

print("\n=== map_variables ===")
mapped = source.map_variables(parsed)
for name, path in mapped.items():
    print(f"  {name}: {path}")

# --- validação dos parquets ---

print("\n=== validação: parquets parsed ===")
for name, path in parsed.items():
    df = pd.read_parquet(path)
    has_encoding_issue = any(
        df[c].astype(str).str.contains(r"[^\x00-\x7F]", regex=True, na=False).any()
        for c in df.select_dtypes("object").columns
    )
    print(f"\n  [{name}]")
    print(f"    linhas    : {len(df):,}")
    print(f"    colunas   : {len(df.columns)}")
    print(f"    dtypes    : {dict(df.dtypes.value_counts())}")
    print(f"    nulos (%) : {(df.isna().mean() * 100).describe()[['mean','max']].to_dict()}")
    print(f"    encoding  : {'⚠ caracteres não-ASCII' if has_encoding_issue else 'ok'}")

print("\n=== validação: parquets mapped ===")
for name, path in mapped.items():
    df = pd.read_parquet(path)
    print(f"\n  [{name}]")
    print(f"    linhas  : {len(df):,}")
    print(f"    colunas : {list(df.columns)[:8]} ...")

# --- sanity check: domicílios AC ---

print("\n=== sanity check: domicílios AC ===")
domi = pd.read_parquet(parsed["domicilios"])

# V0010 = peso amostral (float com 13 decimais)
# Soma dos pesos ≈ total de domicílios no universo
total_universo = domi["V0010"].sum()
linhas_amostra = len(domi)

# IBGE 2010: AC tinha 199.287 domicílios particulares permanentes ocupados
# (Tabela 3217, SIDRA — domicílios particulares permanentes)
referencia_ibge = 199_287

print(f"  linhas na amostra       : {linhas_amostra:,}")
print(f"  soma dos pesos (V0010)  : {total_universo:,.0f}")
print(f"  referência IBGE (SIDRA) : {referencia_ibge:,}")
desvio = abs(total_universo - referencia_ibge) / referencia_ibge * 100
print(f"  desvio                  : {desvio:.1f}%")
print(f"  {'✓ dentro do esperado' if desvio < 5 else '⚠ desvio acima de 5%'}")
