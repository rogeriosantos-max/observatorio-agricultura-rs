
from pathlib import Path
import pandas as pd
import requests

# --------------------------------------------------
# CAMINHOS DOS ARQUIVOS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

ARQUIVO_MUNICIPIOS = ROOT / "config" / "municipios.csv"

ARQUIVO_FAMILIAR = (
    ROOT / "data" / "processed" / "agricultura_familiar.csv"
)

ARQUIVO_SAIDA = (
    ROOT / "data" / "processed"
    / "agricultura_familiar_participacao.csv"
)

# --------------------------------------------------
# CONFIGURACAO SIDRA / IBGE
# --------------------------------------------------

URL_BASE = "https://apisidra.ibge.gov.br/values"

TABELA = "6778"
VARIAVEL = "183"
ANO = "2017"

CATEGORIA_TOTAL = "46302"
CATEGORIA_FAMILIAR = "46304"


def normalizar_codigo(valor):
    return str(valor).replace(".0", "").strip().zfill(7)


def consultar_ibge(codigo, categoria, sessao):
    url = (
        f"{URL_BASE}/t/{TABELA}/n6/{codigo}"
        f"/v/{VARIAVEL}/p/{ANO}/c829/{categoria}"
    )

    resposta = sessao.get(url, timeout=60)
    resposta.raise_for_status()

    dados = resposta.json()

    for item in dados:
        if item.get("D1C") == codigo:
            valor = item.get("V")

            if valor in (None, "", "-", "..."):
                return None

            return float(valor.replace(",", "."))

    raise ValueError(
        f"IBGE nao retornou dados para codigo {codigo}, "
        f"categoria {categoria}"
    )


def main():

    print("\nCONSULTA DE AGRICULTURA FAMILIAR - IBGE")
    print("Referencia: Censo Agropecuario 2017")
    print("-" * 55)

    # Carrega os municipios
    municipios = pd.read_csv(
        ARQUIVO_MUNICIPIOS,
        encoding="utf-8-sig",
        dtype={"codigo_ibge": str},
        skip_blank_lines=True
    )

    municipios["codigo_ibge"] = (
        municipios["codigo_ibge"].apply(normalizar_codigo)
    )

    # Carrega a base familiar existente
    familiar = pd.read_csv(
        ARQUIVO_FAMILIAR,
        encoding="utf-8-sig",
        dtype={"codigo_ibge": str}
    )

    familiar["codigo_ibge"] = (
        familiar["codigo_ibge"].apply(normalizar_codigo)
    )

    resultados = []

    with requests.Session() as sessao:

        total_municipios = len(municipios)

        for indice, municipio in municipios.iterrows():

            codigo = municipio["codigo_ibge"]
            nome = municipio["nome"]

            print(
                f"Consultando {indice + 1}/{total_municipios}: "
                f"{nome}"
            )

            estabelecimentos_total = consultar_ibge(
                codigo,
                CATEGORIA_TOTAL,
                sessao
            )

            estabelecimentos_familiares = consultar_ibge(
                codigo,
                CATEGORIA_FAMILIAR,
                sessao
            )

            resultados.append({
                "codigo_ibge": codigo,
                "total_estabelecimentos": estabelecimentos_total,
                "estabelecimentos_ibge_familiar": (
                    estabelecimentos_familiares
                )
            })

    # Organiza os resultados
    dados_ibge = pd.DataFrame(resultados)

    # Integra com a base familiar existente
    base = familiar.merge(
        dados_ibge,
        on="codigo_ibge",
        how="left",
        validate="one_to_one"
    )

    # Converte os valores para formato numerico
    base["estabelecimentos"] = pd.to_numeric(
        base["estabelecimentos"],
        errors="coerce"
    )

    base["total_estabelecimentos"] = pd.to_numeric(
        base["total_estabelecimentos"],
        errors="coerce"
    )

    base["estabelecimentos_ibge_familiar"] = pd.to_numeric(
        base["estabelecimentos_ibge_familiar"],
        errors="coerce"
    )

    # Calcula a participacao percentual
    base["participacao_percentual"] = (
        base["estabelecimentos"]
        / base["total_estabelecimentos"]
        * 100
    )

    # Verifica consistencia dos dados
    if base["total_estabelecimentos"].isna().any():
        raise ValueError(
            "Existem municipios sem total de estabelecimentos."
        )

    if base["estabelecimentos"].isna().any():
        raise ValueError(
            "Existem municipios sem dados de agricultura familiar."
        )

    divergencias = (
        base["estabelecimentos"]
        != base["estabelecimentos_ibge_familiar"]
    )

    if divergencias.any():
        print("\nATENCAO: divergencia entre a base familiar")
        print("existente e a nova consulta ao IBGE:")
        print(
            base.loc[
                divergencias,
                [
                    "municipio",
                    "estabelecimentos",
                    "estabelecimentos_ibge_familiar"
                ]
            ].to_string(index=False)
        )

        raise ValueError(
            "A consulta foi interrompida para evitar "
            "gerar percentuais com dados divergentes."
        )

    # Salva uma nova base, sem alterar o arquivo original
    base.to_csv(
        ARQUIVO_SAIDA,
        sep=",",
        index=False,
        encoding="utf-8-sig"
    )

    print("\n" + "-" * 55)
    print("CONSULTA CONCLUIDA!")
    print(f"Municipios processados: {len(base)}")
    print(
        "Total de estabelecimentos familiares:",
        f"{base['estabelecimentos'].sum():,.0f}"
    )

    print(
        "Total de estabelecimentos agropecuarios:",
        f"{base['total_estabelecimentos'].sum():,.0f}"
    )

    print(
        "Participacao regional:",
        f"{base['estabelecimentos'].sum() / base['total_estabelecimentos'].sum() * 100:.2f}%"
    )

    print("\nPRIMEIROS RESULTADOS:")
    print(
        base[
            [
                "municipio",
                "estabelecimentos",
                "total_estabelecimentos",
                "participacao_percentual"
            ]
        ].head(10).to_string(index=False)
    )

    print("\nArquivo gerado:")
    print(ARQUIVO_SAIDA)


if __name__ == "__main__":
    main()
