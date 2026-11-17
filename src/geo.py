
from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st


# Caminho do arquivo geográfico dentro do projeto
BASE_DIR = Path(__file__).resolve().parents[1]
GEOJSON_PATH = BASE_DIR / "data" / "municipios_rs.geojson"


@st.cache_data(show_spinner="Carregando limites municipais do RS...")
def load_rs_geometry():

    if not GEOJSON_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo geográfico não encontrado: {GEOJSON_PATH}"
        )

    # Carrega os limites municipais diretamente do arquivo local
    gdf = gpd.read_file(GEOJSON_PATH)

    # Padroniza os códigos IBGE
    if "code_muni" not in gdf.columns:
        raise ValueError(
            "A coluna code_muni não foi encontrada no GeoJSON."
        )

    gdf["code_muni"] = (
        gdf["code_muni"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )

    # Padroniza o sistema de coordenadas
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    return gdf


def regional_geometry(municipalities):

    gdf = load_rs_geometry()

    if municipalities.empty:
        return gdf.iloc[0:0].copy()

    codes = (
        municipalities["codigo_ibge"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )

    return gdf[gdf["code_muni"].isin(codes)].copy()
