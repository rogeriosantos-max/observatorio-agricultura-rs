
from pathlib import Path
import csv
import requests

ROOT = Path(__file__).resolve().parents[1]

ARQUIVO_MUNICIPIOS = ROOT / "config" / "municipios.csv"
ARQUIVO_SAIDA = (
    ROOT / "data" / "processed" / "agricultura_familiar.csv"
)

URL_BASE = "https://apisidra.ibge.gov.br/values"

registros = []

# Lê os 21 municípios da região
with open(
    ARQUIVO_MUNICIPIOS,
    "r",
    encoding="utf-8-sig",
    newline=""
) as arquivo:

    linhas_validas = (
        linha for linha in arquivo
        if linha.strip()
    )

    municipios = list(
        csv.DictReader(linhas_validas)
    )

print(f"Municípios encontrados: {len(municipios)}")

# Consulta individualmente cada município
for municipio in municipios:

    codigo = municipio["codigo_ibge"].strip()
    nome = municipio["nome"].strip()

    url = (
        f"{URL_BASE}/t/6778/n6/{codigo}"
        "/v/183/p/2017/c829/46304"
    )

    resposta = requests.get(url, timeout=60)
    resposta.raise_for_status()

    dados = resposta.json()

    if len(dados) < 2:
        raise ValueError(
            f"Sem dados para {nome} ({codigo})"
        )

    valor = dados[1]["V"]

    if not valor.isdigit():
        raise ValueError(
            f"Valor inválido para {nome}: {valor}"
        )

    registros.append({
        "ano": 2017,
        "codigo_ibge": codigo,
        "municipio": nome,
        "estabelecimentos": int(valor),
        "agricultores": "",
        "area_ha": "",
        "observacao": (
            "Censo Agropecuario 2017 - IBGE/SIDRA "
            "- Tabela 6778 - Agricultura familiar"
        )
    })

    print(f"{nome}: {int(valor):,} estabelecimentos")

# Salva o resultado
campos = [
    "ano",
    "codigo_ibge",
    "municipio",
    "estabelecimentos",
    "agricultores",
    "area_ha",
    "observacao"
]

ARQUIVO_SAIDA.parent.mkdir(
    parents=True,
    exist_ok=True
)

with open(
    ARQUIVO_SAIDA,
    "w",
    encoding="utf-8-sig",
    newline=""
) as arquivo:

    escritor = csv.DictWriter(
        arquivo,
        fieldnames=campos
    )

    escritor.writeheader()
    escritor.writerows(registros)

print("\n--------------------------------")
print("DOWNLOAD CONCLUIDO")
print(f"Municipios processados: {len(registros)}")
print(f"Total de estabelecimentos: "
      f"{sum(r['estabelecimentos'] for r in registros):,}")
print(f"Arquivo salvo em: {ARQUIVO_SAIDA}")
print("--------------------------------")
