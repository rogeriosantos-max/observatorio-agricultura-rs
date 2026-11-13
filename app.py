from pathlib import Path
import sys
from io import BytesIO

import pandas as pd

import streamlit as st
import plotly.express as px
import folium
from streamlit_folium import st_folium
from folium.plugins import Fullscreen
from branca.element import Element

# ============================================================
# CAMINHOS E IMPORTAÇÕES
# ============================================================

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.data import (
    load_municipios,
    load_table,
    filter_region,
    save_uploaded_table,
    FILES
)

from src.geo import regional_geometry


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Observatório da Agricultura RS",
    page_icon="🌱",
    layout="wide"
)

SICOR_FILE = (
    ROOT / "outputs_sicor" /
    "sicor_centro_sul_21_municipios.csv"
)


st.markdown("""
<style>

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}

[data-testid="stMetric"] {
    background: #f3f7f4;
    border: 1px solid #dce8df;
    padding: 12px;
    border-radius: 10px;
}

</style>
""", unsafe_allow_html=True)


st.title("🌱 Observatório Territorial da Agricultura")

st.caption(
    "Centro-Sul do Rio Grande do Sul | "
    "Inteligência territorial, crédito rural e produção agropecuária"
)


# ============================================================
# CARREGAMENTO DOS MUNICÍPIOS
# ============================================================

municipios = load_municipios()

if municipios.empty:
    st.error(
        "Não foi possível carregar config/municipios.csv."
    )
    st.stop()

municipios["codigo_ibge"] = (
    municipios["codigo_ibge"]
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
    .str.strip()
)

if len(municipios) != 21:
    st.warning(
        f"A configuração contém {len(municipios)} municípios. "
        "Verifique config/municipios.csv."
    )


# ============================================================
# LEITURA E PADRONIZAÇÃO DO SICOR
# ============================================================

@st.cache_data(show_spinner="Carregando dados do SICOR...")
def load_sicor(path, municipio_codes):

    """
    Carrega o arquivo regional do SICOR.

    Padroniza os campos necessários para o painel,
    preservando os dados originais da matriz.
    """

    if not Path(path).exists():
        return pd.DataFrame()

    df = pd.read_csv(
        path,
        sep=";",
        decimal=",",
        encoding="utf-8-sig",
        low_memory=False,
        dtype={"COD_MUNICIPIO_IBGE": "string"},
        on_bad_lines="error"
    )

    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
    )

    # --------------------------------------------------------
    # Verificação da estrutura mínima
    # --------------------------------------------------------

    if "COD_MUNICIPIO_IBGE" not in df.columns:
        raise ValueError(
            "A coluna COD_MUNICIPIO_IBGE não foi encontrada no SICOR."
        )

    # --------------------------------------------------------
    # Padronização dos códigos IBGE
    # --------------------------------------------------------

    df["COD_MUNICIPIO_IBGE"] = (
        df["COD_MUNICIPIO_IBGE"]
        .astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )

    df["codigo_ibge"] = df["COD_MUNICIPIO_IBGE"]

    # Restringe a base aos municípios configurados
    municipio_codes = [
        str(c).replace(".0", "").strip()
        for c in municipio_codes
    ]

    df = df[
        df["codigo_ibge"].isin(municipio_codes)
    ].copy()

    if df.empty:
        return df

    # --------------------------------------------------------
    # Data de emissão
    # --------------------------------------------------------

    if "ANO_MES_EMISSAO" in df.columns:

        data_original = (
            df["ANO_MES_EMISSAO"]
            .astype("string")
            .str.strip()
        )

        data_formatada = pd.to_datetime(
            data_original,
            format="%Y%m",
            errors="coerce"
        )

        # Tenta formato alternativo para datas não padronizadas
        data_alternativa = pd.to_datetime(
            data_original,
            errors="coerce"
        )

        df["DATA_EMISSAO"] = (
            data_formatada.fillna(data_alternativa)
        )

    else:

        df["DATA_EMISSAO"] = pd.NaT

    df["ANO"] = df["DATA_EMISSAO"].dt.year
    df["MES"] = df["DATA_EMISSAO"].dt.month

    # --------------------------------------------------------
    # Conversão dos valores numéricos
    # --------------------------------------------------------

    numeric_columns = [
        "CUSTEIO_AREA",
        "CUSTEIO_QTDE",
        "CUSTEIO_VALOR",
        "INVESTIMENTO_AREA",
        "INVESTIMENTO_QTDE",
        "INVESTIMENTO_VALOR",
        "COMERCIALIZACAO_QTDE",
        "COMERCIALIZACAO_VALOR",
        "INDUSTRIALIZACAO_QTDE",
        "INDUSTRIALIZACAO_VALOR",
        "TOTAL_AREA",
        "TOTAL_QTDE",
        "TOTAL_VALOR"
    ]

    for col in numeric_columns:

        if col in df.columns:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            ).fillna(0)

        else:

            df[col] = 0

    # --------------------------------------------------------
    # Padronização dos campos textuais
    # --------------------------------------------------------

    text_columns = [
        "MUNICIPIO",
        "PROGRAMA",
        "SUBPROGRAMA",
        "ATIVIDADE",
        "FONTE_RECURSO",
        "NOME_IF"
    ]

    for col in text_columns:

        if col not in df.columns:
            df[col] = "Não informado"

        df[col] = (
            df[col]
            .fillna("Não informado")
            .astype(str)
            .str.strip()
        )

    # --------------------------------------------------------
    # Nomes oficiais dos municípios
    # --------------------------------------------------------

    municipality_map = dict(
        zip(
            municipios["codigo_ibge"].astype(str),
            municipios["nome"]
        )
    )

    df["municipio"] = (
        df["codigo_ibge"]
        .map(municipality_map)
        .fillna(df["MUNICIPIO"])
    )

    # --------------------------------------------------------
    # Campos padronizados do dashboard
    # --------------------------------------------------------

    df["ano"] = df["ANO"]
    df["mes"] = df["MES"]
    df["data_emissao"] = df["DATA_EMISSAO"]

    df["programa"] = df["PROGRAMA"]
    df["subprograma"] = df["SUBPROGRAMA"]
    df["atividade"] = df["ATIVIDADE"]
    df["fonte_recurso"] = df["FONTE_RECURSO"]

    df["instituicao_financeira"] = df["NOME_IF"]

    df["valor"] = df["TOTAL_VALOR"]
    df["area_total"] = df["TOTAL_AREA"]

    # Preserva o significado original do campo TOTAL_QTDE
    df["quantidade_sicor"] = df["TOTAL_QTDE"]

    return df


# ============================================================
# CARREGAMENTO DAS BASES
# ============================================================

tables = {
    key: filter_region(
        load_table(key),
        municipios
    )
    for key in FILES
}

# Garante a existência dos módulos utilizados pelo painel
for key in [
    "credito",
    "agricola",
    "familiar",
    "pecuaria",
    "solo"
]:
    tables.setdefault(key, pd.DataFrame())


# ------------------------------------------------------------
# Integração do SICOR
# ------------------------------------------------------------

credito_sicor = load_sicor(
    str(SICOR_FILE),
    municipios["codigo_ibge"].astype(str).tolist()
)

if not credito_sicor.empty:

    tables["credito"] = credito_sicor

    st.sidebar.success(
        f"SICOR integrado: {len(credito_sicor):,} registros"
    )


# ============================================================
# FILTROS
# ============================================================

with st.sidebar:

    st.header("Filtros")

    st.caption(
        "Os filtros consideram somente os dados carregados."
    )

    all_years = []

    for df in tables.values():

        if not df.empty and "ano" in df.columns:

            values = pd.to_numeric(
                df["ano"],
                errors="coerce"
            ).dropna().astype(int).tolist()

            all_years.extend(values)

    years = sorted(set(all_years))

    if years:

        selected_years = st.multiselect(
            "Ano(s)",
            years,
            default=years[-3:]
        )

    else:

        selected_years = []

        st.info(
            "Não há anos disponíveis nas bases carregadas."
        )

    municipal_names = (
        municipios["nome"].dropna().tolist()
    )

    selected_munis = st.multiselect(
        "Município(s)",
        municipal_names,
        default=municipal_names
    )

    st.divider()

    st.subheader("Importar dados complementares")

    upload_labels = {
        "agricola": "Produção agrícola",
        "familiar": "Agricultura familiar",
        "pecuaria": "Pecuária",
        "solo": "Uso e cobertura do solo"
    }

    for key, label in upload_labels.items():

        up = st.file_uploader(
            f"{label} (CSV)",
            type=["csv"],
            key=f"upload_{key}"
        )

        if up is not None:

            try:

                n = save_uploaded_table(key, up)

                st.success(
                    f"{n} linhas gravadas. Atualize a página."
                )

            except Exception as e:

                st.error(str(e))


# ============================================================
# APLICAÇÃO DOS FILTROS
# ============================================================

def apply_filters(df, ignore_year=False):

    if df.empty:
        return df

    out = df.copy()

    if (
        not ignore_year
        and selected_years
        and "ano" in out.columns
    ):

        out = out[
            pd.to_numeric(
                out["ano"],
                errors="coerce"
            ).isin(selected_years)
        ]

    if selected_munis and "municipio" in out.columns:

        out = out[
            out["municipio"].isin(selected_munis)
        ]

    
    return out


tables = {
    key: apply_filters(
        df,
        ignore_year=(key in ("familiar", "solo"))
    )
    for key, df in tables.items()
}

credito, agricola, familiar, pecuaria, solo = (
    tables[key]
    for key in [
        "credito",
        "agricola",
        "familiar",
        "pecuaria",
        "solo"
    ]
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def total(df, col):

    if df.empty or col not in df.columns:
        return 0

    return pd.to_numeric(
        df[col],
        errors="coerce"
    ).fillna(0).sum()


def moeda(valor):

    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


# ============================================================
# PAINEL REGIONAL
# ============================================================

st.subheader("Painel regional")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Municípios configurados",
    len(municipios)
)

c2.metric(
    "Crédito rural",
    moeda(total(credito, "valor"))
)

c3.metric(
    "Registros SICOR",
    f"{len(credito):,}".replace(",", ".")
)

c4.metric(
    "Produção agrícola",
    f"{total(agricola, 'quantidade_t'):,.1f} t"
)


# ============================================================
# ABAS
# ============================================================

(
    tab_map,
    tab_credit,
    tab_agri,
    tab_family,
    tab_livestock,
    tab_land,
    tab_data
) = st.tabs([
    "🗺️ Mapa",
    "💳 Crédito rural",
    "🌾 Produção agrícola",
    "👨‍🌾 Agricultura familiar",
    "🐄 Pecuária",
    "🌳 Uso do solo",
    "📁 Dados e metodologia"
])


# ============================================================
# MAPA MUNICIPAL INTERATIVO
# ============================================================

with tab_map:

    st.markdown("### Mapa municipal interativo")

    metric_options = {
        "Crédito rural (R$)": (credito, "valor"),
        "Produção agrícola (toneladas)": (
            agricola, "quantidade_t"
        ),
        "Área plantada (ha)": (
            agricola, "area_plantada_ha"
        ),
        "Estabelecimentos familiares": (
            familiar, "estabelecimentos"
        ),
        "Rebanho / produção pecuária": (
            pecuaria, "quantidade"
        ),
        "Área por classe de uso do solo (ha)": (
            solo, "area_ha"
        )
    }

    metric_label = st.selectbox(
        "Indicador para colorir o mapa",
        list(metric_options)
    )

    source, col = metric_options[metric_label]

    try:

        gdf = regional_geometry(municipios)

        if not gdf.empty:

            # ------------------------------------------------
            # Agregação dos dados por município
            # ------------------------------------------------

            if (
                not source.empty
                and col in source.columns
                and "codigo_ibge" in source.columns
            ):

                agg = source.copy()

                agg["_value"] = pd.to_numeric(
                    agg[col],
                    errors="coerce"
                ).fillna(0)

                agg["codigo_ibge"] = (
                    agg["codigo_ibge"]
                    .astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip()
                )

                agg = (
                    agg.groupby("codigo_ibge")["_value"]
                    .sum()
                    .reset_index()
                )

                gdf = gdf.merge(
                    agg,
                    left_on="code_muni",
                    right_on="codigo_ibge",
                    how="left"
                )

            else:

                gdf["_value"] = 0

            gdf["_value"] = gdf["_value"].fillna(0)

        
            # ------------------------------------------------
            # Centro geográfico do mapa
            # ------------------------------------------------

            geometria_unida = gdf.geometry.unary_union

            if geometria_unida is None or geometria_unida.is_empty:
                st.warning("Não foi possível determinar o centro geográfico.")
                st.stop()

            centroide = geometria_unida.centroid

            center = [
                centroide.y,
                centroide.x
            ]

            
            # ------------------------------------------------
            # Construção do mapa
            # ------------------------------------------------

            m = folium.Map(
                location=center,
                zoom_start=8,
                tiles=None,
                zoom_control=True,
                control_scale=False,
                prefer_canvas=True
            )

            # ------------------------------------------------
            # Controle de tela cheia
            # ------------------------------------------------

            Fullscreen(
                position="topright",
                title="Expandir mapa",
                title_cancel="Sair da tela cheia",
                force_separate_button=True
            ).add_to(m)

            # ------------------------------------------------
            # Camada temática
            # ------------------------------------------------

            choropleth = folium.Choropleth(
                geo_data=gdf.to_json(),
                data=gdf,
                columns=["code_muni", "_value"],
                key_on="feature.properties.code_muni",
                fill_color="YlGn",
                fill_opacity=0.75,
                line_opacity=0.45,
                legend_name=metric_label,
                nan_fill_color="#eeeeee",
                nan_fill_opacity=0.5,
                bins=4
            )

            choropleth.add_to(m)

            # ------------------------------------------------
            # Ajuste visual da legenda
            # ------------------------------------------------

            css_legenda = """
            <style>
            .legend text {
                font-size: 9px !important;
            }
            </style>
            """

            m.get_root().header.add_child(
                Element(css_legenda)
            )

            # ------------------------------------------------
            # Nomes dos municípios e valores ao passar o mouse
            # ------------------------------------------------

            folium.GeoJson(
                gdf,
                tooltip=folium.GeoJsonTooltip(
                    fields=["name_muni", "_value"],
                    aliases=[
                        "Município:",
                        metric_label + ":"
                    ],
                    localize=True,
                    sticky=True
                ),
                style_function=lambda feature: {
                    "color": "#2878b5",
                    "weight": 1.5,
                    "fillOpacity": 0
                }
            ).add_to(m)

            
            # ------------------------------------------------
            # Exibição no Streamlit
            # ------------------------------------------------

            st_folium(
                m,
                height=500,
                use_container_width=True,
                returned_objects=[],
                key="mapa_observatorio"
            )

           
            st.caption(
                "Passe o cursor sobre os municípios para consultar o nome "
                "e o valor do indicador. Municípios sem dados aparecem "
                "sem preenchimento temático."
            )

    except Exception as e:
        st.error(f"Erro ao construir o mapa: {e}")


# ============================================================
# CRÉDITO RURAL — SICOR
# ============================================================

