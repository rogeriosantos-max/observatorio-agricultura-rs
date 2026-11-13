import geopandas as gpd
import pandas as pd
import streamlit as st

@st.cache_data(show_spinner="Carregando limites municipais do RS...")
def load_rs_geometry():
    # A biblioteca geobr obtém os limites municipais oficiais do IBGE.
    import geobr
    gdf = geobr.read_municipality(code_muni=43, year=2020)
    gdf["code_muni"] = gdf["code_muni"].astype(str).str.replace(r"\.0$", "", regex=True)
    return gdf.to_crs(epsg=4326)

def regional_geometry(municipalities):
    gdf = load_rs_geometry()
    if municipalities.empty:
        return gdf.iloc[0:0].copy()
    codes = municipalities["codigo_ibge"].astype(str).str.replace(r"\.0$", "", regex=True)
    return gdf[gdf["code_muni"].isin(codes)].copy()
