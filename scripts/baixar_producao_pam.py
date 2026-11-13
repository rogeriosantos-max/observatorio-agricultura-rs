
from pathlib import Path
import time
import requests
import pandas as pd

# ============================================================
# CONFIGURAÇÕES
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

ARQUIVO_MUNICIPIOS = ROOT / "config" / "municipios.csv"
PASTA_SAIDA = ROOT / "data" / "processed"
ARQUIVO_SAIDA = PASTA_SAIDA / "producao_agricola.csv"

ANO_INICIAL = 2025
ANO_FINAL = 2025

URL_BASE = "https://apisidra.ibge.gov.br/values"

# Tabelas, classificações e variáveis
TABELAS = {
    1612: {
        "tipo": "Temporária",
        "classificacao": 81,
        "variaveis": [109, 216, 214, 112, 215]
    },
    1613: {
        "tipo": "Permanente",
        "classificacao": 82,
        "variaveis": [2313, 216, 214, 112, 215]
    }
}

NOMES_VARIAVEIS = {
    109: "area_plantada_ha",
    2313: "area_destinada_colheita_ha",
    216: "area_colhida_ha",
    214: "quantidade_t",
    112: "produtividade_kg_ha",
    215: "valor_producao_mil_reais"
}


# ============================================================
# LEITURA DOS MUNICÍPIOS
# ============================================================

def carregar_municipios():

    municipios = pd.read_csv(
        ARQUIVO_MUNICIPIOS,
        dtype={"codigo_ibge": str},
        encoding="utf-8-sig"
    )

    municipios["codigo_ibge"] = (
        municipios["codigo_ibge"]
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(7)
    )

    return municipios


# ============================================================
# CONSULTA À API SIDRA
# ============================================================

def consultar_tabela(codigo_municipio, tabela, configuracao):

    classificacao = configuracao["classificacao"]
    variaveis = ",".join(
        str(v) for v in configuracao["variaveis"]
    )

    periodos = (
        f"{ANO_INICIAL}-{ANO_FINAL}"
        if ANO_INICIAL != ANO_FINAL
        else str(ANO_INICIAL)
    )

    url = (
        f"{URL_BASE}/t/{tabela}"
        f"/n6/{codigo_municipio}"
        f"/v/{variaveis}"
        f"/p/{periodos}"
        f"/c{classificacao}/all"
    )

    resposta = requests.get(url, timeout=120)
    resposta.raise_for_status()

    dados = resposta.json()

    if not isinstance(dados, list) or len(dados) <= 1:
        return pd.DataFrame()

    df = pd.DataFrame(dados[1:])

    if df.empty:
        return df

    df["tabela_sidra"] = tabela
    df["tipo_lavoura"] = configuracao["tipo"]

    return df


# ============================================================
# PADRONIZAÇÃO DOS DADOS
# ============================================================

def padronizar_dados(df, municipios):

    if df.empty:
        return pd.DataFrame()

    colunas = [
        "D1C", "D2C", "D3C", "D4C", "D4N",
        "V", "tabela_sidra", "tipo_lavoura"
    ]

    df = df[colunas].copy()

    df["codigo_ibge"] = df["D1C"].astype(str).str.zfill(7)
    df["ano"] = pd.to_numeric(df["D3C"], errors="coerce")
    df["codigo_variavel"] = pd.to_numeric(
        df["D2C"], errors="coerce"
    )
    df["codigo_cultura"] = df["D4C"].astype(str)
    df["cultura"] = df["D4N"].astype(str)

    # "-" e "..." são convertidos em valores ausentes
    df["valor"] = pd.to_numeric(df["V"], errors="coerce")

    indices = [
        "codigo_ibge",
        "ano",
        "codigo_cultura",
        "cultura",
        "tabela_sidra",
        "tipo_lavoura"
    ]

    tabela = df.pivot_table(
        index=indices,
        columns="codigo_variavel",
        values="valor",
        aggfunc="first"
    ).reset_index()

    tabela.columns.name = None

    # Renomear variáveis para nomes padronizados
    tabela = tabela.rename(columns=NOMES_VARIAVEIS)

    # Garantir que todas as colunas existam
    for coluna in NOMES_VARIAVEIS.values():
        if coluna not in tabela.columns:
            tabela[coluna] = pd.NA

    # Associar nomes oficiais do arquivo de municípios
    tabela = tabela.merge(
        municipios[["codigo_ibge", "nome"]],
        on="codigo_ibge",
        how="left"
    )

    tabela = tabela.rename(columns={"nome": "municipio"})

    # Identificar registros agregados
    tabela["eh_total"] = tabela["codigo_cultura"] == "0"

    return tabela


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

