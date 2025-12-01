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
        "https://hsi-sh.de/pegel/od/pegel.csv",
        sep=";",
    )

    return df


def get_measurements(number):
    df = pd.read_csv(
        f"https://hsi-sh.de/pegel/download/{number}_Messwerte.csv",
        sep=";",
    )

    df["Zeit"] = pd.to_datetime(df["Zeit"])
    df = df.set_index("Zeit")
    return df


st.title("Wasserstände Schleswig-Holstein")

st.write(
    """Datenquelle: [Hochwasser-Sturmflut-Information Schleswig-Holstein](https://hsi-sh.de) \\
    Datenherausgeber: [Landesamt für Umwelt Schleswig-Holstein](https://www.schleswig-holstein.de/LFU) \\
    Datenlizenz: [Datenlizenz Deutschland Namensnennung 2.0](https://www.govdata.de/dl-de/by-2-0)"""  # noqa: E501
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
        [row["geogrBreite"], row["geogrLaenge"]],
        popup=f"{row['pegelName']} (Nummer {row['pegelNummer']})",
        tooltip=f"{row['pegelName']} (Nummer {row['pegelNummer']})",
        icon=folium.Icon(icon="tint"),
    ).add_to(map)

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
    st.info("Bitte Messstation wählen")
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
        y=alt.Y("wasserstand", title="Wasserstand"),
    )
)

st.altair_chart(chart, use_container_width=True)
