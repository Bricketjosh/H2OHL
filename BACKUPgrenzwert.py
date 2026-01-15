import datetime
from urllib.error import URLError

import altair as alt
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


@st.cache_data
def get_limit_values():
    # Load limit values (Grenzwerte) from CSV
    df = pd.read_csv(
        "https://raw.githubusercontent.com/Bricketjosh/H2OHL/main/Grenzwerte.csv",
        sep=";",
        decimal=",",
    )
    return df


def get_status_color(value, limit, tolerance=0.05):
    """
    Determine status color based on value and limit.
    Green: value < (limit - tolerance)
    Yellow: (limit - tolerance) <= value < limit
    Red: value >= limit
    Returns: 'green', 'yellow', or 'red'
    """
    if pd.isna(value) or pd.isna(limit):
        return None
    
    if value < (limit - tolerance):
        return "green"
    elif value < limit:
        return "yellow"
    else:
        return "red"
@st.cache_data
def get_stations():
    # parse decimal comma numbers correctly
    df = pd.read_csv(
        "https://raw.githubusercontent.com/Bricketjosh/H2OHL/main/Messpunkte.csv",
        sep=";",
        decimal=",",
    )

    return df


def get_measurements(number):
    # parse decimal comma numbers correctly
    df = pd.read_csv(
        f"https://raw.githubusercontent.com/Bricketjosh/H2OHL/main/Messwerte/{number}_Messwerte.csv",
        sep=";",
        decimal=",",
    )

    # Tag column is in DD-MM-YY format in the CSV; ensure correct parsing
    df["Tag"] = pd.to_datetime(df["Tag"], dayfirst=True)

    # Filter by requested station number (the function previously returned the whole dataset)
    # `number` may be passed as a string from the UI; try to convert to int first
    try:
        num = int(number)
    except Exception:
        num = number

    df = df[df["Nummer"] == num]

    # set datetime index and make sure it's sorted for label-based slicing
    df = df.set_index("Tag").sort_index()

    # Try to coerce measurement columns to numeric where possible so we can plot them
    # Keep text columns like 'Name' and 'Uhrzeit' as-is.
    for col in df.columns:
        if col not in ("Name", "Uhrzeit"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


st.image("UM_H2OHL_Logo.png", width=200)
st.title("H20HL - Wasserqualität im Großraum Lübeck")

st.image("logo-thl.jpg", width=100)
st.write(
    """H2OHL ist ein Studentenprojekt der Technischen Hochschule Lübeck 
    im Rahmen des Moduls Umweltmonitoring (WiSe 2025/26). \\
    Ziel ist es eine Monitoring- App zu entwickeln, die bereitgestellte \\
    Daten über die Wasserqualität der verschiedenen Gewässer im Großraum \\
    Lübeck sammeln, bündeln und darstellen soll. \\
    \\
    Beteiligte Studenten: Joshua S. & Alisa R. \\
    \\
    H2OHL ist immer noch WIP! \\
    \\
    \\
    \\
    Datenquellen: \\
        WIP! [Lübecker Kreisverband der Sportfischer e.V.] (www.angeln-in-luebeck.de) \\
        Datenherausgeber: [Günter Werner / Thomas Kramp] \\
        \\
        WIP! [Labor Prof. Dr. Külls] (Homepage einfügen) \\
        Datenherausgeber: [Einfügen] \\
        \\
        WIP! [Labor Prof. Dr. Heymann] (Homepage einfügen) \\
        Datenherausgeber: [Einfügen] \\
        \\
        WIP! [Entsorgungsbetriebe Lübeck - Klärwerke] (Homepage einfügen) \\
        Datenherausgeber: [Einfügen] \\
        \\
    Datenlizenz: (Einfügen)"""  # noqa: E501
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

# Create a color mapping for different sources
color_palette = [
    "red", "blue", "green", "purple", "orange", "darkred", 
    "lightred", "darkblue", "darkgreen", "cadetblue", "darkpurple"
]
unique_sources = stations["Quelle"].unique()
source_color_map = {source: color_palette[i % len(color_palette)] for i, source in enumerate(unique_sources)}

for _, row in stations.iterrows():
    popup_text = f"""<b>{row['Name']}</b><br>
    Nummer: {row['Nummer']}<br>
    Quelle: {row['Quelle']}<br>
    Gewässer: {row['Gewässer']}<br>
    <strong>STATION_{int(row['Nummer'])}</strong>"""
    
    marker_color = source_color_map[row["Quelle"]]
    
    folium.Marker(
        [row["Breitengrad"], row["Längengrad"]],
        popup=folium.Popup(popup_text, max_width=250),
        tooltip=f"{row['Name']} (Nummer {row['Nummer']})",
        icon=folium.Icon(icon="tint", color=marker_color),
    ).add_to(map)

map_data = st_folium(
    map,
    height=400,
    returned_objects=["last_object_clicked_popup"],
    use_container_width=True,
)

try:
    if map_data is None or map_data.get("last_object_clicked_popup") is None:
        st.info("Bitte Messpunkt wählen")
        st.stop()
    
    popup_content = map_data["last_object_clicked_popup"]
    
    # Extract station number from popup text using the STATION_XXX marker
    import re
    match = re.search(r'STATION_(\d+)', popup_content)
    if not match:
        st.error("Stationsnummer konnte nicht extrahiert werden")
        st.stop()
    
    number = int(match.group(1))
except Exception as e:
    st.error(f"Fehler beim Lesen der Stationsdaten: {str(e)}")
    st.stop()

try:
    measurements = get_measurements(number)
except URLError as error:
    st.error(f"Messwerte konnten nicht geladen werden: {error.reason}")
    st.stop()
except Exception:
    st.error("Messwerte konnten nicht geladen werden")
    st.stop()

try:
    # Dropdown für Zeitraum-Auswahl
    time_option = st.selectbox(
        "Zeitraum auswählen",
        ["Gesamtzeitraum", "Letzte 365 Tage", "2025", "2024", "2023", "2022", "Benutzerdefiniert"]
    )
    
    end = datetime.datetime.today()
    
    if time_option == "Gesamtzeitraum":
        # Nutze min und max Daten aus den Messungen
        start = measurements.index.min().to_pydatetime()
        end = measurements.index.max().to_pydatetime()
    elif time_option == "Letzte 365 Tage":
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

# Convert start/end to timestamps (works for both date and datetime objects) and slice
start_ts = pd.to_datetime(start, dayfirst=True)
end_ts = pd.to_datetime(end, dayfirst=True)

# Measurements now already filtered to the chosen station in get_measurements
# Use a boolean mask for the date range. This works even if the DatetimeIndex
# is not strictly monotonic and is more robust than label-based slicing.
mask = (measurements.index >= start_ts) & (measurements.index <= end_ts)
filtered = measurements.loc[mask].reset_index()

if not filtered.shape[0]:
    # don't stop the app — we still want to show a chart even when there are no
    # measurements in the chosen timeframe. Show a short message instead.
    st.info("Keine Messwerte im gewählten Zeitraum — zeige leeres Diagramm")

# Make sure the time column is available for charting — reset_index() created
# a 'Tag' column, rename it to 'Zeit' to match UI text
if "Tag" in filtered.columns:
    filtered = filtered.rename(columns={"Tag": "Zeit"})

# Build a list of numeric measurement columns we can plot.
# Exclude columns that are not measurement values.
exclude_cols = {"Nummer", "Breitengrad", "Längengrad", "Quelle", "Gewässer"}
numeric_candidates = [
    c for c in measurements.select_dtypes(include="number").columns if c not in exclude_cols
]

if not numeric_candidates:
    st.error("Keine numerischen Messwerte zum Anzeigen gefunden")
    st.stop()

# Dropdown zum Auswählen des Messwerts
measurement_choice = st.selectbox("Messwert auswählen", numeric_candidates, index=0)

# Load limit values and check if selected measurement has a limit
try:
    limit_values = get_limit_values()
    limit_row = limit_values[limit_values["Messwert"] == measurement_choice]
    
    if not limit_row.empty:
        limit = limit_row.iloc[0]["Grenzwert"]
        cas_nr = limit_row.iloc[0]["CAS-Nr"]
        
        # Display limit information
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Grenzwert", f"{limit}")
        with col2:
            st.metric("CAS-Nr.", cas_nr if pd.notna(cas_nr) and cas_nr != "" else "N/A")
        
        # Get the latest measurement value and show its status
        if measurement_choice in filtered.columns and not filtered.empty:
            latest_value = filtered[measurement_choice].iloc[-1]
            tolerance = 0.05
            status_color = get_status_color(latest_value, limit, tolerance)
            
            if status_color == "green":
                color_display = "🟢 Grün (OK)"
                background_color = "#00FF00"
            elif status_color == "yellow":
                color_display = "🟡 Gelb (Warnung)"
                background_color = "#FFFF00"
            else:  # red
                color_display = "🔴 Rot (Grenzwert erreicht/überschritten)"
                background_color = "#FF0000"
            
            st.markdown(f"**Neuester Messwert: {latest_value:.4f} | Status: {color_display}**")
    else:
        st.info(f"Keine Grenzwerte für '{measurement_choice}' definiert")
except Exception as e:
    st.warning(f"Grenzwerte konnten nicht geladen werden: {str(e)}")

# Ensure the selected column exists in 'filtered' (might be empty) — if not present
# try to add it (will produce NaN rows) so the chart is always renderable.
if measurement_choice not in filtered.columns:
    filtered[measurement_choice] = pd.Series(dtype="float64")

# Create main chart with primary X-axis (Zeit) and Y-axis (measurement values)
chart = (
    alt.Chart(filtered)
    .mark_line(point=True, tooltip=True)
    .encode(
        x=alt.X("Zeit:T", title="Zeit"),
        y=alt.Y(f"{measurement_choice}:Q", title=measurement_choice),
        tooltip=["Zeit:T", "Uhrzeit:N", f"{measurement_choice}:Q"]
    )
)

st.altair_chart(chart, use_container_width=True)
