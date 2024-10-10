import streamlit as st
import pandas as pd
import requests
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
import plotly.graph_objs as go
import plotly.express as px
import io

# Define the page configuration
st.set_page_config(page_title="UNILEVER", page_icon="🌍", layout="wide")
st.header(":bar_chart: Unilever Dashboard")
st.markdown('<style>div.block-container{padding-top:2rem;}</style>', unsafe_allow_html=True)

# Caching data to avoid multiple API calls
@st.cache_data
def download_kobo_data(api_url, headers):
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error retrieving the data: {e}")
        return None

# API URL and key
api_url = "https://kf.kobotoolbox.org/api/v2/assets/amfgmGRANPdTQgh85J7YqK/data/?format=json"
headers = {
    "Authorization": "Token fd0239896ad338de0651fe082978bec82cc7dad4"
}

# Download the data from KoboCollect
data = download_kobo_data(api_url, headers)
st.success("KoboCollect data retrieved successfully!")

if data:
    # Convert JSON data to DataFrame
    df_kobo = pd.json_normalize(data['results'])

    # Display the data in Streamlit
    with st.expander("Gross data"):
        st.dataframe(df_kobo)  # Display data as a table

    # Gestion des erreurs pour la transformation des colonnes
    try:
        # Si la colonne GPI contient des listes d'objets, on va les aplatir et les transformer en colonnes séparées
        if 'GPI' in df_kobo.columns:
            gpi_data = df_kobo['GPI'].apply(lambda x: ', '.join([str(obj) if isinstance(obj, dict) else str(obj) for obj in x]) if isinstance(x, list) else x)
            df_kobo['GPI_Transformed'] = gpi_data
            df_kobo = df_kobo.drop(columns=['GPI'])

        # Si la colonne Sondage contient des listes d'objets
        if 'Sondage' in df_kobo.columns:
            sondage_data = df_kobo['Sondage'].apply(lambda x: ', '.join([str(obj) if isinstance(obj, dict) else str(obj) for obj in x]) if isinstance(x, list) else x)
            df_kobo['Sondage_Transformed'] = sondage_data
            df_kobo = df_kobo.drop(columns=['Sondage'])

        # Checking and processing GPS data
        if 'GPS' in df_kobo.columns:
            gps_split = df_kobo['GPS'].str.split(' ', expand=True)
            df_kobo[['Latitude', 'Longitude', 'Altitude', 'Other']] = gps_split.astype(float)

        # Convert the date column
        df_kobo["_submission_time"] = pd.to_datetime(df_kobo["_submission_time"])

        # Input for date selection
        date1 = st.sidebar.date_input("Choose start date")
        date2 = st.sidebar.date_input("Choose end date")

        # Convert date1 and date2 to datetime
        date1 = pd.to_datetime(date1)
        date2 = pd.to_datetime(date2) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        # Filter by date
        df_filtered = df_kobo[
            (df_kobo["_submission_time"] >= pd.to_datetime(date1)) & 
            (df_kobo["_submission_time"] <= pd.to_datetime(date2))
        ]

        # Sidebar for additional filters
        st.sidebar.header("Choose your filters:")
        filters = {
            "Identification/Province": st.sidebar.multiselect("Choose your Province", df_filtered["Identification/Province"].unique()),
            "Identification/Commune": st.sidebar.multiselect("Choose the commune", df_filtered["Identification/Commune"].unique()),
            "Identification/Adresse_PDV": st.sidebar.multiselect("Choose the avenue", df_filtered["Identification/Adresse_PDV"].unique()),
            "Name_Agent": st.sidebar.multiselect("Choose Name and Surname", df_filtered["Name_Agent"].unique())
        }

        for col, selection in filters.items():
            if selection:
                df_filtered = df_filtered[df_filtered[col].isin(selection)]

        with st.expander("ANALYTICS"):
            a1, a2 = st.columns(2)
            # Calculate the sum of the PVT column
            total_price = df_filtered['Sondage/PVT'].astype(float).sum() if 'Sondage/PVT' in df_filtered.columns else 0
            num_rows = len(df_filtered)
            a1.metric(label="Number of PDVs", value=num_rows, help=f"Total Price: {total_price}", delta=total_price)
            a2.metric(label="Total Price", value=total_price, help=f"Total Price: {total_price}", delta=total_price)

        # Sélection des colonnes
        columns = st.multiselect("Select the columns you wish to include in the downloaded file:", 
                                 options=df_kobo.columns.tolist(), 
                                 default=df_kobo.columns.tolist())

        df_final = df_filtered[columns]
        st.subheader("Filtered data")
        st.dataframe(df_final, use_container_width=True)

        # Graphes
        col1, col2 = st.columns(2)
        with col1:
            fig2 = go.Figure(
                data=[go.Bar(x=df_filtered['Sondage/Sorte_caracteristic'], y=df_filtered['Sondage/PVT'].astype(float))],
                layout=go.Layout(title=go.layout.Title(text="BUSINESS TYPE BY QUANTITY"))
            )
            st.plotly_chart(fig2)

        with col2:
            st.plotly_chart(px.histogram(df_filtered, x='Sondage/QT', title="Quantity Histogram"))

    except KeyError as ke:
        st.error(f"L'application est en cours de construction. Veuillez nous excuser pour l'erreur: {ke}. Ce problème ne sera pas long à résoudre.")
    except Exception as e:
        st.error(f"L'application est en cours de construction. Veuillez nous excuser pour l'erreur: {e}. Nous travaillons à la résolution.")

else:
    st.warning("No data available.")
