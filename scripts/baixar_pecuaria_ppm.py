
import csv
import time
from pathlib import Path

import requests


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

ARQUIVO_MUNICIPIOS = ROOT / "config" / "municipios.csv"
ARQUIVO_SAIDA = ROOT / "data" / "processed" / "pecuaria.csv"

ANO = 2025
TABELA = 3939
VARIAVEL = 105
CLASSIFICACAO = 79

REBANHOS = {
    "2670": "Bovino",
    "2675": "Bubalino",
    "2672": "Equino",
    "32794": "Suíno - total",
    "2681": "Caprino",
    "2677": "Ovino",
    "32796": "Galináceos - total",
    "2680": "Codornas",
}

COLUNAS = [
    "ano",
    "codigo_ibge",
    "municipio",
    "produto",
    "quantidade",
    "unidade",
    "valor_mil_reais",
]


# ============================================================
# CARREGAR MUNICÍPIOS
# ============================================================

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


if not municipios:
    raise RuntimeError(
        "Nenhum município encontrado no arquivo de configuração."
    )


# ============================================================
# CONSULTAR SIDRA / IBGE
# ============================================================

session = requests.Session()

registros = []

total_consultas = len(municipios) * len(REBANHOS)
consulta_atual = 0

print("=" * 60)
print("COLETA DA PECUÁRIA - IBGE / PPM")
print("Tabela SIDRA:", TABELA)
print("Ano:", ANO)
print("Municípios:", len(municipios))
print("Categorias:", len(REBANHOS))
print("Consultas previstas:", total_consultas)
print("=" * 60)


for municipio in municipios:

    codigo = str(
        municipio["codigo_ibge"]
    ).strip()

    nome = municipio["nome"].strip()

    for codigo_rebanho, nome_rebanho in REBANHOS.items():

        consulta_atual += 1

        url = (
            f"https://apisidra.ibge.gov.br/values/"
            f"t/{TABELA}/"
            f"n6/{codigo}/"
            f"v/{VARIAVEL}/"
            f"p/{ANO}/"
            f"c{CLASSIFICACAO}/{codigo_rebanho}"
        )

        resposta = session.get(
            url,
            timeout=60
        )

        resposta.raise_for_status()

        dados = resposta.json()

        if not isinstance(dados, list):
            raise RuntimeError(
                f"Resposta inesperada para {nome} - {nome_rebanho}"
            )

        if len(dados) < 2:
            raise RuntimeError(
                f"Resposta sem dados para {nome} - {nome_rebanho}"
            )

        item = dados[1]

        valor = item.get("V", "").strip()

        # Ignorar valores não disponíveis
        if valor in ("", "-", "..."):
            print(
                f"[SEM DADO] {nome} - {nome_rebanho}"
            )
            time.sleep(0.15)
            continue

        registros.append({
            "ano": ANO,
            "codigo_ibge": codigo,
            "municipio": nome,
            "produto": nome_rebanho,
            "quantidade": valor,
            "unidade": item.get("MN", "Cabeças"),
            "valor_mil_reais": "",
        })

        print(
            f"[{consulta_atual}/{total_consultas}] "
            f"{nome} - {nome_rebanho}: {valor}"
        )

        time.sleep(0.15)


# ============================================================
# VALIDAR RESULTADOS
# ============================================================

if not registros:
    raise RuntimeError(
        "Nenhum registro foi obtido. Arquivo anterior preservado."
    )

municipios_com_dados = len({
    registro["codigo_ibge"]
    for registro in registros
})

print("\nRESUMO DA COLETA")
print("Registros obtidos:", len(registros))
print("Municípios com dados:", municipios_com_dados)
print("Ano:", ANO)


# ============================================================
# SALVAR CSV
# ============================================================

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
        fieldnames=COLUNAS,
        delimiter=";"
    )

    escritor.writeheader()
    escritor.writerows(registros)


print("\nArquivo salvo com sucesso:")
print(ARQUIVO_SAIDA)

print("\nColeta concluída!")
