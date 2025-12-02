import datetime
from urllib.error import URLError

import altair as alt
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


@st.cache_data
def get_stations():
    df = pd.read_csv(
        "https://raw.githubusercontent.com/Bricketjosh/H2OHL/refs/heads/main/Wakenitzdaten_ML.csv",
        sep=";",
    )

    return df


def get_measurements(number):
    df = pd.read_csv(
        f"https://raw.githubusercontent.com/Bricketjosh/H2OHL/refs/heads/main/Wakenitzdaten_ML.csv",
        sep=";",
    )

    df["Tag"] = pd.to_datetime(df["Tag"])
    df = df.set_index("Tag")
    return df


st.title("Wasserqualität Lübeck")

st.write(
    """Datenquelle: [Wakenitzgruppe](Homepage einfügen) \\
    Datenherausgeber: [Günter Werner] \\
    Datenlizenz:"""  # noqa: E501
)

try:
    stations = get_stations()
except URLError as error:
    st.error(f"Messstationen konnten nicht geladen werden: {error.reason}")
    st.stop()
except Exception:
    st.error("Messstationen konnten nicht geladen werden")
    st.stop()

map = folium.Map([53.8677, 10.68508], zoom_start=12)

for _, row in stations.iterrows():
    folium.Marker(
        [row["Breitengrad"], row["Längengrad"]],
        popup=f"{row['Name']} (Nummer {row['Nummer']})",
        tooltip=f"{row['Name']} (Nummer {row['Nummer']})",
        icon=folium.Icon(icon="tint"),
    ).add_to(map)
    print(row["Nummer"])
    print(row["Name"]) 

map_data = st_folium(
    map,
    height=400,
    returned_objects="last_object_clicked_popup",
    use_container_width=True,
)

try:
    popup = map_data["last_object_clicked_popup"]
    number = popup[popup.find(" (Nummer ") + 9 : -1]  # noqa: E203
except Exception:
    st.info("Bitte Messpunkt wählen")
    st.stop()

try:
    # Dropdown für Zeitraum-Auswahl
    time_option = st.selectbox(
        "Zeitraum auswählen",
        ["Letzte 365 Tage", "2025", "2024", "2023", "2022", "Benutzerdefiniert"]
    )
    
    end = datetime.datetime.today()
    
    if time_option == "Letzte 365 Tage":
        start = end - datetime.timedelta(days=365)
    elif time_option == "2025":
        start = datetime.datetime(2025, 1, 1)
        end = datetime.datetime(2025, 12, 31)
    elif time_option == "2024":
        start = datetime.datetime(2024, 1, 1)
        end = datetime.datetime(2024, 12, 31)
    elif time_option == "2023":
        start = datetime.datetime(2023, 1, 1)
        end = datetime.datetime(2023, 12, 31)
    elif time_option == "2022":
        start = datetime.datetime(2022, 1, 1)
        end = datetime.datetime(2022, 12, 31)
    else:  # Benutzerdefiniert
        start, end = st.date_input("Zeitraum", (end - datetime.timedelta(days=365), end), format="DD.MM.YYYY")
        
except Exception:
    st.info("Bitte Zeitraum wählen")
    st.stop()

try:
    measurements = get_measurements(number)
except URLError as error:
    st.error(f"Messwerte konnten nicht geladen werden: {error.reason}")
    st.stop()
except Exception:
    st.error("Messwerte konnten nicht geladen werden")
    st.stop()

# filtered = measurements.Nummer[number]
filtered = measurements.loc[start:end]
filtered = filtered.reset_index()

if not filtered.shape[0]:
    st.info("Keine Messwerte im gewählten Zeitraum")
    st.stop()

chart = (
    alt.Chart(filtered)
    .mark_line()
    .encode(
        x=alt.X("Zeit", title="Zeit"),
        y=alt.Y("Wasserqualität", title="Wasserqualität"),
    )
)

st.altair_chart(chart, use_container_width=True)