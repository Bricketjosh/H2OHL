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
    end = datetime.datetime.today()
    start = end - datetime.timedelta(days=365)
    start, end = st.date_input("Zeitraum", (start, end), format="DD.MM.YYYY")
except Exception:
    st.info("Bitte Start- und Enddatum wählen")
    st.stop()

try:
    measurements = get_measurements(number)
except URLError as error:
    st.error(f"Messwerte konnten nicht geladen werden: {error.reason}")
    st.stop()
except Exception:
    st.error("Messwerte konnten nicht geladen werden")
    st.stop()

filtered = measurements.Nummer[number]
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