with tab_credit:

    st.markdown("### Crédito rural — SICOR")


    if credito.empty:

        st.info(
            "Não foram encontrados dados do SICOR."
        )

    else:

        st.caption(
            "Fonte: Matriz de Dados do Crédito Rural — SICOR/BCB. "
            "Os valores representam os campos disponibilizados "
            "na base regional processada."
        )

        # Indicadores principais

        a, b, c = st.columns(3)

        a.metric(
            "Valor total",
            moeda(total(credito, "valor"))
        )

        b.metric(
            "Área total informada",
            f"{total(credito, 'TOTAL_AREA'):,.2f} ha"
        )

        c.metric(
            "Quantidade total — TOTAL_QTDE",
            f"{total(credito, 'quantidade_sicor'):,.0f}"
        )

        st.divider()

        # Crédito por programa

        if {"programa", "valor"}.issubset(credito.columns):

            g = (
                credito.groupby(
                    "programa",
                    dropna=False
                )["valor"]
                .sum()
                .reset_index()
                .sort_values(
                    "valor",
                    ascending=False
                )
            )

            st.plotly_chart(
                px.bar(
                    g,
                    x="programa",
                    y="valor",
                    title="Valor de crédito por programa",
                    labels={
                        "programa": "Programa",
                        "valor": "Valor (R$)"
                    }
                ),
                use_container_width=True
            )

        # PRONAF e PRONAMP

        st.markdown("#### Comparação de programas")

        if "programa" in credito.columns:

            programa_texto = (
                credito["programa"]
                .fillna("")
                .astype(str)
                .str.upper()
            )

            credito_com_programa = credito.copy()

            credito_com_programa["grupo_programa"] = (
                "Outros programas"
            )

            credito_com_programa.loc[
                programa_texto.str.contains("PRONAF"),
                "grupo_programa"
            ] = "PRONAF"

            credito_com_programa.loc[
                programa_texto.str.contains("PRONAMP"),
                "grupo_programa"
            ] = "PRONAMP"

            g = (
                credito_com_programa
                .groupby("grupo_programa")["valor"]
                .sum()
                .reset_index()
            )

            st.plotly_chart(
                px.bar(
                    g,
                    x="grupo_programa",
                    y="valor",
                    title="PRONAF, PRONAMP e demais programas",
                    labels={
                        "grupo_programa": "Grupo",
                        "valor": "Valor (R$)"
                    }
                ),
                use_container_width=True
            )

        # Evolução mensal

        st.markdown("#### Evolução mensal do crédito")

        if "data_emissao" in credito.columns:

            g = (
                credito.dropna(subset=["data_emissao"])
                .groupby("data_emissao")["valor"]
                .sum()
                .reset_index()
                .sort_values("data_emissao")
            )

            if not g.empty:

                st.plotly_chart(
                    px.line(
                        g,
                        x="data_emissao",
                        y="valor",
                        markers=True,
                        title="Evolução mensal do valor do crédito",
                        labels={
                            "data_emissao": "Mês de emissão",
                            "valor": "Valor (R$)"
                        }
                    ),
                    use_container_width=True
                )

        # Crédito por município

        st.markdown("#### Distribuição municipal")

        g = (
            credito.groupby("municipio")["valor"]
            .sum()
            .reset_index()
            .sort_values("valor", ascending=False)
        )

        st.plotly_chart(
            px.bar(
                g,
                x="municipio",
                y="valor",
                title="Valor de crédito por município",
                labels={
                    "municipio": "Município",
                    "valor": "Valor (R$)"
                }
            ),
            use_container_width=True
        )

        # Crédito por atividade

        st.markdown("#### Crédito por atividade")

        if "atividade" in credito.columns:

            g = (
                credito.groupby("atividade")["valor"]
                .sum()
                .reset_index()
            )

            st.plotly_chart(
                px.pie(
                    g,
                    names="atividade",
                    values="valor",
                    title="Distribuição por atividade"
                ),
                use_container_width=True
            )

        # Fontes de recursos

        st.markdown("#### Fontes de recursos")

        if "fonte_recurso" in credito.columns:

            g = (
                credito.groupby("fonte_recurso")["valor"]
                .sum()
                .reset_index()
                .sort_values("valor", ascending=False)
            )

            st.plotly_chart(
                px.bar(
                    g,
                    x="fonte_recurso",
                    y="valor",
                    title="Crédito por fonte de recursos"
                ),
                use_container_width=True
            )

        # Modalidades

        st.markdown("#### Distribuição por modalidade")

        modalidades = {
            "Custeio": "CUSTEIO_VALOR",
            "Investimento": "INVESTIMENTO_VALOR",
            "Comercialização": "COMERCIALIZACAO_VALOR",
            "Industrialização": "INDUSTRIALIZACAO_VALOR"
        }

        modalidade_data = []

        for nome, coluna in modalidades.items():

            if coluna in credito.columns:

                modalidade_data.append({
                    "modalidade": nome,
                    "valor": total(credito, coluna)
                })

        if modalidade_data:

            g = pd.DataFrame(modalidade_data)

            st.plotly_chart(
                px.pie(
                    g,
                    names="modalidade",
                    values="valor",
                    title="Composição do crédito rural"
                ),
                use_container_width=True
            )

        # Tabela detalhada

        with st.expander(
            "Consultar registros detalhados do SICOR"
        ):

            st.dataframe(
                credito,
                use_container_width=True
            )

            st.download_button(
                "Baixar dados SICOR filtrados",
                credito.to_csv(
                    index=False
                ).encode("utf-8-sig"),
                file_name="sicor_centro_sul_filtrado.csv",
                mime="text/csv"
            )


# ============================================================
# PRODUÇÃO AGRÍCOLA
# ============================================================


# ============================================================
# PRODUÇÃO AGRÍCOLA - PAM / IBGE
# ============================================================

with tab_agri:

    st.markdown("### Observatório da Produção Agrícola")
    st.caption(
        "Fonte: Pesquisa Agrícola Municipal (PAM) - "
        "IBGE/SIDRA. Quantidades em toneladas."
    )

    if agricola.empty:

        st.warning(
            "Não foram encontrados dados da produção agrícola."
        )

    else:

        # ----------------------------------------------------
        # Preparação dos dados
        # ----------------------------------------------------

        dados_agri = agricola.copy()

        # Exclui os totais municipais dos gráficos
        if "eh_total" in dados_agri.columns:
            dados_agri = dados_agri[
                dados_agri["eh_total"] == False
            ].copy()

        # Garante campos numéricos
        campos_numericos = [
            "quantidade_t",
            "area_plantada_ha",
            "area_destinada_colheita_ha",
            "area_colhida_ha",
            "produtividade_kg_ha",
            "valor_producao_mil_reais"
        ]

        for campo in campos_numericos:
            if campo in dados_agri.columns:
                dados_agri[campo] = pd.to_numeric(
                    dados_agri[campo],
                    errors="coerce"
                )

        # Área de referência:
        # temporárias = área plantada
        # permanentes = área destinada à colheita
        dados_agri["area_referencia_ha"] = (
            dados_agri["area_plantada_ha"].combine_first(
                dados_agri["area_destinada_colheita_ha"]
            )
        )

        # ----------------------------------------------------
        # Filtros específicos da produção agrícola
        # ----------------------------------------------------

        st.markdown("#### Filtros de análise")

        f1, f2, f3 = st.columns(3)

        tipos = ["Todas"] + sorted(
            dados_agri["tipo_lavoura"].dropna().unique().tolist()
        )

        with f1:
            tipo_selecionado = st.selectbox(
                "Tipo de lavoura",
                tipos,
                key="agri_tipo"
            )

        dados_filtro = dados_agri.copy()

        if tipo_selecionado != "Todas":
            dados_filtro = dados_filtro[
                dados_filtro["tipo_lavoura"] == tipo_selecionado
            ]

        municipios_agri = sorted(
            dados_filtro["municipio"].dropna().unique().tolist()
        )

        with f2:
            municipios_escolhidos = st.multiselect(
                "Municípios",
                municipios_agri,
                default=municipios_agri,
                key="agri_municipios"
            )

        dados_filtro = dados_filtro[
            dados_filtro["municipio"].isin(municipios_escolhidos)
        ]

        culturas_agri = sorted(
            dados_filtro["cultura"].dropna().unique().tolist()
        )

        with f3:
            culturas_escolhidas = st.multiselect(
                "Culturas",
                culturas_agri,
                default=culturas_agri,
                key="agri_culturas"
            )

        dados = dados_filtro[
            dados_filtro["cultura"].isin(culturas_escolhidas)
        ].copy()

        st.divider()

        if dados.empty:

            st.warning(
                "Não existem registros para os filtros selecionados."
            )

        else:

            # ------------------------------------------------
            # Indicadores principais
            # ------------------------------------------------

            producao_total = dados["quantidade_t"].sum()
            area_colhida = dados["area_colhida_ha"].sum()
            area_referencia = dados["area_referencia_ha"].sum()
            valor_total = dados["valor_producao_mil_reais"].sum()
            numero_culturas = dados["cultura"].nunique()

            st.markdown("#### Indicadores da produção")

            a, b, c, d = st.columns(4)

            a.metric(
                "Produção total",
                f"{producao_total:,.0f} t"
            )

            b.metric(
                "Área colhida",
                f"{area_colhida:,.0f} ha"
            )

            c.metric(
                "Área plantada/destinada",
                f"{area_referencia:,.0f} ha"
            )

            d.metric(
                "Culturas identificadas",
                numero_culturas
            )

            st.metric(
                "Valor da produção",
                f"R$ {valor_total:,.1f} mil"
            )

            st.divider()

            # ------------------------------------------------
            # Ranking das culturas
            # ------------------------------------------------

            st.markdown("#### Ranking das culturas por produção")

            ranking = (
                dados.groupby("cultura")["quantidade_t"]
                .sum()
                .reset_index()
                .sort_values(
                    "quantidade_t",
                    ascending=False
                )
                .head(15)
                .sort_values("quantidade_t")
            )

            fig_ranking = px.bar(
                ranking,
                x="quantidade_t",
                y="cultura",
                orientation="h",
                title="15 maiores produções por cultura",
                labels={
                    "quantidade_t": "Produção (toneladas)",
                    "cultura": "Cultura"
                },
                text_auto=".2s"
            )

            st.plotly_chart(
                fig_ranking,
                use_container_width=True
            )

            # ------------------------------------------------
            # Comparação entre municípios
            # ------------------------------------------------

            st.markdown("#### Comparação entre municípios")

            culturas_disponiveis = sorted(
                dados["cultura"].dropna().unique().tolist()
            )

            cultura_principal = (
                dados.groupby("cultura")["quantidade_t"]
                .sum()
                .idxmax()
            )

            cultura_comparacao = st.selectbox(
                "Selecione a cultura para comparar",
                culturas_disponiveis,
                index=culturas_disponiveis.index(cultura_principal),
                key="agri_comparacao"
            )

            comparacao = dados[
                dados["cultura"] == cultura_comparacao
            ]

            comparacao = (
                comparacao.groupby("municipio")["quantidade_t"]
                .sum()
                .reset_index()
                .sort_values(
                    "quantidade_t",
                    ascending=True
                )
            )

            fig_municipios = px.bar(
                comparacao,
                x="quantidade_t",
                y="municipio",
                orientation="h",
                title=f"Produção de {cultura_comparacao} por município",
                labels={
                    "quantidade_t": "Produção (toneladas)",
                    "municipio": "Município"
                },
                text_auto=".2s"
            )

            st.plotly_chart(
                fig_municipios,
                use_container_width=True
            )

            # ------------------------------------------------
            # MAPA TEMÁTICO DA PRODUÇÃO AGRÍCOLA
            # ------------------------------------------------

            st.divider()
            st.markdown("#### Mapa temático da produção agrícola")
            st.caption(
                f"Distribuição territorial da produção de "
                f"{cultura_comparacao}, em toneladas."
            )

            try:
                # Limites geográficos dos municípios
                gdf_map = regional_geometry(municipios)

                # Restringe o mapa aos municípios selecionados
                gdf_map = gdf_map[
                    gdf_map["name_muni"].isin(municipios_escolhidos)
                ].copy()

                # Dados da cultura selecionada
                mapa_dados = dados[
                    dados["cultura"] == cultura_comparacao
                ].copy()

                mapa_dados["codigo_ibge"] = (
                    mapa_dados["codigo_ibge"]
                    .astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip()
                )

                mapa_dados["quantidade_t"] = pd.to_numeric(
                    mapa_dados["quantidade_t"],
                    errors="coerce"
                )

                # Agrega a produção por código IBGE
                mapa_dados = (
                    mapa_dados.groupby("codigo_ibge")["quantidade_t"]
                    .sum(min_count=1)
                    .reset_index()
                )

                gdf_map["code_muni"] = (
                    gdf_map["code_muni"]
                    .astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip()
                )

                # Junta os dados agrícolas à geometria
                gdf_map = gdf_map.merge(
                    mapa_dados,
                    left_on="code_muni",
                    right_on="codigo_ibge",
                    how="left"
                )

                gdf_map["_value"] = pd.to_numeric(
                    gdf_map["quantidade_t"],
                    errors="coerce"
                ).astype("float64")

                valores_mapa = gdf_map["_value"].dropna()

                dados_choropleth = gdf_map[
                    ["code_muni", "_value"]
                ].copy()

                dados_choropleth["_value"] = (
                    dados_choropleth["_value"].astype("float64")
                )

                if gdf_map.empty:
                    st.warning(
                        "Não há municípios para exibir no mapa."
                    )

                elif valores_mapa.empty:
                    st.warning(
                        "Não há valores de produção para esta cultura."
                    )

                else:
                    # Centro geográfico
                    geometria_unida = gdf_map.geometry.unary_union
                    centroide = geometria_unida.centroid

                    centro_mapa = [
                        centroide.y,
                        centroide.x
                    ]

                    # Criação do mapa
                    m_mapa = folium.Map(
                        location=centro_mapa,
                        zoom_start=8,
                        tiles=None,
                        zoom_control=True,
                        control_scale=False,
                        prefer_canvas=True
                    )

                    # Tela cheia
                    Fullscreen(
                        position="topright",
                        title="Expandir mapa",
                        title_cancel="Sair da tela cheia",
                        force_separate_button=True
                    ).add_to(m_mapa)

                    # Intervalos da legenda
                    minimo = float(valores_mapa.min())
                    maximo = float(valores_mapa.max())

                    if minimo == maximo:
                        limite_inferior = min(0.0, minimo)
                        limite_superior = (
                            maximo * 1.01
                            if maximo > 0
                            else 1.0
                        )
                        bins_mapa = [
                            limite_inferior,
                            limite_superior
                        ]
                    else:
                        bins_mapa = sorted(set(
                            [minimo]
                            + [
                                float(v)
                                for v in valores_mapa.quantile(
                                    [0.25, 0.50, 0.75]
                                ).tolist()
                            ]
                            + [maximo]
                        ))

                    # Camada temática
                    camada_mapa = folium.Choropleth(
                        geo_data=gdf_map.to_json(),
                        data=dados_choropleth,
                        columns=["code_muni", "_value"],
                        key_on="feature.properties.code_muni",
                        fill_color="YlGn",
                        fill_opacity=0.80,
                        line_opacity=0.50,
                        legend_name=None,
                        nan_fill_color="#eeeeee",
                        nan_fill_opacity=0.6,
                        bins=bins_mapa
                    )

                    

                    camada_mapa.add_to(m_mapa)

                    # Oculta somente a legenda automática do Folium
                    estilo_legenda = """
                    <style>
                    #legend,
                    .legend {
                        display: none !important;
                    }
                    </style>
                    """

                    m_mapa.get_root().html.add_child(
                        Element(estilo_legenda)
                    )

                    # Legenda personalizada com intervalos espaçados
                    rotulos_legenda = [
                        f"{v:,.0f}".replace(",", ".")
                        for v in bins_mapa
                    ]

                    valores_html = "".join(
                        f"<span>{v}</span>"
                        for v in rotulos_legenda
                    )

                    legenda_html = f"""
                    <style>
                    .legenda-producao {{
                        position: fixed;
                        bottom: 35px;
                        right: 35px;
                        z-index: 99999;
                        background: white;
                        padding: 14px 18px;
                        border-radius: 8px;
                        box-shadow: 0 2px 8px #999;
                        width: 440px;
                        font-family: Arial;
                    }}
                    .legenda-producao .titulo {{
                        font-size: 13px;
                        font-weight: bold;
                        margin-bottom: 12px;
                    }}
                    .legenda-producao .faixa {{
                        height: 15px;
                        border-radius: 4px;
                        background: linear-gradient(
                            to right,
                            #ffffe5,
                            #f7fcb9,
                            #d9f0a3,
                            #addd8e,
                            #78c679,
                            #31a354,
                            #006837
                        );
                    }}
                    .legenda-producao .valores {{
                        display: flex;
                        justify-content: space-between;
                        gap: 12px;
                        margin-top: 10px;
                        font-size: 11px;
                        white-space: nowrap;
                    }}
                    </style>

                    <div class="legenda-producao">
                        <div class="titulo">
                            Produção de {cultura_comparacao} (toneladas)
                        </div>
                        <div class="faixa"></div>
                        <div class="valores">
                            {valores_html}
                        </div>
                    </div>
                    """

                    m_mapa.get_root().html.add_child(
                        Element(legenda_html)
                    )
          
                    # Identificação dos municípios
                    folium.GeoJson(
                        gdf_map,
                        tooltip=folium.GeoJsonTooltip(
                            fields=["name_muni", "_value"],
                            aliases=[
                                "Município:",
                                "Produção (toneladas):"
                            ],
                            localize=True,
                            sticky=True
                        ),
                        
                style_function=lambda feature: {
                    "fill": True,
                    "fillColor": "#ffffff",
                    "fillOpacity": 0.001,
                    "color": "#ffffff",
                    "opacity": 0,
                    "weight": 0
                },

                    ).add_to(m_mapa)

                    # Exibição no Streamlit
                    st_folium(
                        m_mapa,
                        height=550,
                        use_container_width=True,
                        returned_objects=[],
                        key="mapa_producao_agricola"
                    )

                    st.caption(
                        "Passe o cursor sobre cada município para "
                        "consultar sua produção. Áreas em cinza "
                        "indicam ausência de dados para a cultura."
                    )

            except Exception as erro_mapa:
                st.error(
                    f"Erro ao construir o mapa agrícola: {erro_mapa}"
                )

            # ------------------------------------------------
            # Participação por tipo de lavoura
            # ------------------------------------------------

            st.markdown("#### Participação por tipo de lavoura")

            participacao = (
                dados.groupby("tipo_lavoura")["quantidade_t"]
                .sum()
                .reset_index()
            )

            fig_tipo = px.pie(
                participacao,
                names="tipo_lavoura",
                values="quantidade_t",
                title="Produção: lavouras temporárias e permanentes",
                hole=0.45
            )

            st.plotly_chart(
                fig_tipo,
                use_container_width=True
            )

            # ------------------------------------------------
            # Tabela detalhada
            # ------------------------------------------------

            st.markdown("#### Dados detalhados da produção")

            colunas_exibicao = [
                "municipio",
                "ano",
                "tipo_lavoura",
                "cultura",
                "area_plantada_ha",
                "area_destinada_colheita_ha",
                "area_colhida_ha",
                "quantidade_t",
                "produtividade_kg_ha",
                "valor_producao_mil_reais"
            ]

            colunas_exibicao = [
                c for c in colunas_exibicao
                if c in dados.columns
            ]

            st.dataframe(
                dados[colunas_exibicao].sort_values(
                    ["municipio", "cultura"]
                ),
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                "Baixar dados filtrados em CSV",
                data=dados[colunas_exibicao].to_csv(
                    index=False,
                    sep=";",
                    decimal=",",
                    encoding="utf-8-sig"
                ),
                file_name="producao_agricola_filtrada.csv",
                mime="text/csv"
            )


