import streamlit as st
import geopandas as gpd
import pandas as pd
from streamlit_folium import st_folium
import folium

st.set_page_config(layout="wide")

st.title("🌳 Análise de Desmatamento — CAR Feijó (AC)")

# =========================
# CACHE (evita recarregar shp)
# =========================
@st.cache_data
def load_data():
    locais = gpd.read_file("Cadastros_UTM.shp")
    desmat = gpd.read_file("Desmatamento_UTM.shp")
    feijo = gpd.read_file("Feijo_UTM.shp")

    # garantir mesmo CRS
    desmat = desmat.to_crs(locais.crs)
    feijo = feijo.to_crs(locais.crs)

    return locais, desmat, feijo


locais, desmat, feijo = load_data()

# =========================
# SIDEBAR (Filtros)
# =========================
st.sidebar.header("Filtros")

classes = st.sidebar.multiselect(
    "CLASS",
    sorted(locais["CLASS"].dropna().unique()),
    default=sorted(locais["CLASS"].dropna().unique())
)

status = st.sidebar.multiselect(
    "Status",
    sorted(locais["status_imo"].dropna().unique()),
    default=sorted(locais["status_imo"].dropna().unique())
)

tipos = st.sidebar.multiselect(
    "Tipo imóvel",
    sorted(locais["tipo_imove"].dropna().unique()),
    default=sorted(locais["tipo_imove"].dropna().unique())
)

locais_filt = locais[
    (locais["CLASS"].isin(classes)) &
    (locais["status_imo"].isin(status)) &
    (locais["tipo_imove"].isin(tipos))
]

# =========================
# INTERSEÇÃO ESPACIAL
# =========================
st.subheader("Processando áreas...")

intersec = gpd.overlay(locais_filt, desmat, how="intersection")

intersec["area_desmat_ha"] = intersec.geometry.area / 10000

area_por_imovel = (
    intersec.groupby("cod_imovel")["area_desmat_ha"]
    .sum()
    .reset_index()
)

locais_join = locais_filt.merge(area_por_imovel, on="cod_imovel", how="left")
locais_join["area_desmat_ha"] = locais_join["area_desmat_ha"].fillna(0)

locais_join["perc_desmat"] = (
    locais_join["area_desmat_ha"] / locais_join["area_ha"] * 100
)

# =========================
# MÉTRICAS GERAIS
# =========================

# total dentro do município
desmat_feijo = gpd.overlay(desmat, feijo, how="intersection")
total_municipio = desmat_feijo.geometry.area.sum() / 10000

# total nas fazendas
total_fazendas = locais_join["area_desmat_ha"].sum()

col1, col2, col3 = st.columns(3)

col1.metric("🌲 Desmatamento no município (ha)", f"{total_municipio:,.1f}")
col2.metric("🚜 Desmatamento nas fazendas (ha)", f"{total_fazendas:,.1f}")
col3.metric("🏡 Nº imóveis analisados", len(locais_join))

# =========================
# MAPA INTERATIVO
# =========================
st.subheader("Mapa")

cols_mapa = ["cod_imovel", "area_desmat_ha", "perc_desmat", "geometry"]
locais_wgs = locais_join[cols_mapa].to_crs(4326)
desmat_wgs = desmat.to_crs(4326)
feijo_wgs = feijo.to_crs(4326)

center = feijo_wgs.geometry.centroid.iloc[0]
m = folium.Map(location=[center.y, center.x], zoom_start=10)

folium.GeoJson(
    feijo_wgs,
    name="Município",
    style_function=lambda x: {"fill": False, "color": "black", "weight": 2}
).add_to(m)

folium.GeoJson(
    desmat_wgs,
    name="Desmatamento",
    style_function=lambda x: {"color": "red", "weight": 1}
).add_to(m)

folium.GeoJson(
    locais_wgs,
    name="Fazendas",
    tooltip=folium.GeoJsonTooltip(
        fields=["cod_imovel", "area_desmat_ha", "perc_desmat"],
        aliases=["Imóvel:", "Desmat (ha):", "% Desmat:"]
    ),
    style_function=lambda x: {"fillOpacity": 0.2}
).add_to(m)

folium.LayerControl().add_to(m)

st_folium(m, width=1400, height=600)

# =========================
# TABELA
# =========================
st.subheader("Tabela por imóvel")

st.dataframe(
    locais_join[
        ["cod_imovel", "CLASS", "area_ha", "area_desmat_ha", "perc_desmat"]
    ].sort_values("area_desmat_ha", ascending=False),
    use_container_width=True
)

