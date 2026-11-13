
from pathlib import Path
import re
import pandas as pd

# Caminhos
BASE = Path(__file__).resolve().parents[1]

ARQUIVO_EXCEL = (
    Path.home()
    / "Downloads"
    / "Cópia de MAPBIOMAS_BRAZIL-COL.11-BIOME_STATE_MUNICIPALITY.xlsx"
)

ARQUIVO_MUNICIPIOS = BASE / "config" / "municipios.csv"
ARQUIVO_SAIDA = BASE / "data" / "processed" / "uso_solo.csv"

print("Lendo lista de municípios...")

municipios = pd.read_csv(
    ARQUIVO_MUNICIPIOS,
    dtype={"codigo_ibge": str}
)

municipios["codigo_ibge"] = (
    municipios["codigo_ibge"]
    .str.strip()
    .str.zfill(7)
)

nomes_municipios = dict(
    zip(municipios["codigo_ibge"], municipios["nome"])
)

print("Lendo dados do MapBiomas...")

dados = pd.read_excel(
    ARQUIVO_EXCEL,
    sheet_name="COVERAGE_11",
    usecols="F:I,O:BC"
)

def normalizar_codigo(valor):
    if pd.isna(valor):
        return ""
    return str(int(float(valor))).zfill(7)

dados["geocode"] = dados["geocode"].apply(
    normalizar_codigo
)

# Selecionar somente os 21 municípios
dados = dados[
    dados["geocode"].isin(nomes_municipios)
].copy()

encontrados = dados["geocode"].nunique()

print("Municípios encontrados:", encontrados)

if encontrados != len(municipios):
    faltantes = set(nomes_municipios) - set(dados["geocode"])
    raise ValueError(
        f"Municípios não encontrados: {faltantes}"
    )

# Ler legenda oficial em português
print("Lendo legenda oficial...")

legenda = pd.read_excel(
    ARQUIVO_EXCEL,
    sheet_name="LEGEND_CODE",
    header=2,
    usecols="B:E"
)

legenda = legenda.dropna(
    subset=["COLEÇÃO 11 - CLASSES", "ID"]
).copy()

legenda["ID"] = pd.to_numeric(
    legenda["ID"],
    errors="coerce"
)

legenda = legenda.dropna(subset=["ID"])
legenda["ID"] = legenda["ID"].astype(int)

# Identificar classes que possuem subclasses.
# Elas são categorias agregadoras e não devem
# ser somadas junto com suas classes detalhadas.
legenda["codigo_classe"] = (
    legenda["COLEÇÃO 11 - CLASSES"]
    .astype(str)
    .str.extract(r"^(\d+(?:\.\d+)*)", expand=False)
)

codigos = legenda["codigo_classe"].dropna().tolist()

codigos_pais = {
    codigo
    for codigo in codigos
    if any(
        outro.startswith(codigo + ".")
        for outro in codigos
    )
}

ids_agregadores = set(
    legenda.loc[
        legenda["codigo_classe"].isin(codigos_pais),
        "ID"
    ]
)

dados["class"] = pd.to_numeric(
    dados["class"],
    errors="coerce"
).astype("Int64")

# Retirar categorias agregadoras
dados = dados[
    ~dados["class"].isin(ids_agregadores)
].copy()

# Relacionar código da classe ao nome em português
nomes_classes = dict(
    zip(legenda["ID"], legenda["COLEÇÃO 11 - CLASSES"])
)

dados["classe"] = dados["class"].map(nomes_classes)

if dados["classe"].isna().any():
    desconhecidas = dados.loc[
        dados["classe"].isna(), "class"
    ].unique()
    raise ValueError(
        f"Códigos sem correspondência na legenda: {desconhecidas}"
    )

# Conferir duplicidades


# Converter anos de 1985 a 2025 para formato longo
anos = [
    f"y{ano}"
    for ano in range(1985, 2026)
]

print("Organizando série histórica...")

historico = dados.melt(
    id_vars=["geocode", "class", "classe"],
    value_vars=anos,
    var_name="ano",
    value_name="area_ha"
)

historico["ano"] = (
    historico["ano"]
    .str.replace("y", "", regex=False)
    .astype(int)
)

historico["codigo_ibge"] = historico["geocode"]

historico["municipio"] = (
    historico["codigo_ibge"]
    .map(nomes_municipios)
)

historico["area_ha"] = pd.to_numeric(
    historico["area_ha"],
    errors="coerce"
)
# Somar áreas quando o município aparece
# em mais de um bioma, como General Câmara.
historico = (
    historico
    .groupby(
        [
            "ano",
            "geocode",
            "codigo_ibge",
            "municipio",
            "class",
            "classe"
        ],
        as_index=False
    )["area_ha"]
    .sum()
)

historico = historico[
    [
        "ano",
        "codigo_ibge",
        "municipio",
        "classe",
        "area_ha"
    ]
].copy()

historico = historico.dropna(subset=["area_ha"])

historico = historico.sort_values(
    ["ano", "municipio", "classe"]
)

# Salvar CSV
ARQUIVO_SAIDA.parent.mkdir(
    parents=True,
    exist_ok=True
)

historico.to_csv(
    ARQUIVO_SAIDA,
    index=False,
    encoding="utf-8-sig"
)

# Relatório de validação
print("\nIMPORTAÇÃO CONCLUÍDA!")
print("Arquivo:", ARQUIVO_SAIDA)
print("Total de registros:", len(historico))
print("Municípios:", historico["codigo_ibge"].nunique())
print("Classes:", historico["classe"].nunique())
print(
    "Período:",
    historico["ano"].min(),
    "a",
    historico["ano"].max()
)

print("\nÁREA TOTAL POR MUNICÍPIO EM 2025:")

resumo = (
    historico[historico["ano"] == 2025]
    .groupby("municipio")["area_ha"]
    .sum()
    .sort_values(ascending=False)
)

print(resumo.round(2).to_string())

print("\nPRIMEIROS REGISTROS:")
print(historico.head(10).to_string(index=False))