# ============================================================
# AGRICULTURA FAMILIAR
# ============================================================


with tab_family:

    st.markdown("### Agricultura familiar")

    if familiar.empty:

        st.info(
            "Nao ha dados de agricultura familiar para os municipios selecionados."
        )

    else:

        ranking = familiar.copy()

        ranking["estabelecimentos"] = pd.to_numeric(
            ranking["estabelecimentos"],
            errors="coerce"
        )

        ranking = ranking.dropna(
            subset=["estabelecimentos"]
        )

        if ranking.empty:

            st.warning(
                "Nao foram encontrados valores validos de estabelecimentos."
            )

        else:

            total_estabelecimentos = ranking[
                "estabelecimentos"
            ].sum()

            municipios_com_dados = ranking[
                "municipio"
            ].nunique()

            anos_referencia = sorted(
                pd.to_numeric(
                    ranking["ano"],
                    errors="coerce"
                ).dropna().astype(int).unique()
            )

            ano_referencia = ", ".join(
                str(ano) for ano in anos_referencia
            )

            a, b, c = st.columns(3)

            a.metric(
                "Estabelecimentos familiares",
                f"{total_estabelecimentos:,.0f}".replace(",", ".")
            )

            b.metric(
                "Municipios com dados",
                f"{municipios_com_dados}"
            )

            c.metric(
                "Ano de referencia",
                ano_referencia if ano_referencia else "Nao informado"
            )

            st.divider()

            st.markdown("#### Ranking municipal")

            ranking_grafico = ranking.sort_values(
                "estabelecimentos",
                ascending=True
            )

            fig_familiar = px.bar(
                ranking_grafico,
                x="estabelecimentos",
                y="municipio",
                orientation="h",
                text="estabelecimentos",
                title="Estabelecimentos da agricultura familiar por municipio"
            )

            fig_familiar.update_traces(
                texttemplate="%{text:,.0f}",
                textposition="outside",
                cliponaxis=False
            )

            fig_familiar.update_layout(
                xaxis_title="Numero de estabelecimentos",
                yaxis_title="",
                height=650,
                margin=dict(
                    l=20,
                    r=60,
                    t=60,
                    b=40
                )
            )

            st.plotly_chart(
                fig_familiar,
                use_container_width=True
            )

            st.divider()

            st.markdown("#### Dados por municipio")

            tabela_familiar = ranking.sort_values(
                "estabelecimentos",
                ascending=False
            )[
                [
                    "municipio",
                    "ano",
                    "estabelecimentos"
                ]
            ].copy()

            st.dataframe(
                tabela_familiar,
                use_container_width=True,
                hide_index=True
            )

            st.caption(
                "Fonte: IBGE, Censo Agropecuario 2017, SIDRA, tabela 6778. "
                "Os dados apresentados representam estabelecimentos "
                "classificados como agricultura familiar."
            )

            st.info(
                "Os numeros de agricultores individuais e a area total "
                "da agricultura familiar nao estao disponiveis nesta "
                "extracao e, por isso, nao sao apresentados."
            )

            # ------------------------------------------------
            # PARTICIPACAO PERCENTUAL DA AGRICULTURA FAMILIAR
            # ------------------------------------------------

            ranking_percentual = ranking.copy()

            ranking_percentual["total_estabelecimentos"] = (
                pd.to_numeric(
                    ranking_percentual["total_estabelecimentos"],
                    errors="coerce"
                )
            )

            ranking_percentual["participacao_percentual"] = (
                pd.to_numeric(
                    ranking_percentual["participacao_percentual"],
                    errors="coerce"
                )
            )

            ranking_percentual = ranking_percentual.dropna(
                subset=[
                    "estabelecimentos",
                    "total_estabelecimentos",
                    "participacao_percentual"
                ]
            )

            ranking_percentual = ranking_percentual[
                ranking_percentual["total_estabelecimentos"] > 0
            ].copy()

            if not ranking_percentual.empty:

                total_familiar_regional = (
                    ranking_percentual["estabelecimentos"].sum()
                )

                total_agropecuario_regional = (
                    ranking_percentual["total_estabelecimentos"].sum()
                )

                participacao_regional = (
                    total_familiar_regional
                    / total_agropecuario_regional
                    * 100
                )

                st.divider()

                st.markdown(
                    "#### Participacao da agricultura familiar"
                )

                a, b, c = st.columns(3)

                a.metric(
                    "Participacao regional",
                    f"{participacao_regional:.2f}%".replace(".", ",")
                )

                b.metric(
                    "Estabelecimentos familiares",
                    f"{total_familiar_regional:,.0f}".replace(",", ".")
                )

                c.metric(
                    "Total agropecuario",
                    f"{total_agropecuario_regional:,.0f}".replace(",", ".")
                )

                st.markdown("##### Ranking percentual por municipio")

                ranking_percentual_grafico = (
                    ranking_percentual.sort_values(
                        "participacao_percentual",
                        ascending=True
                    )
                )

                fig_participacao = px.bar(
                    ranking_percentual_grafico,
                    x="participacao_percentual",
                    y="municipio",
                    orientation="h",
                    text="participacao_percentual",
                    title=(
                        "Participacao da agricultura familiar "
                        "nos estabelecimentos agropecuarios (%)"
                    ),
                    range_x=[0, 100]
                )

                fig_participacao.update_traces(
                    texttemplate="%{text:.1f}%",
                    textposition="outside",
                    cliponaxis=False
                )

                fig_participacao.update_layout(
                    xaxis_title="Participacao (%)",
                    yaxis_title="",
                    height=650,
                    margin=dict(
                        l=20,
                        r=70,
                        t=60,
                        b=40
                    )
                )

                st.plotly_chart(
                    fig_participacao,
                    use_container_width=True
                )

                st.markdown("##### Indicadores por municipio")

                tabela_participacao = (
                    ranking_percentual[
                        [
                            "municipio",
                            "estabelecimentos",
                            "total_estabelecimentos",
                            "participacao_percentual"
                        ]
                    ]
                    .sort_values(
                        "participacao_percentual",
                        ascending=False
                    )
                    .copy()
                )

                tabela_participacao = (
                    tabela_participacao.rename(
                        columns={
                            "municipio": "Municipio",
                            "estabelecimentos": "Estabelecimentos familiares",
                            "total_estabelecimentos": "Total agropecuario",
                            "participacao_percentual": "Participacao (%)"
                        }
                    )
                )

                tabela_participacao["Participacao (%)"] = (
                    tabela_participacao["Participacao (%)"].round(2)
                )

                st.dataframe(
                    tabela_participacao,
                    use_container_width=True,
                    hide_index=True
                )



    # --------------------------------------------------------
    # MAPA TEMATICO DA AGRICULTURA FAMILIAR
    # --------------------------------------------------------

    st.divider()

    st.markdown("#### Mapa tematico da agricultura familiar")

    st.caption(
        "Distribuicao territorial dos estabelecimentos "
        "da agricultura familiar em 2017."
    )

    try:

        # Carrega os limites geograficos
        gdf_map = regional_geometry(municipios)

        # Prepara os dados familiares
        dados_mapa_familiar = familiar.copy()

        dados_mapa_familiar["codigo_ibge"] = (
            dados_mapa_familiar["codigo_ibge"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )

        dados_mapa_familiar["estabelecimentos"] = pd.to_numeric(
            dados_mapa_familiar["estabelecimentos"],
            errors="coerce"
        )

        # Agrupa os estabelecimentos por municipio
        dados_mapa_familiar = (
            dados_mapa_familiar
            .groupby("codigo_ibge")["estabelecimentos"]
            .sum(min_count=1)
            .reset_index(name="_value")
        )

        # Padroniza os codigos da geometria
        gdf_map["code_muni"] = (
            gdf_map["code_muni"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )

        # Mantem somente municipios com dados
        codigos_selecionados = set(
            dados_mapa_familiar["codigo_ibge"]
        )

        gdf_map = gdf_map[
            gdf_map["code_muni"].isin(codigos_selecionados)
        ].copy()

        # Combina os dados com os limites municipais
        gdf_map = gdf_map.merge(
            dados_mapa_familiar,
            left_on="code_muni",
            right_on="codigo_ibge",
            how="left"
        )

        gdf_map["_value"] = pd.to_numeric(
            gdf_map["_value"],
            errors="coerce"
        ).astype("float64")

        valores_mapa = gdf_map["_value"].dropna()

        if gdf_map.empty:

            st.warning(
                "Nao ha municipios para exibir no mapa."
            )

        elif valores_mapa.empty:

            st.warning(
                "Nao ha valores de estabelecimentos para o mapa."
            )

        else:

            # Centro geografico
            geometria_unida = gdf_map.geometry.unary_union
            centroide = geometria_unida.centroid

            centro_mapa = [
                centroide.y,
                centroide.x
            ]

            # Cria o mapa
            m_familiar = folium.Map(
                location=centro_mapa,
                zoom_start=8,
                tiles=None,
                zoom_control=True,
                control_scale=False,
                prefer_canvas=True
            )

            # Tela cheia
            Fullscreen(
                position="topright",
                title="Expandir mapa",
                title_cancel="Sair da tela cheia",
                force_separate_button=True
            ).add_to(m_familiar)

            # Calcula os intervalos da legenda
            minimo = float(valores_mapa.min())
            maximo = float(valores_mapa.max())

            if minimo == maximo:

                limite_inferior = min(0.0, minimo)

                limite_superior = (
                    maximo * 1.01
                    if maximo > 0
                    else 1.0
                )

                bins_familiar = [
                    limite_inferior,
                    limite_superior
                ]

            else:

                bins_familiar = sorted(set(
                    [minimo]
                    + [
                        float(v)
                        for v in valores_mapa.quantile(
                            [0.25, 0.50, 0.75]
                        ).tolist()
                    ]
                    + [maximo]
                ))

            # Camada tematica
            camada_familiar = folium.Choropleth(
                geo_data=gdf_map.to_json(),
                data=gdf_map[
                    ["code_muni", "_value"]
                ],
                columns=["code_muni", "_value"],
                key_on="feature.properties.code_muni",
                fill_color="YlGn",
                fill_opacity=0.80,
                line_opacity=0.50,
                legend_name=None,
                nan_fill_color="#eeeeee",
                nan_fill_opacity=0.6,
                bins=bins_familiar
            )

            camada_familiar.add_to(m_familiar)

            # Oculta a legenda automatica do Folium
            estilo_legenda = """
            <style>
            #legend,
            .legend {
                display: none !important;
            }
            </style>
            """

            m_familiar.get_root().html.add_child(
                Element(estilo_legenda)
            )

            # Legenda personalizada
            rotulos_legenda = [
                f"{v:,.0f}".replace(",", ".")
                for v in bins_familiar
            ]

            valores_html = "".join(
                f"<span>{v}</span>"
                for v in rotulos_legenda
            )

            legenda_html = f"""
            <style>
            .legenda-familiar {{
                position: fixed;
                bottom: 35px;
                right: 35px;
                z-index: 99999;
                background: white;
                padding: 14px 18px;
                border-radius: 8px;
                box-shadow: 0 2px 8px #999;
                width: 440px;
                font-family: Arial;
            }}

            .legenda-familiar .titulo {{
                font-size: 13px;
                font-weight: bold;
                margin-bottom: 12px;
            }}

            .legenda-familiar .faixa {{
                height: 15px;
                border-radius: 4px;
                background: linear-gradient(
                    to right,
                    #ffffe5,
                    #f7fcb9,
                    #d9f0a3,
                    #addd8e,
                    #78c679,
                    #31a354,
                    #006837
                );
            }}

            .legenda-familiar .valores {{
                display: flex;
                justify-content: space-between;
                gap: 12px;
                margin-top: 10px;
                font-size: 11px;
                white-space: nowrap;
            }}
            </style>

            <div class="legenda-familiar">
                <div class="titulo">
                    Estabelecimentos da agricultura familiar
                </div>
                <div class="faixa"></div>
                <div class="valores">
                    {valores_html}
                </div>
            </div>
            """

            m_familiar.get_root().html.add_child(
                Element(legenda_html)
            )

            # Identificacao dos municipios
            folium.GeoJson(
                gdf_map,
                tooltip=folium.GeoJsonTooltip(
                    fields=["name_muni", "_value"],
                    aliases=[
                        "Municipio:",
                        "Estabelecimentos familiares:"
                    ],
                    localize=True,
                    sticky=True
                ),
                style_function=lambda feature: {
                    "color": "#2878b5",
                    "weight": 1.5,
                    "fillOpacity": 0
                }
            ).add_to(m_familiar)

            # Exibe o mapa
            st_folium(
                m_familiar,
                height=550,
                use_container_width=True,
                returned_objects=[],
                key="mapa_agricultura_familiar"
            )

            st.caption(
                "Fonte: IBGE, Censo Agropecuario 2017, SIDRA, "
                "tabela 6778. Passe o cursor sobre os municipios "
                "para consultar os estabelecimentos familiares."
            )

    except Exception as erro_mapa:

        st.error(
            f"Erro ao construir o mapa da agricultura familiar: {erro_mapa}"
        )

    # --------------------------------------------------------
    # MAPA DA PARTICIPACAO PERCENTUAL DA AGRICULTURA FAMILIAR
    # --------------------------------------------------------

    st.divider()

    st.markdown(
        "#### Mapa percentual da agricultura familiar"
    )

    st.caption(
        "Participacao dos estabelecimentos familiares "
        "no total de estabelecimentos agropecuarios, em 2017."
    )

    try:

        dados_percentual_mapa = familiar.copy()

        dados_percentual_mapa["codigo_ibge"] = (
            dados_percentual_mapa["codigo_ibge"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )

        dados_percentual_mapa["participacao_percentual"] = (
            pd.to_numeric(
                dados_percentual_mapa["participacao_percentual"],
                errors="coerce"
            )
        )

        dados_percentual_mapa = (
            dados_percentual_mapa
            .dropna(subset=["participacao_percentual"])
            .groupby("codigo_ibge")["participacao_percentual"]
            .mean()
            .reset_index(name="_value")
        )

        gdf_percentual = regional_geometry(municipios)

        gdf_percentual["code_muni"] = (
            gdf_percentual["code_muni"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )

        codigos_percentual = set(
            dados_percentual_mapa["codigo_ibge"]
        )

        gdf_percentual = gdf_percentual[
            gdf_percentual["code_muni"].isin(
                codigos_percentual
            )
        ].copy()

        gdf_percentual = gdf_percentual.merge(
            dados_percentual_mapa,
            left_on="code_muni",
            right_on="codigo_ibge",
            how="left"
        )

        gdf_percentual["_value"] = pd.to_numeric(
            gdf_percentual["_value"],
            errors="coerce"
        ).astype("float64")

        valores_percentual = (
            gdf_percentual["_value"].dropna()
        )

        if gdf_percentual.empty or valores_percentual.empty:

            st.warning(
                "Nao existem dados suficientes para construir "
                "o mapa percentual."
            )

        else:

            geometria_unida = (
                gdf_percentual.geometry.unary_union
            )

            centroide = geometria_unida.centroid

            centro_mapa_percentual = [
                centroide.y,
                centroide.x
            ]

            m_percentual = folium.Map(
                location=centro_mapa_percentual,
                zoom_start=8,
                tiles=None,
                zoom_control=True,
                control_scale=False,
                prefer_canvas=True
            )

            Fullscreen(
                position="topright",
                title="Expandir mapa",
                title_cancel="Sair da tela cheia",
                force_separate_button=True
            ).add_to(m_percentual)

            bins_percentual = [
                0, 20, 40, 60, 80, 100
            ]

            camada_percentual = folium.Choropleth(
                geo_data=gdf_percentual.to_json(),
                data=gdf_percentual[
                    ["code_muni", "_value"]
                ],
                columns=["code_muni", "_value"],
                key_on="feature.properties.code_muni",
                fill_color="YlGn",
                fill_opacity=0.80,
                line_opacity=0.50,
                legend_name=None,
                nan_fill_color="#eeeeee",
                nan_fill_opacity=0.6,
                bins=bins_percentual
            )

            camada_percentual.add_to(m_percentual)

            estilo_legenda_percentual = """
            <style>
            #legend,
            .legend {
                display: none !important;
            }
            </style>
            """

            m_percentual.get_root().html.add_child(
                Element(estilo_legenda_percentual)
            )

            legenda_percentual = """
            <style>
            .legenda-percentual {
                position: fixed;
                bottom: 35px;
                right: 35px;
                z-index: 99999;
                background: white;
                padding: 14px 18px;
                border-radius: 8px;
                box-shadow: 0 2px 8px #999;
                width: 340px;
                font-family: Arial;
            }

            .legenda-percentual .titulo {
                font-size: 13px;
                font-weight: bold;
                margin-bottom: 12px;
            }

            .legenda-percentual .faixa {
                height: 15px;
                border-radius: 4px;
                background: linear-gradient(
                    to right,
                    #ffffe5,
                    #f7fcb9,
                    #d9f0a3,
                    #addd8e,
                    #78c679,
                    #31a354,
                    #006837
                );
            }

            .legenda-percentual .valores {
                display: flex;
                justify-content: space-between;
                margin-top: 10px;
                font-size: 11px;
            }
            </style>

            <div class="legenda-percentual">
                <div class="titulo">
                    Participacao da agricultura familiar (%)
                </div>
                <div class="faixa"></div>
                <div class="valores">
                    <span>0%</span>
                    <span>20%</span>
                    <span>40%</span>
                    <span>60%</span>
                    <span>80%</span>
                    <span>100%</span>
                </div>
            </div>
            """

            m_percentual.get_root().html.add_child(
                Element(legenda_percentual)
            )

            folium.GeoJson(
                gdf_percentual,
                tooltip=folium.GeoJsonTooltip(
                    fields=["name_muni", "_value"],
                    aliases=[
                        "Municipio:",
                        "Participacao familiar (%):"
                    ],
                    localize=True,
                    sticky=True
                ),
                style_function=lambda feature: {
                    "color": "#2878b5",
                    "weight": 1.5,
                    "fillOpacity": 0
                }
            ).add_to(m_percentual)

            st_folium(
                m_percentual,
                height=550,
                use_container_width=True,
                returned_objects=[],
                key="mapa_percentual_agricultura_familiar"
            )

            st.caption(
                "Fonte: IBGE, Censo Agropecuario 2017, SIDRA, "
                "tabela 6778. Percentual calculado pela razao "
                "entre estabelecimentos familiares e o total "
                "de estabelecimentos agropecuarios."
            )

    except Exception as erro_percentual:

        st.error(
            "Erro ao construir o mapa percentual: "
            f"{erro_percentual}"
        )


# ============================================================
# PECUÁRIA
# ============================================================


with tab_livestock:

    st.markdown("### Pecuária")
    st.caption(
        "Efetivo dos rebanhos nos municípios do Centro-Sul "
        "do Rio Grande do Sul | IBGE – PPM 2025"
    )

    if pecuaria.empty:

        st.info(
            "Não há dados pecuários disponíveis para os filtros selecionados."
        )

    else:

        # ----------------------------------------------------
        # SELEÇÃO DO REBANHO
        # ----------------------------------------------------

        produtos = sorted(
            pecuaria["produto"].dropna().unique().tolist()
        )

        produto_selecionado = st.selectbox(
            "Selecione o tipo de rebanho:",
            produtos,
            key="pecuaria_produto"
        )

        dados_rebanho = pecuaria[
            pecuaria["produto"] == produto_selecionado
        ].copy()

        dados_rebanho["quantidade"] = pd.to_numeric(
            dados_rebanho["quantidade"],
            errors="coerce"
        )

        dados_rebanho = dados_rebanho.dropna(
            subset=["quantidade"]
        )

        if dados_rebanho.empty:

            st.warning(
                "Não existem valores disponíveis para este rebanho."
            )

        else:

            # ------------------------------------------------
            # INDICADORES
            # ------------------------------------------------

            total_rebanho = int(
                dados_rebanho["quantidade"].sum()
            )

            numero_municipios = (
                dados_rebanho["municipio"].nunique()
            )

            maior = dados_rebanho.loc[
                dados_rebanho["quantidade"].idxmax()
            ]

            ano_referencia = int(
                dados_rebanho["ano"].dropna().max()
            )

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "Efetivo informado",
                f"{total_rebanho:,.0f}".replace(",", "."),
                help="Soma dos valores disponíveis para o rebanho selecionado."
            )

            col2.metric(
                "Municípios com dados",
                f"{numero_municipios} / 21"
            )

            col3.metric(
                "Maior efetivo municipal",
                f"{int(maior['quantidade']):,.0f}".replace(",", "."),
                help=maior["municipio"]
            )

            col4.metric(
                "Ano de referência",
                ano_referencia
            )

            st.divider()

            # ------------------------------------------------
            # RANKING MUNICIPAL
            # ------------------------------------------------

            st.markdown("#### Ranking municipal")

            ranking = (
                dados_rebanho
                .groupby("municipio", as_index=False)["quantidade"]
                .sum()
                .sort_values(
                    "quantidade",
                    ascending=False
                )
            )

            ranking["quantidade_formatada"] = (
                ranking["quantidade"]
                .map(lambda x: f"{x:,.0f}".replace(",", "."))
            )

            fig_ranking = px.bar(
                ranking,
                x="quantidade",
                y="municipio",
                orientation="h",
                text="quantidade_formatada",
                title=f"Efetivo de {produto_selecionado} por município",
                labels={
                    "quantidade": "Número de cabeças",
                    "municipio": "Município"
                }
            )

            fig_ranking.update_layout(
                yaxis={"categoryorder": "total ascending"},
                height=650,
                showlegend=False
            )

            fig_ranking.update_traces(
                textposition="outside",
                cliponaxis=False
            )

            st.plotly_chart(
                fig_ranking,
                use_container_width=True
            )

            st.divider()

            # ------------------------------------------------
            # MAPA TEMÁTICO
            # ------------------------------------------------

            st.markdown("#### Distribuição territorial do rebanho")

            gdf_map = regional_geometry(municipios).copy()

            gdf_map["code_muni"] = (
                gdf_map["code_muni"]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
            )

            dados_mapa = (
                dados_rebanho
                .groupby("codigo_ibge", as_index=False)["quantidade"]
                .sum()
            )

            dados_mapa["codigo_ibge"] = (
                dados_mapa["codigo_ibge"]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
            )

            # INTERVALOS DINÂMICOS DA LEGENDA
            valor_maximo = float(
                dados_mapa["quantidade"].max()
            )

            limite_superior = valor_maximo * 1.000001

            bins_mapa = [
                limite_superior * i / 5
                for i in range(6)
            ]

            cores_legenda = [
                "#ffffcc",
                "#c2e699",
                "#78c679",
                "#31a354",
                "#006837"
            ]

            def formatar_efetivo(valor):
                return f"{valor:,.0f}".replace(",", ".")

            m_pecuaria = folium.Map(
                location=[-30.8, -51.8],
                zoom_start=8,
                tiles=None,
                control_scale=True
            )

            camada_pecuaria = folium.Choropleth(
                geo_data=gdf_map.to_json(),
                data=dados_mapa,
                columns=["codigo_ibge", "quantidade"],
                key_on="feature.properties.code_muni",
                fill_color="YlGn",
                fill_opacity=0.80,
                line_opacity=0.50,
                legend_name=None,
                nan_fill_color="#eeeeee",
                nan_fill_opacity=0.6,
                bins=bins_mapa
            )

            camada_pecuaria.add_to(m_pecuaria)

            # ------------------------------------------------
            # TOOLTIP COM DADOS DO MUNICÍPIO
            # ------------------------------------------------

            dados_tooltip = dados_mapa.copy()

            dados_tooltip["quantidade_formatada"] = (
                dados_tooltip["quantidade"]
                .map(lambda x: f"{x:,.0f}".replace(",", "."))
            )

            gdf_tooltip = gdf_map.merge(
                dados_tooltip,
                left_on="code_muni",
                right_on="codigo_ibge",
                how="left"
            )

            gdf_tooltip["efetivo_exibido"] = (
                gdf_tooltip["quantidade_formatada"]
                .fillna("Sem dado disponível")
            )

            folium.GeoJson(
                gdf_tooltip.to_json(),
                name="Informações dos municípios",
                style_function=lambda feature: {
                    "fillOpacity": 0,
                    "color": "transparent",
                    "weight": 0
                },
                highlight_function=lambda feature: {
                    "weight": 3,
                    "color": "#222222",
                    "fillOpacity": 0.15
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=[
                        "name_muni",
                        "efetivo_exibido"
                    ],
                    aliases=[
                        "Município:",
                        "Efetivo:"
                    ],
                    localize=True,
                    sticky=True,
                    labels=True
                )
            ).add_to(m_pecuaria)

            # Ocultar legenda automática do Folium
            estilo_legenda_pecuaria = """
            <style>
            #legend,
            .legend {
                display: none !important;
            }
            </style>
            """

            m_pecuaria.get_root().html.add_child(
                Element(estilo_legenda_pecuaria)
            )

            # LEGENDA TEMÁTICA PERSONALIZADA
            itens_legenda = ""

            for i in range(5):
                inferior = bins_mapa[i]
                superior = bins_mapa[i + 1]

                itens_legenda += f"""
                <div style="
                    display:flex;
                    align-items:center;
                    margin:5px 0;
                    gap:8px;
                ">
                    <span style="
                        display:inline-block;
                        width:22px;
                        height:15px;
                        background:{cores_legenda[i]};
                        border:1px solid #888;
                    "></span>
                    <span>
                        {formatar_efetivo(inferior)}
                        – {formatar_efetivo(superior)}
                    </span>
                </div>
                """

            legenda_html = f"""
            <div style="
                position: fixed;
                bottom: 100px;
                left: 15px;
                z-index: 9999;
                background: white;
                padding: 12px 15px;
                border: 1px solid #888;
                border-radius: 6px;
                box-shadow: 0 1px 5px rgba(0,0,0,0.3);
                font-size: 12px;
                color: #222;
                min-width: 190px;
            ">
                <div style="
                    font-weight:bold;
                    margin-bottom:8px;
                    font-size:13px;
                ">
                    Efetivo – {produto_selecionado}
                </div>

                {itens_legenda}

                <div style="
                    display:flex;
                    align-items:center;
                    gap:8px;
                    margin-top:7px;
                ">
                    <span style="
                        display:inline-block;
                        width:22px;
                        height:15px;
                        background:#eeeeee;
                        border:1px solid #888;
                    "></span>
                    <span>Sem dado disponível</span>
                </div>
            </div>
            """

            m_pecuaria.get_root().html.add_child(
                Element(legenda_html)
            )


            Fullscreen(
                position="topright",
                title="Expandir mapa",
                title_cancel="Sair da tela cheia",
                force_separate_button=True
            ).add_to(m_pecuaria)

            st_folium(
                m_pecuaria,
                width=None,
                height=600,
                key="mapa_pecuaria"
            )

            st.caption(
                "Escala de cores: tons mais claros representam "
                "menores efetivos e tons mais escuros representam "
                "maiores efetivos. Cinza representa ausência de dado."
            )

            st.divider()

            # ------------------------------------------------
            # TABELA DETALHADA
            # ------------------------------------------------

            st.markdown("#### Dados pecuários por município")

            tabela_pecuaria = dados_rebanho[
                [
                    "ano",
                    "municipio",
                    "produto",
                    "quantidade",
                    "unidade"
                ]
            ].sort_values(
                "quantidade",
                ascending=False
            )

            st.dataframe(
                tabela_pecuaria,
                use_container_width=True,
                hide_index=True
            )

            st.caption(
                "Fonte: IBGE – Pesquisa da Pecuária Municipal (PPM), "
                "SIDRA, Tabela 3939, ano de referência 2025. "
                "Ausência de registro não significa necessariamente "
                "efetivo igual a zero."
            )


# ============================================================
# USO E COBERTURA DO SOLO
# ============================================================


with tab_land:

    st.markdown("### Uso e cobertura do solo")
    st.caption(
        "Fonte: MapBiomas Collection 11 | Municípios do Centro-Sul do RS | 1985–2025"
    )

    if solo.empty:

        st.info("Não há dados de uso e cobertura do solo disponíveis.")

    else:

        # Preparação dos dados
        solo = solo.copy()
        solo["ano"] = pd.to_numeric(solo["ano"], errors="coerce")
        solo["area_ha"] = pd.to_numeric(solo["area_ha"], errors="coerce")
        solo = solo.dropna(subset=["ano", "area_ha", "classe", "municipio"])

        anos_solo = sorted(solo["ano"].astype(int).unique().tolist())

        # Seleção do ano
        ano_selecionado = st.selectbox(
            "Ano de referência",
            anos_solo,
            index=len(anos_solo) - 1,
            key="ano_uso_solo"
        )

        dados_ano = solo[solo["ano"] == ano_selecionado].copy()

        # Classificação temática das áreas
        classes = dados_ano["classe"].astype(str)

        vegetacao = dados_ano[
            classes.str.startswith(("1.", "2."))
        ]["area_ha"].sum()

        lavouras_pastagens = dados_ano[
            classes.str.startswith(("3.1.", "3.2."))
        ]["area_ha"].sum()

        silvicultura = dados_ano[
            classes.str.startswith("3.3.")
        ]["area_ha"].sum()

        area_urbanizada = dados_ano[
            classes.str.startswith("4.2.")
        ]["area_ha"].sum()

        area_total = dados_ano["area_ha"].sum()

        # Indicadores regionais
        st.markdown("#### Indicadores territoriais")

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric(
            "Área total mapeada",
            f"{area_total:,.0f} ha"
        )

        c2.metric(
            "Vegetação e formações naturais",
            f"{vegetacao:,.0f} ha"
        )

        c3.metric(
            "Lavouras e pastagens",
            f"{lavouras_pastagens:,.0f} ha"
        )

        c4.metric(
            "Silvicultura",
            f"{silvicultura:,.0f} ha"
        )

        c5.metric(
            "Área urbanizada",
            f"{area_urbanizada:,.0f} ha"
        )

        st.divider()

        # Seleção de classe
        st.markdown("#### Análise por classe de uso e cobertura")

        classes_disponiveis = sorted(
            dados_ano["classe"].dropna().unique().tolist()
        )

        classe_selecionada = st.selectbox(
            "Selecione uma classe",
            classes_disponiveis,
            key="classe_uso_solo"
        )

        dados_classe = dados_ano[
            dados_ano["classe"] == classe_selecionada
        ].copy()

        # Dados da classe organizados por código IBGE
        # Utilizados nos mapas temáticos

        dados_mapa = (
            dados_classe.groupby(
                "codigo_ibge",
                as_index=False
            )["area_ha"]
            .sum()
        )

        dados_mapa["codigo_ibge"] = (
            dados_mapa["codigo_ibge"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )

        dados_mapa["area_ha"] = pd.to_numeric(
            dados_mapa["area_ha"],
            errors="coerce"
        )


        ranking_classe = (
            dados_classe.groupby("municipio")["area_ha"]
            .sum()
            .reset_index()
            .sort_values("area_ha", ascending=True)
        )

        st.plotly_chart(
            px.bar(
                ranking_classe,
                x="area_ha",
                y="municipio",
                orientation="h",
                title=f"Distribuição municipal: {classe_selecionada}",
                labels={
                    "area_ha": "Área (ha)",
                    "municipio": "Município"
                }
            ),
            use_container_width=True
        )

        st.divider()

        # Ranking de área total por município
        st.markdown("#### Ranking municipal — área total mapeada")

        ranking_municipal = (
            dados_ano.groupby("municipio")["area_ha"]
            .sum()
            .reset_index()
            .sort_values("area_ha", ascending=True)
        )

        st.plotly_chart(
            px.bar(
                ranking_municipal,
                x="area_ha",
                y="municipio",
                orientation="h",
                title=f"Área total por município em {ano_selecionado}",
                labels={
                    "area_ha": "Área (ha)",
                    "municipio": "Município"
                }
            ),
            use_container_width=True
        )

        # ----------------------------------------------------
        # MAPA PERCENTUAL DA ÁREA MUNICIPAL
        # ----------------------------------------------------

        st.divider()
        st.markdown("#### Mapa percentual por município")

        st.caption(
            f"Percentual do território municipal ocupado por "
            f"{classe_selecionada} — {ano_selecionado}"
        )

        if dados_mapa.empty:

            st.warning(
                "Não há dados disponíveis para calcular os percentuais."
            )

        else:

            # Calcular a área territorial de cada município
            # EPSG 5880: projeção adequada para cálculo de áreas no Brasil

            gdf_area = gdf_map.to_crs(epsg=5880).copy()

            gdf_area["area_municipio_ha"] = (
                gdf_area.geometry.area / 10000
            )

            # Associar área da classe à área total municipal

            dados_percentual = gdf_area[
                ["code_muni", "name_muni", "area_municipio_ha"]
            ].merge(
                dados_mapa,
                left_on="code_muni",
                right_on="codigo_ibge",
                how="left"
            )

            dados_percentual["area_ha"] = (
                dados_percentual["area_ha"].fillna(0)
            )

            # Calcular participação percentual

            dados_percentual["percentual"] = (
                dados_percentual["area_ha"]
                / dados_percentual["area_municipio_ha"]
            ) * 100

            dados_percentual["percentual"] = (
                dados_percentual["percentual"].fillna(0)
            )

            
            valor_maximo_pct = float(
                dados_percentual["percentual"].max()
            )

            if valor_maximo_pct <= 0:

                st.warning(
                    "Não há valores positivos para representar no mapa."
                )

            else:

                # Escala fixa de 0 a 100%

                bins_pct = [
                    0, 20, 40, 60, 80, 100
                ]


                cores_pct = [
                    "#ffffcc",
                    "#c2e699",
                    "#78c679",
                    "#31a354",
                    "#006837"
                ]

                def formatar_numero_pct(valor):
                    return f"{valor:,.2f}".replace(
                        ",", "X"
                    ).replace(".", ",").replace("X", ".")

                # Preparar dados do mapa

                dados_mapa_pct = dados_percentual[
                    ["code_muni", "percentual"]
                ].copy()

                # Construir mapa

                m_pct = folium.Map(
                    location=[-30.8, -51.8],
                    zoom_start=8,
                    tiles=None,
                    control_scale=True
                )

                camada_pct = folium.Choropleth(
                    geo_data=gdf_map.to_json(),
                    data=dados_mapa_pct,
                    columns=["code_muni", "percentual"],
                    key_on="feature.properties.code_muni",
                    fill_color="YlGn",
                    fill_opacity=0.80,
                    line_opacity=0.50,
                    legend_name=None,
                    nan_fill_color="#eeeeee",
                    nan_fill_opacity=0.6,
                    bins=bins_pct
                )

                camada_pct.add_to(m_pct)

                # Preparar informações para o tooltip

                dados_tooltip_pct = dados_percentual.copy()

                dados_tooltip_pct["percentual_exibido"] = (
                    dados_tooltip_pct["percentual"]
                    .map(formatar_numero_pct)
                    .astype(str) + "%"
                )

                dados_tooltip_pct["area_exibida"] = (
                    dados_tooltip_pct["area_ha"]
                    .map(formatar_numero_pct)
                )

                gdf_tooltip_pct = gdf_map.merge(
                    dados_tooltip_pct[
                        [
                            "code_muni",
                            "area_municipio_ha",
                            "area_exibida",
                            "percentual_exibido"
                        ]
                    ],
                    on="code_muni",
                    how="left"
                )

                gdf_tooltip_pct["area_total_exibida"] = (
                    gdf_tooltip_pct["area_municipio_ha"]
                    .map(formatar_numero_pct)
                )

                folium.GeoJson(
                    gdf_tooltip_pct.to_json(),
                    name="Percentual por município",
                    style_function=lambda feature: {
                        "fillOpacity": 0,
                        "color": "transparent",
                        "weight": 0
                    },
                    highlight_function=lambda feature: {
                        "weight": 3,
                        "color": "#222222",
                        "fillOpacity": 0.15
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=[
                            "name_muni",
                            "area_exibida",
                            "area_total_exibida",
                            "percentual_exibido"
                        ],
                        aliases=[
                            "Município:",
                            "Área da classe (ha):",
                            "Área municipal (ha):",
                            "Participação territorial:"
                        ],
                        localize=True,
                        sticky=True,
                        labels=True
                    )
                ).add_to(m_pct)

                # Ocultar legenda automática

                estilo_legenda_pct = """
                <style>
                #legend,
                .legend {
                    display: none !important;
                }
                </style>
                """

                m_pct.get_root().html.add_child(
                    Element(estilo_legenda_pct)
                )

                # Criar legenda personalizada

                itens_legenda_pct = ""

                for i in range(5):

                    inferior = bins_pct[i]
                    superior = bins_pct[i + 1]

                    itens_legenda_pct += f"""
                    <div style="
                        display:flex;
                        align-items:center;
                        margin:5px 0;
                        gap:8px;
                    ">
                        <span style="
                            display:inline-block;
                            width:22px;
                            height:15px;
                            background:{cores_pct[i]};
                            border:1px solid #888;
                        "></span>
                        <span>
                            {formatar_numero_pct(inferior)}
                            – {formatar_numero_pct(superior)}%
                        </span>
                    </div>
                    """

                legenda_pct = f"""
                <div style="
                    position:fixed;
                    bottom:100px;
                    left:15px;
                    z-index:9999;
                    background:white;
                    padding:12px 15px;
                    border:1px solid #888;
                    border-radius:6px;
                    box-shadow:0 1px 5px rgba(0,0,0,0.3);
                    font-size:12px;
                    color:#222;
                    min-width:210px;
                ">
                    <div style="
                        font-weight:bold;
                        margin-bottom:8px;
                        font-size:13px;
                    ">
                        Participação territorial (%)
                    </div>

                    {itens_legenda_pct}
                </div>
                """

                m_pct.get_root().html.add_child(
                    Element(legenda_pct)
                )

                # Tela cheia

                Fullscreen(
                    position="topright",
                    title="Expandir mapa",
                    title_cancel="Sair da tela cheia",
                    force_separate_button=True
                ).add_to(m_pct)

                # Exibir mapa

                st_folium(
                    m_pct,
                    width=None,
                    height=600,
                    key="mapa_uso_solo_percentual"
                )

                
                st.caption(
                    "O percentual representa a área da classe selecionada "
                    "dividida pela área territorial total do município. "
                    "A escala de cores é fixa, de 0 a 100%."
                )

                # Ranking percentual dos municípios

                st.divider()
                st.markdown(
                    "#### Ranking municipal — participação territorial"
                )

                ranking_percentual = dados_percentual[
                    [
                        "name_muni",
                        "area_ha",
                        "area_municipio_ha",
                        "percentual"
                    ]
                ].copy()

                ranking_percentual = (
                    ranking_percentual
                    .sort_values(
                        "percentual",
                        ascending=False
                    )
                    .reset_index(drop=True)
                )

                ranking_percentual.columns = [
                    "Município",
                    "Área da classe (ha)",
                    "Área municipal (ha)",
                    "Participação (%)"
                ]

                ranking_percentual["Área da classe (ha)"] = (
                    ranking_percentual["Área da classe (ha)"].round(2)
                )

                ranking_percentual["Área municipal (ha)"] = (
                    ranking_percentual["Área municipal (ha)"].round(2)
                )

                ranking_percentual["Participação (%)"] = (
                    ranking_percentual["Participação (%)"].round(2)
                )

                st.dataframe(
                    ranking_percentual,
                    use_container_width=True,
                    hide_index=True
                )


        st.markdown("#### Dados detalhados")

        # ----------------------------------------------------
        # MAPA TEMÁTICO DO MAPBIOMAS
        # ----------------------------------------------------

        st.divider()
        st.markdown("#### Mapa interativo de uso e cobertura do solo")

        st.caption(
            f"Distribuição territorial de {classe_selecionada} "
            f"nos municípios da região — {ano_selecionado}"
        )

        gdf_map = regional_geometry(municipios).copy()

        gdf_map["code_muni"] = (
            gdf_map["code_muni"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )

        dados_mapa = (
            dados_classe.groupby(
                "codigo_ibge",
                as_index=False
            )["area_ha"]
            .sum()
        )

        dados_mapa["codigo_ibge"] = (
            dados_mapa["codigo_ibge"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )

        dados_mapa["area_ha"] = pd.to_numeric(
            dados_mapa["area_ha"],
            errors="coerce"
        )

        dados_mapa = dados_mapa.dropna(
            subset=["area_ha"]
        )

        if dados_mapa.empty or dados_mapa["area_ha"].max() <= 0:

            st.warning(
                "Não há valores positivos disponíveis para "
                "representar esta classe no mapa."
            )

        else:

            # Escala de cinco intervalos
            valor_maximo = float(
                dados_mapa["area_ha"].max()
            )

            limite_superior = valor_maximo * 1.000001

            bins_mapa = [
                limite_superior * i / 5
                for i in range(6)
            ]

            cores_legenda = [
                "#ffffcc",
                "#c2e699",
                "#78c679",
                "#31a354",
                "#006837"
            ]

            def formatar_area_solo(valor):
                return f"{valor:,.2f}".replace(
                    ",", "X"
                ).replace(".", ",").replace("X", ".")

            # Construção do mapa
            m_solo = folium.Map(
                location=[-30.8, -51.8],
                zoom_start=8,
                tiles=None,
                control_scale=True
            )

            camada_solo = folium.Choropleth(
                geo_data=gdf_map.to_json(),
                data=dados_mapa,
                columns=["codigo_ibge", "area_ha"],
                key_on="feature.properties.code_muni",
                fill_color="YlGn",
                fill_opacity=0.80,
                line_opacity=0.50,
                legend_name=None,
                nan_fill_color="#eeeeee",
                nan_fill_opacity=0.6,
                bins=bins_mapa
            )

            camada_solo.add_to(m_solo)

            # Tooltip municipal
            dados_tooltip = dados_mapa.copy()

            dados_tooltip["area_formatada"] = (
                dados_tooltip["area_ha"]
                .map(formatar_area_solo)
            )

            gdf_tooltip = gdf_map.merge(
                dados_tooltip,
                left_on="code_muni",
                right_on="codigo_ibge",
                how="left"
            )

            gdf_tooltip["area_exibida"] = (
                gdf_tooltip["area_formatada"]
                .fillna("Sem dado disponível")
            )

            folium.GeoJson(
                gdf_tooltip.to_json(),
                name="Informações dos municípios",
                style_function=lambda feature: {
                    "fillOpacity": 0,
                    "color": "transparent",
                    "weight": 0
                },
                highlight_function=lambda feature: {
                    "weight": 3,
                    "color": "#222222",
                    "fillOpacity": 0.15
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=[
                        "name_muni",
                        "area_exibida"
                    ],
                    aliases=[
                        "Município:",
                        "Área (ha):"
                    ],
                    localize=True,
                    sticky=True,
                    labels=True
                )
            ).add_to(m_solo)

            # Ocultar legenda automática
            estilo_legenda_solo = """
            <style>
            #legend,
            .legend {
                display: none !important;
            }
            </style>
            """

            m_solo.get_root().html.add_child(
                Element(estilo_legenda_solo)
            )

            # Legenda personalizada
            itens_legenda_solo = ""

            for i in range(5):

                inferior = bins_mapa[i]
                superior = bins_mapa[i + 1]

                itens_legenda_solo += f"""
                <div style="
                    display:flex;
                    align-items:center;
                    margin:5px 0;
                    gap:8px;
                ">
                    <span style="
                        display:inline-block;
                        width:22px;
                        height:15px;
                        background:{cores_legenda[i]};
                        border:1px solid #888;
                    "></span>
                    <span>
                        {formatar_area_solo(inferior)}
                        – {formatar_area_solo(superior)} ha
                    </span>
                </div>
                """

            legenda_html_solo = f"""
            <div style="
                position: fixed;
                bottom: 100px;
                left: 15px;
                z-index: 9999;
                background: white;
                padding: 12px 15px;
                border: 1px solid #888;
                border-radius: 6px;
                box-shadow: 0 1px 5px rgba(0,0,0,0.3);
                font-size: 12px;
                color: #222;
                min-width: 210px;
            ">
                <div style="
                    font-weight:bold;
                    margin-bottom:8px;
                    font-size:13px;
                ">
                    Área — {classe_selecionada}
                </div>

                {itens_legenda_solo}

                <div style="
                    display:flex;
                    align-items:center;
                    gap:8px;
                    margin-top:7px;
                ">
                    <span style="
                        display:inline-block;
                        width:22px;
                        height:15px;
                        background:#eeeeee;
                        border:1px solid #888;
                    "></span>
                    <span>Sem dado disponível</span>
                </div>
            </div>
            """

            m_solo.get_root().html.add_child(
                Element(legenda_html_solo)
            )

            # Tela cheia
            Fullscreen(
                position="topright",
                title="Expandir mapa",
                title_cancel="Sair da tela cheia",
                force_separate_button=True
            ).add_to(m_solo)

            # Exibição
            st_folium(
                m_solo,
                width=None,
                height=600,
                key="mapa_uso_solo"
            )

            st.caption(
                "Tons mais claros representam menores áreas; "
                "tons mais escuros representam maiores áreas. "
                "Cinza representa ausência de dado."
            )



        # ----------------------------------------------------
        # EVOLUÇÃO HISTÓRICA DO USO E COBERTURA DO SOLO
        # ----------------------------------------------------

        st.divider()
        st.markdown("#### Evolução histórica do uso e cobertura do solo")

        st.caption(
            "Série histórica MapBiomas Collection 11 | 1985–2025"
        )

        # Somar a área da classe selecionada em cada ano

        historico_classe = (
            solo[solo["classe"] == classe_selecionada]
            .groupby("ano", as_index=False)["area_ha"]
            .sum()
            .rename(columns={"area_ha": "area_classe_ha"})
        )

        # Calcular a área total mapeada em cada ano

        historico_total = (
            solo.groupby("ano", as_index=False)["area_ha"]
            .sum()
            .rename(columns={"area_ha": "area_total_ha"})
        )

        # Integrar os dois conjuntos de dados

        historico = historico_classe.merge(
            historico_total,
            on="ano",
            how="left"
        )

        historico["participacao_percentual"] = (
            historico["area_classe_ha"]
            / historico["area_total_ha"]
        ) * 100

        historico = historico.sort_values("ano")

        # Indicadores históricos

        if not historico.empty:

            primeiro = historico.iloc[0]
            ultimo = historico.iloc[-1]

            variacao_ha = (
                ultimo["area_classe_ha"]
                - primeiro["area_classe_ha"]
            )

            variacao_pct = (
                (variacao_ha / primeiro["area_classe_ha"]) * 100
                if primeiro["area_classe_ha"] > 0
                else 0
            )

            h1, h2, h3 = st.columns(3)

            h1.metric(
                "Área em 1985",
                f"{primeiro['area_classe_ha']:,.0f} ha"
            )

            h2.metric(
                "Área em 2025",
                f"{ultimo['area_classe_ha']:,.0f} ha"
            )

            h3.metric(
                "Variação da área",
                f"{variacao_pct:+.2f}%",
                delta=f"{variacao_ha:+,.0f} ha"
            )

            st.markdown("##### Evolução da área ocupada")

            fig_historico_area = px.line(
                historico,
                x="ano",
                y="area_classe_ha",
                markers=True,
                title=f"Evolução de {classe_selecionada} — 1985 a 2025",
                labels={
                    "ano": "Ano",
                    "area_classe_ha": "Área (ha)"
                }
            )

            fig_historico_area.update_layout(
                hovermode="x unified",
                xaxis=dict(
                    dtick=5,
                    title="Ano"
                ),
                yaxis_title="Área (ha)"
            )

            st.plotly_chart(
                fig_historico_area,
                use_container_width=True
            )

            st.markdown("##### Participação na área regional")

            fig_historico_pct = px.line(
                historico,
                x="ano",
                y="participacao_percentual",
                markers=True,
                title=f"Participação territorial de {classe_selecionada}",
                labels={
                    "ano": "Ano",
                    "participacao_percentual": "Participação (%)"
                }
            )

            fig_historico_pct.update_layout(
                hovermode="x unified",
                xaxis=dict(
                    dtick=5,
                    title="Ano"
                ),
                yaxis_title="Participação (%)"
            )

            st.plotly_chart(
                fig_historico_pct,
                use_container_width=True
            )

            # Tabela da série histórica

            st.markdown("##### Série histórica detalhada")

            tabela_historica = historico[
                [
                    "ano",
                    "area_classe_ha",
                    "area_total_ha",
                    "participacao_percentual"
                ]
            ].copy()

            tabela_historica.columns = [
                "Ano",
                "Área da classe (ha)",
                "Área regional (ha)",
                "Participação regional (%)"
            ]

            st.dataframe(
                tabela_historica.round(2),
                use_container_width=True,
                hide_index=True
            )
        # ----------------------------------------------------
        # COMPARAÇÃO HISTÓRICA ENTRE MUNICÍPIOS
        # ----------------------------------------------------

        st.divider()

        st.markdown(
            "#### Comparação histórica entre municípios"
        )

        st.caption(
            "Compare a evolução de uma classe de uso e cobertura "
            "do solo em até três municípios, de 1985 a 2025."
        )

        # Carregar a base completa, sem o filtro municipal geral
        solo_comparacao = load_table("solo").copy()

        solo_comparacao["ano"] = pd.to_numeric(
            solo_comparacao["ano"],
            errors="coerce"
        )

        solo_comparacao["area_ha"] = pd.to_numeric(
            solo_comparacao["area_ha"],
            errors="coerce"
        )

        solo_comparacao = solo_comparacao.dropna(
            subset=["ano", "area_ha", "classe", "municipio"]
        )

        municipios_comparacao = sorted(
            solo_comparacao["municipio"].unique().tolist()
        )

        classes_comparacao = sorted(
            solo_comparacao["classe"].unique().tolist()
        )

        # Seleção dos municípios
        municipios_padrao = [
            nome for nome in [
                "Camaquã",
                "Encruzilhada do Sul"
            ]
            if nome in municipios_comparacao
        ]

        municipios_escolhidos = st.multiselect(
            "Selecione os municípios para comparar",
            options=municipios_comparacao,
            default=municipios_padrao,
            key="municipios_comparacao_solo"
        )

        # Seleção da classe
        indice_classe = (
            classes_comparacao.index(classe_selecionada)
            if classe_selecionada in classes_comparacao
            else 0
        )

        classe_comparacao = st.selectbox(
            "Classe de uso e cobertura do solo",
            options=classes_comparacao,
            index=indice_classe,
            key="classe_comparacao_solo"
        )

        if len(municipios_escolhidos) > 3:

            st.warning(
                "Selecione no máximo três municípios para "
                "manter a visualização dos gráficos."
            )

        elif len(municipios_escolhidos) < 2:

            st.info(
                "Selecione pelo menos dois municípios "
                "para realizar a comparação."
            )

        else:

            # Filtrar municípios e classe selecionados
            dados_comparacao = solo_comparacao[
                solo_comparacao["municipio"].isin(
                    municipios_escolhidos
                )
            ].copy()

            # Área da classe por município e ano
            serie_classe = (
                dados_comparacao[
                    dados_comparacao["classe"] == classe_comparacao
                ]
                .groupby(
                    ["ano", "municipio"],
                    as_index=False
                )["area_ha"]
                .sum()
            )

            # Área total mapeada por município e ano
            serie_total = (
                dados_comparacao
                .groupby(
                    ["ano", "municipio"],
                    as_index=False
                )["area_ha"]
                .sum()
                .rename(
                    columns={"area_ha": "area_total_ha"}
                )
            )

            # Integrar as séries
            comparacao = serie_total.merge(
                serie_classe,
                on=["ano", "municipio"],
                how="left"
            )

            # Classe ausente no registro representa área zero
            comparacao["area_ha"] = (
                comparacao["area_ha"].fillna(0)
            )

            comparacao["participacao_percentual"] = (
                comparacao["area_ha"]
                / comparacao["area_total_ha"]
            ) * 100

            comparacao = comparacao.sort_values(
                ["ano", "municipio"]
            )

            # Gráfico de área em hectares
            st.markdown(
                "##### Evolução da área por município"
            )

            fig_comparacao_area = px.line(
                comparacao,
                x="ano",
                y="area_ha",
                color="municipio",
                markers=True,
                title=f"{classe_comparacao} — área em hectares",
                labels={
                    "ano": "Ano",
                    "area_ha": "Área (ha)",
                    "municipio": "Município"
                }
            )

            fig_comparacao_area.update_layout(
                hovermode="x unified",
                xaxis=dict(
                    dtick=5,
                    title="Ano"
                ),
                yaxis_title="Área (ha)",
                legend_title="Município"
            )

            st.plotly_chart(
                fig_comparacao_area,
                use_container_width=True
            )

            # Gráfico de participação percentual
            st.markdown(
                "##### Participação na área mapeada de cada município"
            )

            fig_comparacao_pct = px.line(
                comparacao,
                x="ano",
                y="participacao_percentual",
                color="municipio",
                markers=True,
                title=(
                    f"Participação territorial de "
                    f"{classe_comparacao}"
                ),
                labels={
                    "ano": "Ano",
                    "participacao_percentual": "Participação (%)",
                    "municipio": "Município"
                }
            )

            fig_comparacao_pct.update_layout(
                hovermode="x unified",
                xaxis=dict(
                    dtick=5,
                    title="Ano"
                ),
                yaxis_title="Participação (%)",
                legend_title="Município"
            )

            st.plotly_chart(
                fig_comparacao_pct,
                use_container_width=True
            )

            # Tabela comparativa do ano mais recente
            st.markdown(
                "##### Comparação municipal — ano mais recente"
            )

            ano_recente = comparacao["ano"].max()

            tabela_comparacao = comparacao[
                comparacao["ano"] == ano_recente
            ][
                [
                    "municipio",
                    "area_ha",
                    "area_total_ha",
                    "participacao_percentual"
                ]
            ].copy()

            tabela_comparacao.columns = [
                "Município",
                "Área da classe (ha)",
                "Área mapeada municipal (ha)",
                "Participação (%)"
            ]

            tabela_comparacao = tabela_comparacao.sort_values(
                "Participação (%)",
                ascending=False
            )

            st.dataframe(
                tabela_comparacao.round(2),
                use_container_width=True,
                hide_index=True
            )

            st.caption(
                "Fonte: MapBiomas Collection 11. "
                "A participação percentual corresponde à área da "
                "classe dividida pela soma das áreas mapeadas no "
                "respectivo município e ano."
            )
        tabela_solo = dados_ano[
            ["municipio", "classe", "area_ha"]
        ].sort_values(
            ["municipio", "area_ha"],
            ascending=[True, False]
        )

        st.dataframe(
            tabela_solo,
            use_container_width=True,
            hide_index=True
        )

# ============================================================
# DADOS E METODOLOGIA
# ============================================================

with tab_data:

    st.markdown("### Dados, estrutura e qualidade")

    st.write(
        "O Observatório utiliza bases oficiais e dados importados. "
        "Indicadores ausentes não são estimados automaticamente."
    )

    st.markdown("#### Municípios configurados")

    st.dataframe(
        municipios,
        use_container_width=True
    )

    st.markdown("#### Situação da integração SICOR")

    if not credito_sicor.empty:

        st.success(
            f"{len(credito_sicor):,} registros SICOR carregados "
            "para os municípios configurados."
        )

        st.write(
            f"Período disponível: "
            f"{credito_sicor['data_emissao'].min()} até "
            f"{credito_sicor['data_emissao'].max()}"
        )

    else:

        st.warning(
            "Arquivo regional SICOR não localizado ou sem registros "
            "para os municípios configurados. "
            f"Verifique: {SICOR_FILE}"
        )

    st.markdown("#### Modelos de dados complementares")

    for key, (filename, cols) in FILES.items():

        st.write(
            f"**{filename}** — " + ", ".join(cols)
        )

    st.markdown("#### Cuidados metodológicos")

    st.markdown("""
    - Registrar fonte, ano de referência e data de extração.
    - Não somar variáveis com unidades diferentes.
    - Distinguir valor contratado, liberado e efetivamente aplicado.
    - Distinguir produção, área plantada e produtividade.
    - Não interpretar automaticamente TOTAL_QTDE como número de contratos.
    - Evitar somar estabelecimentos de fontes ou anos incompatíveis.
    - Manter os códigos IBGE como identificadores dos municípios.
    - Identificar claramente os dados ausentes e as limitações das bases.
    """)

    # --------------------------------------------------------
    # RELATORIO EXECUTIVO REGIONAL
    # --------------------------------------------------------

    st.divider()
    st.markdown("### Relatorio Executivo Regional")

    st.caption(
        "Indicadores consolidados dos 21 municipios "
        "do Centro-Sul do Rio Grande do Sul."
    )
    # --------------------------------------------------------
    # PREPARACAO DOS INDICADORES
    # --------------------------------------------------------

    agricola_exec = tables["agricola"].copy()
    familiar_exec = tables["familiar"].copy()
    pecuaria_exec = tables["pecuaria"].copy()
    solo_exec = tables["solo"].copy()

    # Excluir totais gerais da producao agricola
    if "eh_total" in agricola_exec.columns:
        agricola_exec = agricola_exec[
            agricola_exec["eh_total"].astype(str).str.lower()
            .isin(["false", "0", "nao", "não"])
        ].copy()

    # Converter variaveis numericas
    for coluna in ["quantidade_t", "area_colhida_ha"]:
        if coluna in agricola_exec.columns:
            agricola_exec[coluna] = pd.to_numeric(
                agricola_exec[coluna],
                errors="coerce"
            )

    if "quantidade" in pecuaria_exec.columns:
        pecuaria_exec["quantidade"] = pd.to_numeric(
            pecuaria_exec["quantidade"],
            errors="coerce"
        )

    if "estabelecimentos" in familiar_exec.columns:
        familiar_exec["estabelecimentos"] = pd.to_numeric(
            familiar_exec["estabelecimentos"],
            errors="coerce"
        )

    if "ano" in solo_exec.columns:
        solo_exec["ano"] = pd.to_numeric(
            solo_exec["ano"],
            errors="coerce"
        )

    if "area_ha" in solo_exec.columns:
        solo_exec["area_ha"] = pd.to_numeric(
            solo_exec["area_ha"],
            errors="coerce"
        )

    # Calcular indicadores
    total_municipios_exec = len(municipios)

    total_familiar_exec = familiar_exec[
        "estabelecimentos"
    ].sum()

    total_producao_exec = agricola_exec[
        "quantidade_t"
    ].sum()

    total_pecuaria_exec = pecuaria_exec[
        "quantidade"
    ].sum()

    total_area_colhida_exec = agricola_exec[
        "area_colhida_ha"
    ].sum()

    total_credito_registros_exec = len(tables["credito"])

    # Identificar o ano mais recente do MapBiomas
    ano_solo_exec = (
        int(solo_exec["ano"].max())
        if not solo_exec.empty and solo_exec["ano"].notna().any()
        else None
    )

    solo_atual_exec = (
        solo_exec[solo_exec["ano"] == ano_solo_exec].copy()
        if ano_solo_exec is not None
        else solo_exec.iloc[0:0].copy()
    )

    total_area_solo_exec = solo_atual_exec[
        "area_ha"
    ].sum()

    # --------------------------------------------------------
    # CARTOES DE INDICADORES REGIONAIS
    # --------------------------------------------------------

    st.markdown("#### Indicadores regionais")

    k1, k2, k3, k4 = st.columns(4)

    k1.metric(
        "Municipios",
        f"{total_municipios_exec}"
    )

    k2.metric(
        "Estabelecimentos familiares",
        f"{total_familiar_exec:,.0f}"
    )

    k3.metric(
        "Producao agricola",
        f"{total_producao_exec:,.0f} t"
    )

    k4.metric(
        "Efetivos pecuarios informados",
        f"{total_pecuaria_exec:,.0f}"
    )

    k5, k6, k7 = st.columns(3)

    k5.metric(
        "Area colhida acumulada",
        f"{total_area_colhida_exec:,.0f} ha"
    )

    k6.metric(
        "Registros de credito rural",
        f"{total_credito_registros_exec:,.0f}"
    )

    k7.metric(
        f"Area mapeada ({ano_solo_exec})"
        if ano_solo_exec is not None
        else "Area mapeada",
        f"{total_area_solo_exec:,.0f} ha"
    )

    # --------------------------------------------------------
    # RANKING DAS PRINCIPAIS CULTURAS AGRICOLAS
    # --------------------------------------------------------

    st.divider()

    st.markdown("#### Principais culturas agricolas")

    ranking_culturas_exec = (
        agricola_exec
        .dropna(subset=["quantidade_t"])
        .groupby("cultura", as_index=False)["quantidade_t"]
        .sum()
        .sort_values("quantidade_t", ascending=False)
        .head(10)
    )

    if not ranking_culturas_exec.empty:

        fig_culturas_exec = px.bar(
            ranking_culturas_exec,
            x="quantidade_t",
            y="cultura",
            orientation="h",
            text_auto=".2s",
            title="Dez culturas com maior producao",
            labels={
                "quantidade_t": "Producao (toneladas)",
                "cultura": "Cultura"
            }
        )

        fig_culturas_exec.update_layout(
            yaxis={"categoryorder": "total ascending"},
            xaxis_title="Producao (toneladas)",
            yaxis_title="",
            showlegend=False
        )

        st.plotly_chart(
            fig_culturas_exec,
            use_container_width=True
        )

    else:
        st.info(
            "Nao ha dados de producao agricola para o ranking."
        )

    # --------------------------------------------------------
    # RANKING DOS PRINCIPAIS EFETIVOS PECUARIOS
    # --------------------------------------------------------

    st.markdown("#### Principais efetivos pecuarios")

    ranking_pecuaria_exec = (
        pecuaria_exec
        .dropna(subset=["quantidade"])
        .groupby("produto", as_index=False)["quantidade"]
        .sum()
        .sort_values("quantidade", ascending=False)
        .head(10)
    )

    if not ranking_pecuaria_exec.empty:

        fig_pecuaria_exec = px.bar(
            ranking_pecuaria_exec,
            x="quantidade",
            y="produto",
            orientation="h",
            text_auto=".2s",
            title="Efetivo por tipo de rebanho",
            labels={
                "quantidade": "Quantidade (cabecas)",
                "produto": "Tipo de rebanho"
            }
        )

        fig_pecuaria_exec.update_layout(
            yaxis={"categoryorder": "total ascending"},
            xaxis_title="Quantidade (cabecas)",
            yaxis_title="",
            showlegend=False
        )

        st.plotly_chart(
            fig_pecuaria_exec,
            use_container_width=True
        )

    else:
        st.info(
            "Nao ha dados de pecuaria para o ranking."
        )

    # --------------------------------------------------------
    # RANKING DO USO E COBERTURA DO SOLO
    # --------------------------------------------------------

    st.divider()

    st.markdown(
        "#### Principais classes de uso e cobertura do solo"
    )

    ranking_solo_exec = (
        solo_atual_exec
        .groupby("classe", as_index=False)["area_ha"]
        .sum()
        .sort_values("area_ha", ascending=False)
        .head(10)
    )

    if not ranking_solo_exec.empty:

        fig_solo_exec = px.bar(
            ranking_solo_exec,
            x="area_ha",
            y="classe",
            orientation="h",
            text_auto=".2s",
            title=(
                f"Dez classes com maior area em {ano_solo_exec}"
            ),
            labels={
                "area_ha": "Area (hectares)",
                "classe": "Classe"
            }
        )

        fig_solo_exec.update_layout(
            yaxis={"categoryorder": "total ascending"},
            xaxis_title="Area (hectares)",
            yaxis_title="",
            showlegend=False
        )

        st.plotly_chart(
            fig_solo_exec,
            use_container_width=True
        )

    else:
        st.info(
            "Nao ha dados de uso do solo para o ranking."
        )

  
    # --------------------------------------------------------
    # RANKING MUNICIPAL DA PRODUCAO AGRICOLA
    # --------------------------------------------------------

    st.divider()

    st.markdown(
        "### Ranking municipal da produção agrícola"
    )

    st.caption(
        "Classificação dos municípios pelo valor da produção "
        "agrícola no ano mais recente disponível."
    )

    ranking_municipal_exec = agricola_exec.copy()

    ranking_municipal_exec["ano"] = pd.to_numeric(
        ranking_municipal_exec["ano"],
        errors="coerce"
    )

    ranking_municipal_exec["valor_producao_mil_reais"] = (
        pd.to_numeric(
            ranking_municipal_exec["valor_producao_mil_reais"],
            errors="coerce"
        )
    )

    ranking_municipal_exec["quantidade_t"] = pd.to_numeric(
        ranking_municipal_exec["quantidade_t"],
        errors="coerce"
    )

    ano_ranking_exec = ranking_municipal_exec["ano"].max()

    if pd.notna(ano_ranking_exec):

        dados_ranking_exec = ranking_municipal_exec[
            ranking_municipal_exec["ano"] == ano_ranking_exec
        ].copy()

        ranking_municipal_exec = (
            dados_ranking_exec
            .groupby("municipio", as_index=False)
            .agg(
                valor_producao_mil_reais=(
                    "valor_producao_mil_reais",
                    lambda x: x.sum(min_count=1)
                ),
                quantidade_t=(
                    "quantidade_t",
                    lambda x: x.sum(min_count=1)
                )
            )
            .dropna(subset=["valor_producao_mil_reais"])
            .sort_values(
                "valor_producao_mil_reais",
                ascending=False
            )
        )

        total_valor_regional_exec = (
            ranking_municipal_exec[
                "valor_producao_mil_reais"
            ].sum()
        )

        if total_valor_regional_exec > 0:

            ranking_municipal_exec[
                "participacao_percentual"
            ] = (
                ranking_municipal_exec[
                    "valor_producao_mil_reais"
                ] / total_valor_regional_exec * 100
            )

            fig_ranking_municipal_exec = px.bar(
                ranking_municipal_exec,
                x="valor_producao_mil_reais",
                y="municipio",
                orientation="h",
                text_auto=".2s",
                title=(
                    "Valor da produção agrícola por município — "
                    f"{int(ano_ranking_exec)}"
                ),
                labels={
                    "valor_producao_mil_reais": "Valor (R$ mil)",
                    "municipio": "Município"
                }
            )

            fig_ranking_municipal_exec.update_layout(
                yaxis={"categoryorder": "total ascending"},
                xaxis_title="Valor da produção (R$ mil)",
                yaxis_title="",
                showlegend=False
            )

            st.plotly_chart(
                fig_ranking_municipal_exec,
                width="stretch"
            )

            tabela_ranking_municipal_exec = (
                ranking_municipal_exec.copy()
            )

            tabela_ranking_municipal_exec.columns = [
                "Município",
                "Valor da produção (R$ mil)",
                "Produção (t)",
                "Participação regional (%)"
            ]

            tabela_ranking_municipal_exec[
                "Valor da produção (R$ mil)"
            ] = tabela_ranking_municipal_exec[
                "Valor da produção (R$ mil)"
            ].round(2)

            tabela_ranking_municipal_exec[
                "Produção (t)"
            ] = tabela_ranking_municipal_exec[
                "Produção (t)"
            ].round(2)

            tabela_ranking_municipal_exec[
                "Participação regional (%)"
            ] = tabela_ranking_municipal_exec[
                "Participação regional (%)"
            ].round(2)

            st.dataframe(
                tabela_ranking_municipal_exec,
                width="stretch",
                hide_index=True
            )

        else:
            st.info(
                "Não há valores de produção disponíveis "
                "para calcular a participação regional."
            )

    else:
        st.info(
            "Não há ano de referência disponível "
            "para o ranking municipal."
        )

    
    # --------------------------------------------------------
    # COMPARACAO DOS 21 MUNICIPIOS
    # --------------------------------------------------------

    st.divider()

    st.markdown(
        "### Comparação dos indicadores municipais"
    )

    st.caption(
        "Comparação das principais dimensões territoriais, "
        "agrícolas e pecuárias dos 21 municípios."
    )

    # Carregar bases completas, sem depender dos filtros da tela
    familiar_comp = load_table("familiar").copy()
    agricola_comp = load_table("agricola").copy()
    pecuaria_comp = load_table("pecuaria").copy()
    solo_comp = load_table("solo").copy()

    # Padronizar códigos IBGE
    for df_comp in [
        familiar_comp,
        agricola_comp,
        pecuaria_comp,
        solo_comp
    ]:
        df_comp["codigo_ibge"] = (
            df_comp["codigo_ibge"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )

    # Município de referência: base do Censo Agropecuário
    comparacao_municipal = (
        familiar_comp[
            ["codigo_ibge", "municipio"]
        ]
        .drop_duplicates("codigo_ibge")
        .copy()
    )

    # Agricultura familiar - Censo 2017
    familiar_comp["estabelecimentos"] = pd.to_numeric(
        familiar_comp["estabelecimentos"],
        errors="coerce"
    )

    familiar_comp["participacao_percentual"] = pd.to_numeric(
        familiar_comp["participacao_percentual"],
        errors="coerce"
    )

    familiar_resumo = (
        familiar_comp
        .groupby("codigo_ibge", as_index=False)
        .agg(
            estabelecimentos_familiares=(
                "estabelecimentos",
                "sum"
            ),
            participacao_familiar_pct=(
                "participacao_percentual",
                "mean"
            )
        )
    )

    # Produção agrícola - ano mais recente
    agricola_comp["ano"] = pd.to_numeric(
        agricola_comp["ano"],
        errors="coerce"
    )

    agricola_comp["valor_producao_mil_reais"] = pd.to_numeric(
        agricola_comp["valor_producao_mil_reais"],
        errors="coerce"
    )

    agricola_comp["quantidade_t"] = pd.to_numeric(
        agricola_comp["quantidade_t"],
        errors="coerce"
    )

    if "eh_total" in agricola_comp.columns:
        agricola_comp = agricola_comp[
            agricola_comp["eh_total"].astype(str).str.lower()
            .isin(["false", "0", "nao", "não"])
        ].copy()

    ano_agricola_comp = agricola_comp["ano"].max()

    agricola_comp = agricola_comp[
        agricola_comp["ano"] == ano_agricola_comp
    ].copy()

    agricola_resumo = (
        agricola_comp
        .groupby("codigo_ibge", as_index=False)
        .agg(
            valor_producao_mil_reais=(
                "valor_producao_mil_reais",
                lambda x: x.sum(min_count=1)
            ),
            producao_t=(
                "quantidade_t",
                lambda x: x.sum(min_count=1)
            )
        )
    )

    # Pecuária - ano mais recente disponível
    pecuaria_comp["ano"] = pd.to_numeric(
        pecuaria_comp["ano"],
        errors="coerce"
    )

    pecuaria_comp["quantidade"] = pd.to_numeric(
        pecuaria_comp["quantidade"],
        errors="coerce"
    )

    ano_pecuaria_comp = pecuaria_comp["ano"].max()

    pecuaria_comp = pecuaria_comp[
        pecuaria_comp["ano"] == ano_pecuaria_comp
    ].copy()

    pecuaria_resumo = (
        pecuaria_comp
        .groupby("codigo_ibge", as_index=False)
        .agg(
            efetivo_pecuario_cabecas=(
                "quantidade",
                lambda x: x.sum(min_count=1)
            )
        )
    )

    # Uso e cobertura do solo - ano mais recente
    solo_comp["ano"] = pd.to_numeric(
        solo_comp["ano"],
        errors="coerce"
    )

    solo_comp["area_ha"] = pd.to_numeric(
        solo_comp["area_ha"],
        errors="coerce"
    )

    ano_solo_comp = solo_comp["ano"].max()

    solo_comp = solo_comp[
        solo_comp["ano"] == ano_solo_comp
    ].copy()

    solo_resumo = (
        solo_comp
        .groupby("codigo_ibge", as_index=False)
        .agg(
            area_mapeada_ha=(
                "area_ha",
                lambda x: x.sum(min_count=1)
            )
        )
    )

    # Integrar indicadores
    comparacao_municipal = (
        comparacao_municipal
        .merge(familiar_resumo, on="codigo_ibge", how="left")
        .merge(agricola_resumo, on="codigo_ibge", how="left")
        .merge(pecuaria_resumo, on="codigo_ibge", how="left")
        .merge(solo_resumo, on="codigo_ibge", how="left")
    )

    comparacao_municipal = (
        comparacao_municipal
        .sort_values(
            "valor_producao_mil_reais",
            ascending=False,
            na_position="last"
        )
        .reset_index(drop=True)
    )

    comparacao_municipal.insert(
        0,
        "Posição",
        range(1, len(comparacao_municipal) + 1)
    )

    # Apresentação da tabela
    tabela_comparacao = comparacao_municipal[
        [
            "Posição",
            "municipio",
            "estabelecimentos_familiares",
            "participacao_familiar_pct",
            "valor_producao_mil_reais",
            "producao_t",
            "efetivo_pecuario_cabecas",
            "area_mapeada_ha"
        ]
    ].copy()

    tabela_comparacao.columns = [
        "Posição",
        "Município",
        "Estabelecimentos familiares (2017)",
        "Agricultura familiar (%)",
        "Produção agrícola (R$ mil)",
        "Produção agrícola (t)",
        "Efetivo pecuário (cabeças)",
        f"Área mapeada ({int(ano_solo_comp)})"
    ]

    st.dataframe(
        tabela_comparacao,
        width="stretch",
        hide_index=True
    )

    st.caption(
        "Os anos de referência são apresentados separadamente. "
        "Células sem informação representam dados ausentes, "
        "não valores iguais a zero. O ranking segue o valor "
        "da produção agrícola no ano mais recente disponível."
    )

    # --------------------------------------------------------
    # EXPORTAÇÃO DOS DADOS
    # --------------------------------------------------------

    st.divider()

    st.markdown("#### Exportar dados do Observatório")

    st.caption(
        "Os arquivos respeitam os filtros aplicados no painel."
    )

    export_frames = {
        "Crédito rural": tables["credito"],
        "Produção agrícola": tables["agricola"],
        "Agricultura familiar": tables["familiar"],
        "Pecuária": tables["pecuaria"],
        "Uso do solo": tables["solo"],
        "Municípios": municipios
    }

    # Criar arquivo Excel em memória
    excel_buffer = BytesIO()

    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        for nome_aba, df in export_frames.items():

            df_exportar = df.copy()

            df_exportar.to_excel(
                writer,
                sheet_name=nome_aba,
                index=False
            )

            ws = writer.sheets[nome_aba]

            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions

            # Formatação do cabeçalho
            from openpyxl.styles import Font, PatternFill

            for celula in ws[1]:

                celula.font = Font(
                    bold=True,
                    color="FFFFFF"
                )

                celula.fill = PatternFill(
                    fill_type="solid",
                    fgColor="245B45"
                )

            # Ajustar largura das colunas
            for coluna in ws.columns:

                maior = 0
                letra = coluna[0].column_letter

                for celula in coluna[:200]:

                    if celula.value is not None:
                        maior = max(
                            maior,
                            len(str(celula.value))
                        )

                ws.column_dimensions[letra].width = min(
                    maior + 3,
                    40
                )

    excel_buffer.seek(0)

    # --------------------------------------------------------
    # GERAR RELATORIO PDF
    # --------------------------------------------------------

    from datetime import datetime
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak
    )
    from xml.sax.saxutils import escape

    pdf_buffer = BytesIO()

    largura_pagina, altura_pagina = landscape(A4)

    documento = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=2.0 * cm,
        bottomMargin=1.8 * cm
    )

    estilos = getSampleStyleSheet()

    estilo_capa = ParagraphStyle(
        "CapaObservatorio",
        parent=estilos["Title"],
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=30,
        textColor=colors.HexColor("#245B45"),
        alignment=1,
        spaceAfter=20
    )

    estilo_subtitulo = ParagraphStyle(
        "SubtituloObservatorio",
        parent=estilos["Normal"],
        fontSize=13,
        leading=20,
        alignment=1
    )

    estilo_secao = ParagraphStyle(
        "SecaoObservatorio",
        parent=estilos["Heading2"],
        textColor=colors.HexColor("#245B45"),
        spaceBefore=14,
        spaceAfter=8
    )

    estilo_celula = ParagraphStyle(
        "CelulaPDF",
        parent=estilos["Normal"],
        fontSize=7,
        leading=9
    )

    estilo_cabecalho = ParagraphStyle(
        "CabecalhoPDF",
        parent=estilos["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=colors.white
    )

    conteudo_pdf = []

    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")

       # CAPA
        # CAPA DO RELATORIO
    # --------------------------------------------------------

    conteudo_pdf.append(Spacer(1, 2.5 * cm))

    conteudo_pdf.append(
        Paragraph(
            "OBSERVATORIO TERRITORIAL<br/>DA AGRICULTURA",
            estilo_capa
        )
    )

    conteudo_pdf.append(
        Paragraph(
            "CENTRO-SUL DO RIO GRANDE DO SUL",
            estilo_subtitulo
        )
    )

    conteudo_pdf.append(Spacer(1, 1.5 * cm))

    conteudo_pdf.append(
        Paragraph(
            "RELATORIO TECNICO DE DADOS TERRITORIAIS",
            ParagraphStyle(
                "TituloRelatorio",
                parent=estilos["Heading1"],
                alignment=1,
                textColor=colors.HexColor("#333333")
            )
        )
    )

    conteudo_pdf.append(Spacer(1, 1 * cm))

    conteudo_pdf.append(
        Paragraph(
            "Informacoes sobre producao agricola, agricultura "
            "familiar, pecuaria, credito rural e uso e cobertura "
            "do solo.",
            estilo_subtitulo
        )
    )

    conteudo_pdf.append(Spacer(1, 2 * cm))

    conteudo_pdf.append(
        Paragraph(
            f"Data de geracao: {data_geracao}",
            estilo_subtitulo
        )
    )

    conteudo_pdf.append(
        Paragraph(
            "Abrangencia: 21 municipios do Centro-Sul do RS",
            estilo_subtitulo
        )
    )

    conteudo_pdf.append(PageBreak())
    conteudo_pdf.append(
        Paragraph(
            "CENTRO-SUL DO RIO GRANDE DO SUL",
            estilo_subtitulo
        )
    )

    conteudo_pdf.append(Spacer(1, 1.5 * cm))

    conteudo_pdf.append(
        Paragraph(
            "RELATORIO TECNICO DE DADOS TERRITORIAIS",
            ParagraphStyle(
                "TituloRelatorio",
                parent=estilos["Heading1"],
                alignment=1,
                textColor=colors.HexColor("#333333")
            )
        )
    )

    conteudo_pdf.append(Spacer(1, 1 * cm))

    conteudo_pdf.append(
        Paragraph(
            "Informacoes sobre producao agricola, agricultura "
            "familiar, pecuaria, credito rural e uso e cobertura "
            "do solo.",
            estilo_subtitulo
        )
    )

    conteudo_pdf.append(Spacer(1, 2 * cm))

    conteudo_pdf.append(
        Paragraph(
            f"Data de geracao: {data_geracao}",
            estilo_subtitulo
        )
    )

    conteudo_pdf.append(
        Paragraph(
            "Abrangencia: 21 municipios do Centro-Sul do RS",
            estilo_subtitulo
        )
    )

    conteudo_pdf.append(PageBreak())

    # --------------------------------------------------------
    # APRESENTACAO
    # --------------------------------------------------------

    conteudo_pdf.append(
        Paragraph(
            "1. Apresentacao",
            estilo_secao
        )
    )

    conteudo_pdf.append(
        Paragraph(
            "Este relatorio apresenta uma sintese dos dados "
            "disponiveis no Observatorio Territorial da Agricultura "
            "do Centro-Sul do Rio Grande do Sul. As informacoes "
            "sao organizadas por modulo tematico e respeitam os "
            "filtros aplicados no painel no momento da exportacao.",
            estilos["BodyText"]
        )
    )

    conteudo_pdf.append(Spacer(1, 12))

    # --------------------------------------------------------
    # RESUMO DOS MODULOS
    # --------------------------------------------------------

    conteudo_pdf.append(
        Paragraph(
            "2. Modulos e dados disponiveis",
            estilo_secao
        )
    )

    resumo_modulos = [
        ["Modulo", "Registros", "Municipios"],
    ]

    for nome, df in export_frames.items():

        resumo_modulos.append([
            nome,
            str(len(df)),
            str(
                df["municipio"].nunique()
                if "municipio" in df.columns
                else len(df)
            )
        ])

    tabela_resumo = Table(
        resumo_modulos,
        repeatRows=1,
        colWidths=[9 * cm, 4 * cm, 4 * cm]
    )

    tabela_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#245B45")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#EAF1ED")
        ]),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))

    conteudo_pdf.append(tabela_resumo)
    conteudo_pdf.append(Spacer(1, 18))

    # --------------------------------------------------------
    # TABELAS DOS MODULOS
    # --------------------------------------------------------

    conteudo_pdf.append(
        Paragraph(
            "3. Dados por modulo",
            estilo_secao
        )
    )

    for nome, df in export_frames.items():

        conteudo_pdf.append(
            Paragraph(
                escape(nome),
                estilos["Heading3"]
            )
        )

        if df.empty:

            conteudo_pdf.append(
                Paragraph(
                    "Nao ha registros disponiveis para os filtros aplicados.",
                    estilos["BodyText"]
                )
            )

            continue

        df_pdf = df.head(12).copy()

        # Limitar a quantidade de colunas para facilitar a leitura
        df_pdf = df_pdf.iloc[:, :7]

        cabecalho = [
            Paragraph(escape(str(col)), estilo_cabecalho)
            for col in df_pdf.columns
        ]

        linhas_pdf = [cabecalho]

        for _, linha in df_pdf.iterrows():

            valores = []

            for valor in linha:

                if pd.isna(valor):
                    texto = ""
                else:
                    texto = str(valor)

                valores.append(
                    Paragraph(
                        escape(texto[:80]),
                        estilo_celula
                    )
                )

            linhas_pdf.append(valores)

        quantidade_colunas = len(df_pdf.columns)

        tabela_dados = Table(
            linhas_pdf,
            repeatRows=1,
            colWidths=[
                (largura_pagina - 3 * cm) / quantidade_colunas
            ] * quantidade_colunas
        )

        tabela_dados.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#245B45")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#F0F4F1")
            ]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))

        conteudo_pdf.append(tabela_dados)

        conteudo_pdf.append(
            Paragraph(
                f"Exibindo ate 12 registros de um total de {len(df)}.",
                estilos["Italic"]
            )
        )

        conteudo_pdf.append(Spacer(1, 12))

    # --------------------------------------------------------
    # FONTES E METODOLOGIA
    # --------------------------------------------------------

    conteudo_pdf.append(
        Paragraph(
            "4. Fontes de dados e observacoes metodologicas",
            estilo_secao
        )
    )

    fontes_pdf = [
        "IBGE/SIDRA — Producao Agricola Municipal (PAM).",
        "IBGE/SIDRA — Censo Agropecuario 2017, agricultura familiar.",
        "IBGE/SIDRA — Pesquisa da Pecuaria Municipal (PPM).",
        "Banco Central do Brasil — Sistema de Operacoes do Credito Rural (SICOR).",
        "MapBiomas — Colecao 11, uso e cobertura do solo."
    ]

    for fonte in fontes_pdf:
        conteudo_pdf.append(
            Paragraph(
                "• " + escape(fonte),
                estilos["BodyText"]
            )
        )
        conteudo_pdf.append(Spacer(1, 5))

    conteudo_pdf.append(Spacer(1, 12))

    conteudo_pdf.append(
        Paragraph(
            "Nota: os dados apresentados respeitam os filtros "
            "aplicados no painel. As tabelas deste PDF exibem "
            "amostras de ate 12 registros por modulo. Para acessar "
            "os dados completos, utilize os arquivos Excel ou CSV.",
            estilos["BodyText"]
        )
    )

    # --------------------------------------------------------
    # RODAPE E NUMERACAO DE PAGINAS
    # --------------------------------------------------------

    def rodape_pdf(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(
            1.5 * cm,
            1.0 * cm,
            "Observatorio Territorial da Agricultura — Centro-Sul/RS"
        )
        canvas.drawRightString(
            largura_pagina - 1.5 * cm,
            1.0 * cm,
            f"Pagina {doc.page}"
        )
        canvas.restoreState()

    documento.build(
        conteudo_pdf,
        onFirstPage=rodape_pdf,
        onLaterPages=rodape_pdf
    )

    pdf_buffer.seek(0)

    # --------------------------------------------------------
    # RELATORIO EXECUTIVO REGIONAL - 21 MUNICIPIOS
    # --------------------------------------------------------

    pdf_exec_buffer = BytesIO()

    documento_exec = SimpleDocTemplate(
        pdf_exec_buffer,
        pagesize=landscape(A4),
        rightMargin=1.3 * cm,
        leftMargin=1.3 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.7 * cm
    )

    conteudo_exec = []

    estilo_titulo_exec = ParagraphStyle(
        "TituloExecutivo",
        parent=estilos["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=28,
        alignment=1,
        textColor=colors.HexColor("#245B45")
    )

    estilo_texto_exec = ParagraphStyle(
        "TextoExecutivo",
        parent=estilos["BodyText"],
        fontSize=10,
        leading=15,
        alignment=4
    )

    # CAPA
    conteudo_exec.append(Spacer(1, 2.5 * cm))

    conteudo_exec.append(
        Paragraph(
            "OBSERVATORIO TERRITORIAL<br/>DA AGRICULTURA",
            estilo_titulo_exec
        )
    )

    conteudo_exec.append(Spacer(1, 0.5 * cm))

    conteudo_exec.append(
        Paragraph(
            "CENTRO-SUL DO RIO GRANDE DO SUL",
            estilo_subtitulo
        )
    )

    conteudo_exec.append(Spacer(1, 1.5 * cm))

    conteudo_exec.append(
        Paragraph(
            "RELATORIO EXECUTIVO REGIONAL",
            estilo_secao
        )
    )

    conteudo_exec.append(Spacer(1, 1 * cm))

    conteudo_exec.append(
        Paragraph(
            "Diagnostico territorial da agricultura, "
            "agricultura familiar, pecuaria e uso "
            "e cobertura do solo.",
            estilo_subtitulo
        )
    )

    conteudo_exec.append(Spacer(1, 2 * cm))

    conteudo_exec.append(
        Paragraph(
            f"21 municipios | Gerado em {data_geracao}",
            estilo_subtitulo
        )
    )

    conteudo_exec.append(PageBreak())

    # APRESENTACAO
    conteudo_exec.append(
        Paragraph(
            "1. Apresentacao",
            estilo_secao
        )
    )

    conteudo_exec.append(
        Paragraph(
            "Este relatorio apresenta uma sintese dos principais "
            "indicadores territoriais dos 21 municipios do "
            "Centro-Sul do Rio Grande do Sul. O documento integra "
            "informacoes oficiais sobre producao agricola, "
            "agricultura familiar, pecuaria e uso e cobertura "
            "do solo, permitindo uma leitura comparativa "
            "da dinamica agropecuaria regional.",
            estilo_texto_exec
        )
    )

    conteudo_exec.append(Spacer(1, 15))

    # INDICADORES REGIONAIS
    conteudo_exec.append(
        Paragraph(
            "2. Indicadores regionais consolidados",
            estilo_secao
        )
    )

    total_familiar_pdf = comparacao_municipal[
        "estabelecimentos_familiares"
    ].sum(min_count=1)

    total_producao_pdf = comparacao_municipal[
        "valor_producao_mil_reais"
    ].sum(min_count=1)

    total_pecuaria_pdf = comparacao_municipal[
        "efetivo_pecuario_cabecas"
    ].sum(min_count=1)

    total_area_pdf = comparacao_municipal[
        "area_mapeada_ha"
    ].sum(min_count=1)

    indicadores_pdf = [
        ["Indicador", "Resultado"],
        ["Municipios abrangidos", "21"],
        [
            "Estabelecimentos familiares (2017)",
            f"{total_familiar_pdf:,.0f}"
            if pd.notna(total_familiar_pdf) else "Sem dados"
        ],
        [
            "Valor da producao agricola (R$ mil)",
            f"{total_producao_pdf:,.2f}"
            if pd.notna(total_producao_pdf) else "Sem dados"
        ],
        [
            "Efetivo pecuario informado (cabecas)",
            f"{total_pecuaria_pdf:,.0f}"
            if pd.notna(total_pecuaria_pdf) else "Sem dados"
        ],
        [
            f"Area mapeada pelo MapBiomas ({int(ano_solo_comp)})",
            f"{total_area_pdf:,.2f}"
            if pd.notna(total_area_pdf) else "Sem dados"
        ]
    ]

    tabela_indicadores_pdf = Table(
        indicadores_pdf,
        colWidths=[12 * cm, 9 * cm]
    )

    tabela_indicadores_pdf.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#245B45")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#EAF1ED")
        ]),
        ("PADDING", (0, 0), (-1, -1), 7)
    ]))

    conteudo_exec.append(tabela_indicadores_pdf)

    conteudo_exec.append(PageBreak())

    # COMPARACAO MUNICIPAL
    conteudo_exec.append(
        Paragraph(
            "3. Comparacao dos 21 municipios",
            estilo_secao
        )
    )

    conteudo_exec.append(
        Paragraph(
            "A tabela apresenta os indicadores municipais "
            "organizados pelo valor da producao agricola.",
            estilo_texto_exec
        )
    )

    conteudo_exec.append(Spacer(1, 10))

    colunas_exec = [
        "Município",
        "Estabelecimentos familiares",
        "Agricultura familiar (%)",
        "Produção agrícola (R$ mil)",
        "Produção agrícola (t)",
        "Efetivo pecuário (cabeças)",
        "Área mapeada (ha)"
    ]

    dados_exec = [
        [
            Paragraph(str(col), estilo_cabecalho)
            for col in colunas_exec
        ]
    ]

    for _, linha in comparacao_municipal.iterrows():

        dados_exec.append([
            str(linha["municipio"]),
            (
                f'{linha["estabelecimentos_familiares"]:,.0f}'
                if pd.notna(linha["estabelecimentos_familiares"])
                else "—"
            ),
            (
                f'{linha["participacao_familiar_pct"]:.2f}%'
                if pd.notna(linha["participacao_familiar_pct"])
                else "—"
            ),
            (
                f'{linha["valor_producao_mil_reais"]:,.2f}'
                if pd.notna(linha["valor_producao_mil_reais"])
                else "—"
            ),
            (
                f'{linha["producao_t"]:,.2f}'
                if pd.notna(linha["producao_t"])
                else "—"
            ),
            (
                f'{linha["efetivo_pecuario_cabecas"]:,.0f}'
                if pd.notna(linha["efetivo_pecuario_cabecas"])
                else "—"
            ),
            (
                f'{linha["area_mapeada_ha"]:,.2f}'
                if pd.notna(linha["area_mapeada_ha"])
                else "—"
            )
        ])

    tabela_municipios_pdf = Table(
        dados_exec,
        repeatRows=1,
        colWidths=[
            3.0 * cm,
            3.1 * cm,
            2.4 * cm,
            3.2 * cm,
            2.5 * cm,
            3.0 * cm,
            3.0 * cm
        ]
    )

    tabela_municipios_pdf.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#245B45")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white,
            colors.HexColor("#EAF1ED")
        ]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 5)
    ]))

    conteudo_exec.append(tabela_municipios_pdf)

    conteudo_exec.append(Spacer(1, 15))

    # FONTES E METODOLOGIA
    conteudo_exec.append(
        Paragraph(
            "4. Fontes e referencias metodologicas",
            estilo_secao
        )
    )

    fontes_exec = [
        "IBGE/SIDRA - Producao Agricola Municipal (PAM).",
        "IBGE/SIDRA - Censo Agropecuario 2017.",
        "IBGE/SIDRA - Pesquisa da Pecuaria Municipal (PPM).",
        "Banco Central do Brasil - SICOR.",
        "MapBiomas - Colecao 11."
    ]

    for fonte in fontes_exec:
        conteudo_exec.append(
            Paragraph(
                "- " + escape(fonte),
                estilos["BodyText"]
            )
        )

    conteudo_exec.append(Spacer(1, 10))

    conteudo_exec.append(
        Paragraph(
            "Os anos de referencia variam conforme a fonte: "
            "agricultura familiar (2017), producao agricola "
            f"({int(ano_agricola_comp)}), pecuaria "
            f"({int(ano_pecuaria_comp)}) e uso do solo "
            f"({int(ano_solo_comp)}). Dados ausentes nao "
            "devem ser interpretados como valores iguais a zero. "
            "Os efetivos pecuarios representam a soma das "
            "categorias informadas na base consultada.",
            estilo_texto_exec
        )
    )

    documento_exec.build(
        conteudo_exec,
        onFirstPage=rodape_pdf,
        onLaterPages=rodape_pdf
    )

    pdf_exec_buffer.seek(0)

    # --------------------------------------------------------
    # RELATORIO EXECUTIVO REGIONAL - 21 MUNICIPIOS
    # --------------------------------------------------------

    pdf_exec_buffer = BytesIO()

    documento_exec = SimpleDocTemplate(
        pdf_exec_buffer,
        pagesize=landscape(A4),
        rightMargin=1.3 * cm,
        leftMargin=1.3 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.7 * cm
    )

    conteudo_exec = []

    estilo_titulo_exec = ParagraphStyle(
        "TituloExecutivo",
        parent=estilos["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=28,
        alignment=1,
        textColor=colors.HexColor("#245B45")
    )

    estilo_texto_exec = ParagraphStyle(
        "TextoExecutivo",
        parent=estilos["BodyText"],
        fontSize=10,
        leading=15,
        alignment=4
    )

      # CAPA INSTITUCIONAL
    conteudo_exec.append(Spacer(1, 1.5 * cm))

    estilo_institucional = ParagraphStyle(
        "Institucional",
        parent=estilos["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=18,
        alignment=1,
        textColor=colors.HexColor("#333333")
    )

    estilo_autoria = ParagraphStyle(
        "Autoria",
        parent=estilos["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=16,
        alignment=1,
        textColor=colors.HexColor("#555555")
    )

    conteudo_exec.append(
        Paragraph(
            "INSTITUTO FEDERAL SUL-RIO-GRANDENSE<br/>"
            "CÂMPUS CAMAQUÃ",
            estilo_institucional
        )
    )

    conteudo_exec.append(Spacer(1, 1.5 * cm))

    conteudo_exec.append(
        Paragraph(
            "OBSERVATÓRIO TERRITORIAL<br/>DA AGRICULTURA",
            estilo_titulo_exec
        )
    )

    conteudo_exec.append(Spacer(1, 0.5 * cm))

    conteudo_exec.append(
        Paragraph(
            "CENTRO-SUL DO RIO GRANDE DO SUL",
            estilo_subtitulo
        )
    )

    conteudo_exec.append(Spacer(1, 1.2 * cm))

    conteudo_exec.append(
        Paragraph(
            "RELATÓRIO EXECUTIVO REGIONAL",
            estilo_secao
        )
    )

    conteudo_exec.append(Spacer(1, 0.7 * cm))

    conteudo_exec.append(
        Paragraph(
            "Diagnóstico territorial da agricultura, agricultura familiar, "
            "pecuária e uso e cobertura do solo.",
            estilo_subtitulo
        )
    )

    conteudo_exec.append(Spacer(1, 1.2 * cm))

    conteudo_exec.append(
        Paragraph(
            "Prof. Dr. Rogério Pires Santos",
            estilo_autoria
        )
    )

    conteudo_exec.append(Spacer(1, 1 * cm))

    conteudo_exec.append(
        Paragraph(
            f"21 municípios | Gerado em {data_geracao}",
            estilo_subtitulo
        )
    )

    conteudo_exec.append(PageBreak())
    # APRESENTACAO
    conteudo_exec.append(
        Paragraph("1. Apresentacao", estilo_secao)
    )
    conteudo_exec.append(
        Paragraph(
            "Este relatorio apresenta uma sintese dos principais indicadores "
            "territoriais dos 21 municipios do Centro-Sul do Rio Grande do Sul. "
            "O documento integra informacoes oficiais sobre producao agricola, "
            "agricultura familiar, pecuaria e uso e cobertura do solo, "
            "permitindo uma leitura comparativa da dinamica agropecuaria regional.",
            estilo_texto_exec
        )
    )
    conteudo_exec.append(Spacer(1, 15))

    # INDICADORES REGIONAIS
    conteudo_exec.append(
        Paragraph("2. Indicadores regionais consolidados", estilo_secao)
    )

    total_familiar_pdf = comparacao_municipal[
        "estabelecimentos_familiares"
    ].sum(min_count=1)

    total_producao_pdf = comparacao_municipal[
        "valor_producao_mil_reais"
    ].sum(min_count=1)

    total_pecuaria_pdf = comparacao_municipal[
        "efetivo_pecuario_cabecas"
    ].sum(min_count=1)

    total_area_pdf = comparacao_municipal[
        "area_mapeada_ha"
    ].sum(min_count=1)

    indicadores_pdf = [
        ["Indicador", "Resultado"],
        ["Municipios abrangidos", "21"],
        [
            "Estabelecimentos familiares (2017)",
            f"{total_familiar_pdf:,.0f}".replace(",", ".")
            if pd.notna(total_familiar_pdf) else "—"
        ],
        [
            "Valor da producao agricola (R$ mil)",
            f"{total_producao_pdf:,.2f}".replace(",", "X")
            .replace(".", ",").replace("X", ".")
            if pd.notna(total_producao_pdf) else "—"
        ],
        [
            "Efetivo pecuario informado (cabecas)",
            f"{total_pecuaria_pdf:,.0f}".replace(",", ".")
            if pd.notna(total_pecuaria_pdf) else "—"
        ],
        [
            f"Area mapeada pelo MapBiomas ({int(ano_solo_comp)})",
            f"{total_area_pdf:,.2f}".replace(",", "X")
            .replace(".", ",").replace("X", ".")
            if pd.notna(total_area_pdf) else "—"
        ]
    ]

    tabela_indicadores_pdf = Table(
        indicadores_pdf,
        colWidths=[12 * cm, 9 * cm]
    )

    tabela_indicadores_pdf.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#245B45")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#EAF2ED")
            ]),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("PADDING", (0, 0), (-1, -1), 7)
        ])
    )

    conteudo_exec.append(tabela_indicadores_pdf)
    conteudo_exec.append(PageBreak())

    # COMPARACAO MUNICIPAL
    conteudo_exec.append(
        Paragraph("3. Comparacao dos 21 municipios", estilo_secao)
    )
    conteudo_exec.append(
        Paragraph(
            "Indicadores municipais organizados pelo valor da producao agricola.",
            estilo_texto_exec
        )
    )

    colunas_pdf = [
        "Municipio",
        "Estab. familiares",
        "Agricultura familiar (%)",
        "Producao agricola (R$ mil)",
        "Producao (t)",
        "Efetivo pecuario",
        "Area mapeada (ha)"
    ]

    dados_municipios_pdf = [
        [Paragraph(str(c), estilo_cabecalho) for c in colunas_pdf]
    ]

    for _, linha in comparacao_municipal.iterrows():
        dados_municipios_pdf.append([
            str(linha["municipio"]),
            (
                f'{linha["estabelecimentos_familiares"]:,.0f}'.replace(",", ".")
                if pd.notna(linha["estabelecimentos_familiares"]) else "—"
            ),
            (
                f'{linha["participacao_familiar_pct"]:.2f}%'.replace(".", ",")
                if pd.notna(linha["participacao_familiar_pct"]) else "—"
            ),
            (
                f'{linha["valor_producao_mil_reais"]:,.2f}'.replace(",", "X")
                .replace(".", ",").replace("X", ".")
                if pd.notna(linha["valor_producao_mil_reais"]) else "—"
            ),
            (
                f'{linha["producao_t"]:,.0f}'.replace(",", ".")
                if pd.notna(linha["producao_t"]) else "—"
            ),
            (
                f'{linha["efetivo_pecuario_cabecas"]:,.0f}'.replace(",", ".")
                if pd.notna(linha["efetivo_pecuario_cabecas"]) else "—"
            ),
            (
                f'{linha["area_mapeada_ha"]:,.0f}'.replace(",", ".")
                if pd.notna(linha["area_mapeada_ha"]) else "—"
            )
        ])

    tabela_municipios_pdf = Table(
        dados_municipios_pdf,
        repeatRows=1,
        colWidths=[
            3.0 * cm, 2.5 * cm, 2.5 * cm, 3.0 * cm,
            2.3 * cm, 2.5 * cm, 2.5 * cm
        ]
    )

    tabela_municipios_pdf.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#245B45")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#EAF2ED")
            ]),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 5)
        ])
    )

    conteudo_exec.append(tabela_municipios_pdf)
    conteudo_exec.append(Spacer(1, 15))

    # FONTES E METODOLOGIA
    conteudo_exec.append(
        Paragraph("4. Fontes e referencias metodologicas", estilo_secao)
    )

    fontes_exec = [
        "IBGE/SIDRA - Producao Agricola Municipal (PAM).",
        "IBGE/SIDRA - Censo Agropecuario 2017.",
        "IBGE/SIDRA - Pesquisa da Pecuaria Municipal (PPM).",
        "Banco Central do Brasil - SICOR.",
        "MapBiomas - Colecao 11."
    ]

    for fonte in fontes_exec:
        conteudo_exec.append(
            Paragraph(f"• {escape(fonte)}", estilo_texto_exec)
        )

    conteudo_exec.append(Spacer(1, 10))
    conteudo_exec.append(
        Paragraph(
            f"Anos de referencia: agricultura {ano_agricola_comp}; "
            f"pecuaria {ano_pecuaria_comp}; MapBiomas {ano_solo_comp}. "
            "A agricultura familiar utiliza dados do Censo Agropecuario de 2017. "
            "Os efetivos pecuarios representam os registros informados na base. "
            "Valores ausentes nao foram interpretados como zero.",
            estilo_texto_exec
        )
    )

    documento_exec.build(
        conteudo_exec,
        onFirstPage=rodape_pdf,
        onLaterPages=rodape_pdf
    )

    pdf_exec_buffer.seek(0)
    col_excel, col_csv, col_pdf = st.columns(3)

    col_excel.download_button(
        "📊 Baixar relatório Excel",
        data=excel_buffer.getvalue(),
        file_name="observatorio_agricultura_rs.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    # Manter também a exportação CSV
    export_frames_csv = []

    for nome, df in tables.items():

        if not df.empty:

            temp = df.copy()
            temp.insert(0, "modulo", nome)
            export_frames_csv.append(temp)

    if export_frames_csv:

        out = pd.concat(
            export_frames_csv,
            ignore_index=True,
            sort=False
        )

        col_csv.download_button(
            "📄 Baixar dados filtrados CSV",
            out.to_csv(index=False).encode("utf-8-sig"),
            file_name="observatorio_agricultura_rs_dados.csv",
            mime="text/csv"
        )
    col_pdf.download_button(
        "📕 Baixar relatório PDF",
        data=pdf_buffer.getvalue(),
        file_name="observatorio_agricultura_rs_relatorio.pdf",
        mime="application/pdf"
    )
    st.download_button(
        "📘 Baixar Relatório Executivo Regional (21 municípios)",
        data=pdf_exec_buffer.getvalue(),
        file_name="observatorio_agricultura_rs_relatorio_executivo_regional.pdf",
        mime="application/pdf",
        width="stretch"
    )


# ============================================================
# RODAPÉ
# ============================================================

st.caption(
    "Observatório Territorial da Agricultura — Centro-Sul do RS | "
    "Versão 0.2 | Dados SICOR integrados"
)
