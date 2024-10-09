import streamlit as st
import pandas as pd
import requests
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
import plotly.graph_objs as go
import plotly.express as px
import io

# Définir la configuration de la page
st.set_page_config(page_title="UNILEVER", page_icon="🌍", layout="wide")
st.header(":bar_chart: Unilever Dashboard")
st.markdown('<style>div.block-container{padding-top:2rem;}</style>', unsafe_allow_html=True)

# Caching des données pour éviter les appels multiples à l'API
@st.cache_data
def download_kobo_data(api_url, headers):
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la récupération des données : {e}")
        return None

# API URL et clé
api_url = "https://kf.kobotoolbox.org/api/v2/assets/amfgmGRANPdTQgh85J7YqK/data/?format=json"
headers = {
    "Authorization": "Token fd0239896ad338de0651fe082978bec82cc7dad4"
}

# Télécharger les données depuis KoboCollect
data = download_kobo_data(api_url, headers)

if data:
    # Conversion des données JSON en DataFrame
    df_kobo = pd.json_normalize(data['results'])

    # Afficher les données dans Streamlit
    st.subheader("Données collectées")
    st.dataframe(df_kobo)  # Afficher les données sous forme de tableau

    # Convertir le DataFrame en un fichier Excel en mémoire
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_kobo.to_excel(writer, index=False)
    processed_data = output.getvalue()

    # Bouton pour télécharger le fichier Excel
    st.download_button(
        label="📥 Télécharger les données en format Excel",
        data=processed_data,
        file_name="donnees_collectees.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Création et transformation des DataFrames GPI et Sondage
    df_gpi = pd.DataFrame([
        {'Categorie': 'PERSONAL_CARE', 'Sorte': 'Vaseline_PJs_240ml'},
        {'Categorie': 'PERSONAL_CARE', 'Sorte': 'Vaseline_PJs_240ml'},
        {'Categorie': 'PERSONAL_CARE', 'Sorte': 'Vaseline_PJs_240ml'},
        {'Categorie': 'HOME_CARE', 'Sorte': 'Vim_500g'}
    ])

    df_sondage = pd.DataFrame([
        {'Sorte_caracteristic': 'Royco_8g_Cases', 'PVU': '22000', 'QT': '1', 'PVT': '22000'},
        {'Sorte_caracteristic': 'Vaseline_PJs_240ml', 'PVU': '11000', 'QT': '2', 'PVT': '22000'}
    ])

    # Combiner les deux DataFrames et ajouter à df_kobo
    df_combined = pd.concat([df_gpi, df_sondage], axis=1)
    df_kobo[['Categorie', 'Sorte', 'Sorte_caracteristic', 'PVU', 'QT', 'PVT']] = df_combined

    # Vérification et traitement des données GPS
    if 'GPS' in df_kobo.columns:
        gps_split = df_kobo['GPS'].str.split(' ', expand=True)
        df_kobo[['Latitude', 'Longitude', 'Altitude', 'Autre']] = gps_split.astype(float)

        # Convertir la colonne des dates
        df_kobo["_submission_time"] = pd.to_datetime(df_kobo["_submission_time"])

        # Entrée pour la sélection des dates
        date1 = st.sidebar.date_input("Choisissez la date de début")
        date2 = st.sidebar.date_input("Choisissez la date de fin")

        # Filtrer par date
        df_filtered = df_kobo[
            (df_kobo["_submission_time"] >= pd.to_datetime(date1)) & 
            (df_kobo["_submission_time"] <= pd.to_datetime(date2))
        ]

        # Sidebar pour les filtres supplémentaires
        st.sidebar.header("Choisissez vos filtres:")
        filters = {
            "Identification/Province": st.sidebar.multiselect("Choisissez votre Province", df_filtered["Identification/Province"].unique()),
            "Identification/Commune": st.sidebar.multiselect("Choisir la commune", df_filtered["Identification/Commune"].unique()),
            "Identification/Adresse_PDV": st.sidebar.multiselect("Choisir l'avenue", df_filtered["Identification/Adresse_PDV"].unique()),
            "Name_Agent": st.sidebar.multiselect("Choisir le Nom et prénom", df_filtered["Name_Agent"].unique())
        }

        for col, selection in filters.items():
            if selection:
                df_filtered = df_filtered[df_filtered[col].isin(selection)]

        with st.expander("ANALYTICS"):
            a1, a2 = st.columns(2)
	    # Calculer la somme de la colonne PVT
            total_price = df_filtered['PVT'].astype(float).sum() if 'PVT' in df_filtered.columns else 0
            # Calculer le prix total
            num_rows = len(df_filtered)  # Utiliser len() pour obtenir le nombre total de lignes
            a1.metric(label="Nombres de PDV", value=num_rows, help=f"Total Price: {total_price}", delta=total_price)
            a2.metric(label="Total Price", value=total_price, help=f"Total Price: {total_price}", delta=total_price)


        # Afficher les données filtrées
        st.subheader("Données Filtrées")
        st.dataframe(df_filtered, use_container_width=True)

        # Convertir le DataFrame filtré en un fichier Excel en mémoire
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_filtered.to_excel(writer, index=False)
        processed_data = output.getvalue()

        # Bouton pour télécharger les données filtrées en format Excel
        st.download_button(
            label="📥 Télécharger les données filtrées en format Excel",
            data=processed_data,
            file_name="données_filtrées.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Vérification avant d'afficher la carte
        if not df_filtered[['Latitude', 'Longitude']].isna().all().any():
            df_filtered = df_filtered.dropna(subset=['Latitude', 'Longitude'])
            map_center = [df_filtered['Latitude'].mean(), df_filtered['Longitude'].mean()]
            map_folium = folium.Map(location=map_center, zoom_start=12)
            marker_cluster = MarkerCluster().add_to(map_folium)

            for _, row in df_filtered.iterrows():
                folium.Marker(
                    location=[row['Latitude'], row['Longitude']],
                    popup=f"Agent: {row['Name_Agent']}"
                ).add_to(marker_cluster)

            folium_static(map_folium)
        else:
            st.warning("Aucune donnée valide pour afficher la carte.")

        # Graphiques
        col1, col2 = st.columns(2)
        with col1:
            fig2 = go.Figure(
                data=[go.Bar(x=df_filtered['Sorte'], y=df_filtered['PVT'].astype(float))],
                layout=go.Layout(
                    title=go.layout.Title(text="BUSINESS TYPE BY QUARTILES OF INVESTMENT"),
                    plot_bgcolor='rgba(0, 0, 0, 0)',
                    paper_bgcolor='rgba(0, 0, 0, 0)',
                    xaxis=dict(showgrid=True, gridcolor='#cecdcd'),
                    yaxis=dict(showgrid=True, gridcolor='#cecdcd'),
                    font=dict(color='#cecdcd'),
                )
            )
            st.plotly_chart(fig2, use_container_width=True)

        with col2:
            fig = px.pie(df_filtered, values='PVT', names='Sorte', title='TotalPrice by Name')
            fig.update_traces(hole=0.4)
            fig.update_layout(width=800)
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning("Aucune donnée valide pour afficher les informations GPS.")
else:
    st.error("Impossible d'afficher les données, veuillez sélectionner au moins un emplacement commercial.")
