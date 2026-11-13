
import pandas as pd
from pathlib import Path
import os
import sys

MUNICIPIOS = {
    "4300851": "ARAMBARÉ",
    "4301107": "ARROIO DOS RATOS",
    "4301750": "BARÃO DO TRIUNFO",
    "4301909": "BARRA DO RIBEIRO",
    "4302709": "BUTIÁ",
    "4303509": "CAMAQUÃ",
    "4305173": "CERRO GRANDE DO SUL",
    "4305355": "CHARQUEADAS",
    "4305447": "CHUVISCA",
    "4306056": "CRISTAL",
    "4306502": "DOM FELICIANO",
    "4306767": "ELDORADO DO SUL",
    "4306908": "ENCRUZILHADA DO SUL",
    "4309308": "GUAÍBA",
    "4308805": "GENERAL CÂMARA",
    "4311981": "MARIANA PIMENTEL",
    "4312252": "MINAS DO LEÃO",
    "4320354": "SENTINELA DO SUL",
    "4320552": "SERTÃO SANTANA",
    "4318408": "SÃO JERÔNIMO",
    "4321105": "TAPES"
}

arquivo = os.path.join(
    os.environ["USERPROFILE"],
    "Downloads",
    "MATRIZ_CR_REGIAO_2026.gz"
)

saida = Path("outputs_sicor")
saida.mkdir(exist_ok=True)

print("Lendo SICOR...")
df = pd.read_csv(
    arquivo,
    sep=";",
    decimal=",",
    encoding="utf-8-sig",
    compression="gzip",
    dtype={"COD_MUNICIPIO_IBGE": "string"},
    low_memory=False
)

df["COD_MUNICIPIO_IBGE"] = (
    df["COD_MUNICIPIO_IBGE"].str.strip().str.zfill(7)
)

regional = df[
    df["COD_MUNICIPIO_IBGE"].isin(MUNICIPIOS)
].copy()

regional["MUNICIPIO"] = (
    regional["COD_MUNICIPIO_IBGE"].map(MUNICIPIOS)
)

colunas = [
    "CUSTEIO_AREA", "CUSTEIO_QTDE", "CUSTEIO_VALOR",
    "INVESTIMENTO_AREA", "INVESTIMENTO_QTDE",
    "INVESTIMENTO_VALOR", "COMERCIALIZACAO_QTDE",
    "COMERCIALIZACAO_VALOR", "INDUSTRIALIZACAO_QTDE",
    "INDUSTRIALIZACAO_VALOR", "TOTAL_AREA",
    "TOTAL_QTDE", "TOTAL_VALOR"
]

colunas = [c for c in colunas if c in regional.columns]

for c in colunas:
    regional[c] = pd.to_numeric(
        regional[c], errors="coerce"
    ).fillna(0)

regional.to_csv(
    saida / "sicor_centro_sul_21_municipios.csv",
    sep=";", decimal=",", index=False, encoding="utf-8-sig"
)

def exportar_grupo(dimensoes, nome):
    resultado = (
        regional.groupby(dimensoes, dropna=False)[colunas]
        .sum()
        .reset_index()
    )
    resultado.to_csv(
        saida / nome,
        sep=";", decimal=",", index=False, encoding="utf-8-sig"
    )

exportar_grupo(
    ["COD_MUNICIPIO_IBGE", "MUNICIPIO"],
    "resumo_por_municipio.csv"
)

exportar_grupo(
    ["MUNICIPIO", "PROGRAMA"],
    "resumo_municipio_programa.csv"
)

exportar_grupo(
    ["MUNICIPIO", "ATIVIDADE"],
    "resumo_municipio_atividade.csv"
)

exportar_grupo(
    ["MUNICIPIO", "FONTE_RECURSO"],
    "resumo_municipio_fonte_recurso.csv"
)

exportar_grupo(
    ["ANO_MES_EMISSAO", "MUNICIPIO"],
    "serie_mensal_municipio.csv"
)

encontrados = set(regional["COD_MUNICIPIO_IBGE"].unique())
ausentes = set(MUNICIPIOS) - encontrados

print("\n========== RESULTADO ==========")
print("Registros regionais:", len(regional))
print("Municípios encontrados:", len(encontrados))
print("Municípios sem registros:", len(ausentes))

for codigo in sorted(ausentes):
    print(MUNICIPIOS[codigo])

print("\nArquivos salvos em:", saida.resolve())
