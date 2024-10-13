import streamlit as st
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static
import plotly.express as px
import io

# Page configuration
st.set_page_config(page_title="UNILEVER", page_icon="🌍", layout="wide")
st.header(":bar_chart: Unilever Dashboard")
st.markdown('<style>div.block-container{padding-top:2rem;}</style>', unsafe_allow_html=True)

# Setting up retries for HTTP requests
session = requests.Session()
retry = Retry(total=5, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount('https://', adapter)

# Caching data to avoid multiple API calls
@st.cache_data
def download_kobo_data(api_url, headers):
    try:
        response = session.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error while retrieving data: {e}")
        return None

# API URL and authentication key
api_url = "https://kf.kobotoolbox.org/api/v2/assets/amfgmGRANPdTQgh85J7YqK/data/?format=json"
headers = {"Authorization": "Token fd0239896ad338de0651fe082978bec82cc7dad4"}

# Downloading data from KoboCollect
data = download_kobo_data(api_url, headers)
if data:
    st.success("KoboCollect data retrieved successfully!")

    # Converting JSON data to DataFrame
    df_kobo = pd.json_normalize(data['results'])

    # Displaying raw data
    with st.expander("Raw Data"):
        st.dataframe(df_kobo)

    # Transforming GPI and Survey columns
    for col in ['GPI', 'Survey']:
        if col in df_kobo.columns:
            df_kobo[f'{col}_Transformed'] = df_kobo[col].apply(lambda x: ', '.join([str(obj) for obj in x]) if isinstance(x, list) else x)
            df_kobo.drop(columns=[col], inplace=True)

    # Processing GPS data
    if 'GPS' in df_kobo.columns:
        gps_split = df_kobo['GPS'].str.split(' ', expand=True)
        df_kobo[['Latitude', 'Longitude', 'Altitude', 'Other']] = gps_split.apply(pd.to_numeric, errors='coerce')

    # Converting submission time column to datetime
    df_kobo["_submission_time"] = pd.to_datetime(df_kobo["_submission_time"])

    # Date filtering
    date1 = st.sidebar.date_input("Choose a start date")
    date2 = st.sidebar.date_input("Choose an end date")

    date1 = pd.to_datetime(date1)
    date2 = pd.to_datetime(date2) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    df_filtered = df_kobo[(df_kobo["_submission_time"] >= date1) & (df_kobo["_submission_time"] <= date2)]

    # Additional filters
    st.sidebar.header("Additional Filters:")
    filters = {
        "Identification/Province": st.sidebar.multiselect("Province", df_filtered["Identification/Province"].unique()),
        "Identification/Commune": st.sidebar.multiselect("Commune", df_filtered["Identification/Commune"].unique()),
        "Identification/Address_PDV": st.sidebar.multiselect("Avenue", df_filtered["Identification/Address_PDV"].unique()),
        "Name_Agent": st.sidebar.multiselect("Agent", df_filtered["Name_Agent"].unique())
    }

    for col, selection in filters.items():
        if selection:
            df_filtered = df_filtered[df_filtered[col].isin(selection)]

    # Analytical block
    with st.expander("Analytics"):
        a1, a2 = st.columns(2)

        if 'Survey_Transformed' in df_filtered.columns:
            df_filtered['Survey/PVT'] = pd.to_numeric(df_filtered['Survey_Transformed'], errors='coerce')
            total_price = df_filtered['Survey/PVT'].sum()
            num_rows = len(df_filtered)
            a1.metric(label="Number of PDVs", value=num_rows)
            a2.metric(label="Total Price", value=total_price)
        else:
            st.error("The column 'Survey_Transformed' is missing.")

    # Selecting columns and downloading data
    columns = st.multiselect("Columns to include in the downloaded file", options=df_kobo.columns.tolist(), default=df_kobo.columns.tolist())
    df_final = df_filtered[columns]

    st.subheader("Filtered Data")
    st.dataframe(df_final, use_container_width=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_final.to_excel(writer, index=False)
    processed_data = output.getvalue()

    st.download_button(
        label="Download Filtered Data",
        data=processed_data,
        file_name="filtered_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Displaying the map
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
        st.warning("No valid GPS data available to display the map.")

    # Graphs
    col1, col2 = st.columns(2)

    with col1:
        if 'Identification/Type_PDV' in df_filtered.columns:
            st.subheader("Pie Chart Type_PDV")
            pie_chart_data = df_filtered['Identification/Type_PDV'].value_counts()
            fig = px.pie(pie_chart_data, values=pie_chart_data.values, names=pie_chart_data.index, title="Distribution by Type_PDV", hole=0.3)
            fig.update_traces(textinfo='value', textposition='inside')
            st.plotly_chart(fig)

    with col2:
        if 'Name_Agent' in df_filtered.columns:
            st.subheader("Bar Chart of Agents")
            bar_chart_data = df_filtered['Name_Agent'].value_counts()
            fig = px.bar(bar_chart_data, x=bar_chart_data.index, y=bar_chart_data.values, labels={"x": "Agent Name", "y": "Number of Occurrences"}, title="Number of Agents")
            st.plotly_chart(fig)