def main():

    print("=" * 60)
    print("OBSERVATÓRIO TERRITORIAL DA AGRICULTURA")
    print("INTEGRAÇÃO PAM / IBGE - SIDRA")
    print("=" * 60)

    municipios = carregar_municipios()

    print(f"\nMunicípios identificados: {len(municipios)}")
    print(f"Período: {ANO_INICIAL} a {ANO_FINAL}")

    resultados = []

    total_consultas = len(municipios) * len(TABELAS)
    consulta_atual = 0

    for codigo in municipios["codigo_ibge"]:

        nome = municipios.loc[
            municipios["codigo_ibge"] == codigo,
            "nome"
        ].iloc[0]

        print(f"\nMunicípio: {nome} ({codigo})")

        for tabela, configuracao in TABELAS.items():

            consulta_atual += 1

            print(
                f"  Consulta {consulta_atual}/{total_consultas}: "
                f"Tabela {tabela}"
            )

            try:

                dados = consultar_tabela(
                    codigo,
                    tabela,
                    configuracao
                )

                if not dados.empty:
                    dados = padronizar_dados(
                        dados,
                        municipios
                    )

                    resultados.append(dados)

                    print(
                        f"  Registros recebidos: {len(dados)}"
                    )
                else:
                    print("  Nenhum registro retornado.")

            except Exception as erro:

                print(f"  ERRO: {erro}")

            time.sleep(0.3)

    if not resultados:

        print("\nERRO: Nenhum dado foi obtido.")
        return

    # Unificar os resultados
    final = pd.concat(
        resultados,
        ignore_index=True
    )

    # Organizar colunas
    colunas = [
        "codigo_ibge",
        "municipio",
        "ano",
        "tipo_lavoura",
        "tabela_sidra",
        "codigo_cultura",
        "cultura",
        "area_plantada_ha",
        "area_destinada_colheita_ha",
        "area_colhida_ha",
        "quantidade_t",
        "produtividade_kg_ha",
        "valor_producao_mil_reais",
        "eh_total"
    ]

    final = final[colunas]

    final = final.sort_values(
        ["municipio", "tipo_lavoura", "cultura"]
    )

    # Salvar arquivo
    PASTA_SAIDA.mkdir(
        parents=True,
        exist_ok=True
    )

    final.to_csv(
        ARQUIVO_SAIDA,
        index=False,
        sep=";",
        decimal=",",
        encoding="utf-8-sig"
    )

    # Relatório
    print("\n" + "=" * 60)
    print("IMPORTAÇÃO CONCLUÍDA")
    print("=" * 60)

    print(f"Arquivo: {ARQUIVO_SAIDA}")
    print(f"Registros: {len(final)}")
    print(
        "Municípios encontrados:",
        final["codigo_ibge"].nunique()
    )
    print(
        "Culturas identificadas:",
        final.loc[
            ~final["eh_total"], "cultura"
        ].nunique()
    )

    print("\nRegistros por tipo de lavoura:")
    print(final["tipo_lavoura"].value_counts())

    print("\nAmostra dos dados:")
    print(
        final[
            [
                "municipio",
                "cultura",
                "quantidade_t",
                "ano"
            ]
        ].head(10).to_string(index=False)
    )

    print("\nArquivo CSV gerado com sucesso.")


if __name__ == "__main__":
    main()
