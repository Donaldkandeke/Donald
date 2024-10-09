import streamlit as st
import pandas as pd
import requests
import folium
from folium.plugins import MarkerCluster, HeatMap, Draw, Fullscreen
from streamlit_folium import folium_static
import plotly.graph_objs as go
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

    # Convert the DataFrame to an Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_kobo.to_excel(writer, index=False)
    processed_data = output.getvalue()

    # Button to download the Excel file
    st.download_button(
        label="📥 Download data in Excel format",
        data=processed_data,
        file_name="collected_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # If the GPI column contains object lists, we will flatten them and turn them into separate columns
    if 'GPI' in df_kobo.columns:
        # Extract data from the GPI column
        gpi_data = df_kobo['GPI'].apply(lambda x: ', '.join([str(obj) if isinstance(obj, dict) else str(obj) for obj in x]) if isinstance(x, list) else x)
        df_kobo['GPI_Transformed'] = gpi_data  # Create a new column with the flattened data
        df_kobo = df_kobo.drop(columns=['GPI'])  # Remove the old GPI column

    # Séparer la colonne 'Sondage' en plusieurs colonnes
    sondage_split = df_kobo['Sondage'].str.split(' ', expand=True)

    # Vérifier combien de colonnes sont réellement créées
    num_columns = sondage_split.shape[1]
    st.write(f"Number of columns created by split: {num_columns}")

    # S'assurer qu'il y a exactement 4 colonnes, et remplir les valeurs manquantes si nécessaire
    if num_columns < 4:
        for i in range(4 - num_columns):
            sondage_split[num_columns + i] = None  # Ajouter des colonnes manquantes avec des valeurs vides

    # Renommer les colonnes avec des noms explicites
    df_kobo[['Sondage/Sorte_caracteristic', 'Sondage/PVU', 'Sondage/QT', 'Sondage/PVT']] = sondage_split.iloc[:, :4]

    # Convertir les colonnes pertinentes en type numérique (si applicable)
    df_kobo['Sondage/PVU'] = pd.to_numeric(df_kobo['Sondage/PVU'], errors='coerce')
    df_kobo['Sondage/QT'] = pd.to_numeric(df_kobo['Sondage/QT'], errors='coerce')
    df_kobo['Sondage/PVT'] = pd.to_numeric(df_kobo['Sondage/PVT'], errors='coerce')

    # Supprimer la colonne d'origine 'Sondage' si nécessaire
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

    # Convert date1 and date2 to datetime and ensure date2 covers the entire day
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
        # Calculate the total price
        num_rows = len(df_filtered)  # Use len() to get the total number of rows
        a1.metric(label="Number of PDVs", value=num_rows, help=f"Total Price: {total_price}", delta=total_price)
        a2.metric(label="Total Price", value=total_price, help=f"Total Price: {total_price}", delta=total_price)

    # Display the filtered data
    with st.expander("Filtered Data"):
        st.dataframe(df_filtered, use_container_width=True)

    # Convert the filtered DataFrame to an Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_filtered.to_excel(writer, index=False)
    processed_data = output.getvalue()

    # Button to download the filtered data in Excel format
    st.download_button(
        label="📥 Download filtered data in Excel format",
        data=processed_data,
        file_name="filtered_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


    # Vérifier si les coordonnées de latitude et de longitude contiennent des valeurs NaN
    if df_filtered['Latitude'].isnull().all() or \
       df_filtered['Longitude'].isnull().all():
        st.error("Les coordonnées de localisation sont toutes manquantes.")
    else:
        # Calculer les moyennes tout en ignorant les NaN
        latitude_mean = df_filtered['Latitude'].mean()
        longitude_mean = df_filtered['Longitude'].mean()

        # Créer une carte avec les coordonnées moyennes des points filtrés
        m = folium.Map(location=[latitude_mean, longitude_mean], zoom_start=4)

        # Ajouter des marqueurs avec des clusters
        marker_cluster = MarkerCluster().add_to(m)
        for i, row in df_filtered.iterrows():
            if pd.notnull(row['Latitude']) and \
               pd.notnull(row['Longitude']):
                popup_content = f"""
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
                <ul class="list-group">
                    <h3>Information of {row['Identification/Name_PDV']}</h3>
                    <hr class='bg-danger text-primary'>
                    <div style='width:400px;height:200px;margin:10px;color:gray;font-size:18px;'>
                        <li class="list-group-item"><b>Branch Identification/Type_PDV:</b> {row['Identification/Type_PDV']}</li>
                        <li class="list-group-item"><b>Province:</b> {row['Identification/Province']}</li>
                        <li class="list-group-item"><b>Commune:</b> {row['Identification/Commune']}</li>
                        <li class="list-group-item"><b>Point de vente:</b> {row['Identification/Adresse_PDV']}</li>
                    </div>
                </ul>
                """
                folium.Marker(
                    location=[row['Latitude'], row['Longitude']],
                    popup=popup_content,
                ).add_to(marker_cluster)

        # Utiliser st_folium pour afficher la carte
        folium_static(m)

