
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "config"

FILES = {
    "credito": (
        "credito_rural.csv",
        [
            "ano", "codigo_ibge", "municipio", "programa",
            "finalidade", "produto", "fonte_recurso",
            "contratos", "valor"
        ]
    ),

    "agricola": (
        "producao_agricola.csv",
        [
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
    ),

  
    "familiar": (
        "agricultura_familiar_participacao.csv",
        [
            "ano", "codigo_ibge", "municipio",
            "estabelecimentos", "agricultores",
            "area_ha", "observacao",
            "total_estabelecimentos",
            "participacao_percentual"
        ]
    ),


    "pecuaria": (
        "pecuaria.csv",
        [
            "ano", "codigo_ibge", "municipio",
            "produto", "quantidade", "unidade",
            "valor_mil_reais"
        ]
    ),

    "solo": (
        "uso_solo.csv",
        [
            "ano", "codigo_ibge", "municipio",
            "classe", "area_ha"
        ]
    ),
}


def load_municipios():
    path = CONFIG / "municipios.csv"

    if not path.exists():
        return pd.DataFrame(
            columns=["codigo_ibge", "nome"]
        )

    df = pd.read_csv(
        path,
        dtype={"codigo_ibge": str}
    )

    df["nome"] = df["nome"].astype(str).str.strip()

    return df.dropna(subset=["nome"])



def load_table(key):
    filename, columns = FILES[key]
    path = PROCESSED / filename

  
    if not path.exists():
        return pd.DataFrame(columns=columns)

    if key in ("agricola", "pecuaria"):
        df = pd.read_csv(
            path,
            sep=";",
            encoding="utf-8-sig",
            low_memory=False,
            dtype={"codigo_ibge": str}
        )
    else:
        df = pd.read_csv(
            path,
            low_memory=False
        )

    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA

    df = df[columns].copy()

    
    if key == "agricola":
        numeric_columns = [
            "ano",
            "area_plantada_ha",
            "area_destinada_colheita_ha",
            "area_colhida_ha",
            "quantidade_t",
            "produtividade_kg_ha",
            "valor_producao_mil_reais"
        ]

        for col in numeric_columns:
            df[col] = pd.to_numeric(
                df[col].astype("string").str.replace(
                    ",", ".", regex=False
                ),
                errors="coerce"
            )

    elif key == "pecuaria":
        numeric_columns = [
            "ano",
            "quantidade",
            "valor_mil_reais"
        ]

        for col in numeric_columns:
            df[col] = pd.to_numeric(
                df[col].astype("string").str.replace(
                    ",", ".", regex=False
                ),
                errors="coerce"
            )


    return df



def save_uploaded_table(key, uploaded_file):
    filename, columns = FILES[key]

    df = pd.read_csv(
        uploaded_file,
        low_memory=False
    )

    missing = [
        c for c in columns
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            "Colunas obrigatórias ausentes: "
            + ", ".join(missing)
        )

    PROCESSED.mkdir(
        parents=True,
        exist_ok=True
    )

    df[columns].to_csv(
        PROCESSED / filename,
        index=False,
        encoding="utf-8-sig"
    )

    return len(df)


def filter_region(df, municipalities):
    if (
        df.empty
        or municipalities.empty
        or "codigo_ibge" not in df.columns
    ):
        return df.copy()

    codes = (
        municipalities["codigo_ibge"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
    )

    data = df.copy()

    data["codigo_ibge"] = (
        data["codigo_ibge"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
    )

    return data[data["codigo_ibge"].isin(codes)]
