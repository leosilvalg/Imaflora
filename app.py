import streamlit as st
import geopandas as gpd
import pandas as pd
from streamlit_folium import st_folium
import folium

st.set_page_config(layout="wide")

col1, col2, col3 = st.columns([3,1,3])

with col2:
    st.image("logo.png", width=150)

st.markdown(
    "<h1 style='text-align:center;'>🌳 Análise de Desmatamento — CAR Feijó (AC)</h1>",
    unsafe_allow_html=True
)



# =========================
# CACHE (evita recarregar shp)
# =========================
@st.cache_data

def load_data():
    gpkg = "Dados_Feijo.gpkg"

    locais = gpd.read_file(gpkg, layer="Area_WGS").to_crs(31979)
    desmat = gpd.read_file(gpkg, layer="DesmatamentoWGS").to_crs(31979)
    feijo = gpd.read_file(gpkg, layer="FeijoWGS").to_crs(31979)
    intersect = gpd.read_file(gpkg, layer="Intersec_Dissolvido_WGS").to_crs(31979)
    Brasil = gpd.read_file(gpkg, layer="BrasilWGS")

    return locais, desmat, feijo, intersect, Brasil


locais, desmat, feijo, intersect, Brasil = load_data()


# SIDEBAR

st.markdown("## 🔎 Filtros")

c1, c2, c3, c4 = st.columns(4)

with c1:
    classes = st.multiselect(
        "Classe (Baseada no Módulo Fiscal e Fração Mínima de Parcelamento)",
        sorted(locais["Classe"].dropna().unique()),
        default=sorted(locais["Classe"].dropna().unique())
    )

with c2:
    status = st.multiselect(
        "Status do imóvel",
        sorted(locais["Status"].dropna().unique()),
        default=sorted(locais["Status"].unique())
    )

with c3:
    tipos = st.multiselect(
        "Tipo do imóvel",
        sorted(locais["Tipo"].dropna().unique()),
        default=sorted(locais["Tipo"].unique())
    )

with c4:
    codigo = st.selectbox(
        "Código do imóvel",
        options=["Todos"] + sorted(locais["Codigo"].astype(str).unique()),
        index=0
    )

locais_filt = locais[
    (locais["Classe"].isin(classes)) &
    (locais["Status"].isin(status)) &
    (locais["Tipo"].isin(tipos))
]

if codigo != "Todos":
    locais_filt = locais_filt[locais_filt["Codigo"].astype(str) == codigo]

# INTERSEÇÃO ESPACIAL

st.subheader("Processando áreas...")

#intersec = intersect

intersect["Area Desmatada (ha)"] = intersect.geometry.area / 10000

area_por_imovel = (
    intersect.groupby("Codigo")["Area Desmatada (ha)"]
    .sum()
    .reset_index()
)

locais_join = locais_filt.merge(area_por_imovel, on="Codigo", how="left")
locais_join["Area Desmatada (ha)"] = (locais_join["Area Desmatada (ha)"].fillna(0)).round(2)

locais_join["Percentual de Area Desmatada (%)"] = (
    locais_join["Area Desmatada (ha)"] / locais_join["Area"] * 100
).round(0).astype(int).astype(str) + "%"


# MÉTRICAS GERAIS


# total dentro do município
desmat_diss = desmat.dissolve()   # remove sobreposição interna
desmat_feijo = gpd.overlay(desmat_diss, feijo, how="intersection")
total_municipio = desmat_feijo.geometry.area.sum() / 10000

# total nas fazendas
total_fazendas = locais_join["Area Desmatada (ha)"].sum()

col1, col2, col3 = st.columns(3)

col1.metric("🌲 Desmatamento no município (ha)", f"{total_municipio:,.1f}")
col2.metric("🚜 Desmatamento nas propriedades (ha)", f"{total_fazendas:,.1f}")
col3.metric("🏡 Nº imóveis analisados", len(locais_join))


# MAPA INTERATIVO

st.subheader("Mapa")

mostrar_sobreposicao = st.checkbox(
    "Mostrar apenas feições de desmatamento na área dos imóveis",
    value=False
)

cols_mapa = ["Codigo", "Area Desmatada (ha)", "Percentual de Area Desmatada (%)", "geometry"]
locais_wgs = locais_join[cols_mapa].to_crs(4326)
desmat_wgs = desmat.to_crs(4326)
feijo_wgs = feijo.to_crs(4326)


codigos_validos = locais_filt["Codigo"].astype(str).unique()

intersect_filt = intersect[
    intersect["Codigo"].astype(str).isin(codigos_validos)
]
intersec_wgs = intersect_filt.to_crs(4326)


m = folium.Map(tiles="Esri.WorldImagery")

if codigo != "Todos" and len(locais_wgs) > 0:
    bounds = locais_wgs.total_bounds
    m.fit_bounds([
        [bounds[1], bounds[0]],
        [bounds[3], bounds[2]]
    ])
else:
    bounds = feijo_wgs.total_bounds
    m.fit_bounds([
        [bounds[1], bounds[0]],
        [bounds[3], bounds[2]]
    ])

folium.GeoJson(
    Brasil,
    name="País",
    style_function=lambda x: {"fill": False, "color": "black", "weight": 2}
).add_to(m)

folium.GeoJson(
    feijo_wgs,
    name="Município",
    style_function=lambda x: {"fill": False, "color": "black", "weight": 2}
).add_to(m)

if mostrar_sobreposicao:
    folium.GeoJson(
        intersec_wgs,
        name="Desmatamento dentro dos imóveis",
        style_function=lambda x: {
            "color": "yellow",
            "weight": 1,
            "fillOpacity": 0.7
        }
    ).add_to(m)
else:
    folium.GeoJson(
        desmat_wgs,
        name="Desmatamento total",
        style_function=lambda x: {
            "color": "red",
            "weight": 1
        }
    ).add_to(m)

folium.GeoJson(
    locais_wgs,
    name="Fazendas",
    tooltip=folium.GeoJsonTooltip(
        fields=["Codigo", "Area Desmatada (ha)", "Percentual de Area Desmatada (%)"],
        aliases=["Imóvel:", "Desmat (ha):", "% Desmat:"]
    ),
    style_function=lambda x: {"fillOpacity": 0.2}
).add_to(m)

folium.LayerControl().add_to(m)

st_folium(m, width=1400, height=600)


# TABELA 1

st.subheader("Resumo por Condição da Propriedade")

resumo_cond = (
    locais_filt
        .groupby("Condicao")
        .size()
        .reset_index(name="Quantidade de Propriedades")
)

total = resumo_cond["Quantidade de Propriedades"].sum()

resumo_cond["Percentual"] = (
    resumo_cond["Quantidade de Propriedades"] / total * 100
).round(0).astype(int).astype(str) + "%"

resumo_cond = resumo_cond.sort_values(
    "Quantidade de Propriedades", ascending=False
)

st.dataframe(
    resumo_cond,
    use_container_width=True,
    hide_index=True
)

# TABELA 2

st.subheader("Resumo Individual por Propriedade")

st.dataframe(
    locais_join[
        ["Codigo", "Condicao", "Classe", "Area", "Area Desmatada (ha)", "Percentual de Area Desmatada (%)"]
    ].sort_values("Area Desmatada (ha)", ascending=False),
    use_container_width=True
)

