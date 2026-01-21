import datetime
from urllib.error import URLError

import altair as alt
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


def get_limit_values():
    # Load limit values (Grenzwerte) from CSV
    df = pd.read_csv(
        "https://raw.githubusercontent.com/Bricketjosh/H2OHL/refs/heads/main/Messwerte/Grenzwerte.csv",
        sep=";",
        decimal=",",
    )
    # Strip whitespace from column names and values
    df.columns = df.columns.str.strip()
    if "Messwert" in df.columns:
        df["Messwert"] = df["Messwert"].str.strip()
        # Clean measurement names to match cleaned column names
        import re
        df["Messwert_cleaned"] = df["Messwert"].apply(
            lambda x: x.replace('[', '_').replace(']', '').replace('°', 'deg').replace('/', '_')
                      .replace(' ', '_') if pd.notna(x) else x
        ).apply(lambda x: re.sub(r'_+', '_', x).strip('_') if pd.notna(x) else x)
    return df


def extract_unit(column_name):
    """
    Extract unit from column name with proper formatting.
    Supports both formats:
    - Bracket format: 'Temperatur Wasser [°C]' -> '°C'
    - Underscore format: 'Temp_Wasser_°C' -> '°C'
    """
    # First, try to extract from bracket format: [unit]
    import re
    bracket_match = re.search(r'\[([^\]]+)\]', column_name)
    if bracket_match:
        return bracket_match.group(1)
    
    # Fall back to underscore format
    if '_' in column_name:
        unit = column_name.split('_', 1)[1]  # Get everything after first underscore
        
        # Handle temperature columns - just return °C
        if column_name.startswith('Temp_'):
            return "°C"
        
        # Handle concentration columns - standardize to mg/L
        if unit.endswith('mg/l'):
            return "mg/L"
        if 'mg/L' in unit:
            # For cases like NH4_mg/L, NO2_mg/L, NO3_mg/L - just return mg/L
            return "mg/L"
        if unit == 'ortho_PO4':
            return "mg/L"
        
        return unit
    return ""


def format_value_with_unit(value, column_name):
    """
    Format value to match CSV display format.
    E.g., 13.30000 becomes '13,3'
    """
    if pd.isna(value):
        return "N/A"
    
    # Format the numeric value
    formatted = f"{value:.5f}".rstrip('0').rstrip('.')
    formatted = formatted.replace('.', ',')
    
    return formatted


def format_limit_value(value):
    """
    Format limit value to match CSV display format (remove trailing zeros).
    E.g., 13.30000 becomes 13,3 (with comma as decimal separator in German format)
    """
    if pd.isna(value):
        return "N/A"
    
    # Convert to string with appropriate precision, then remove trailing zeros
    formatted = f"{value:.5f}".rstrip('0').rstrip('.')
    # Replace dot with comma for German decimal format
    formatted = formatted.replace('.', ',')
    return formatted


def get_status_color(value, limit, tolerance=0.05, measurement_name=None):
    """
    Determine status color based on value and limit.
    
    For most parameters (e.g., pollutants):
    - Green: value < (limit - tolerance)
    - Yellow: (limit - tolerance) <= value < limit
    - Red: value >= limit
    
    For oxygen saturation (Sauerstoffsättigung):
    - Green: value > (limit + tolerance)
    - Yellow: limit < value <= (limit + tolerance)
    - Red: value <= limit
    
    Args:
        value: The measured value
        limit: The limit value
        tolerance: Tolerance factor (default 0.05)
        measurement_name: Name of the measurement to determine if special logic applies
    
    Returns: 'green', 'yellow', or 'red'
    """
    if pd.isna(value) or pd.isna(limit):
        return None
    
    # Special logic for oxygen saturation - lower values are bad
    if measurement_name and "Sauerstoffsättigung" in measurement_name:
        if value > (limit + tolerance):
            return "green"
        elif value > limit:
            return "yellow"
        else:
            return "red"
    else:
        # Default logic - higher values are bad
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
    
    # Strip whitespace from column names
    df.columns = df.columns.str.strip()

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
    
    # Create a mapping of cleaned column names to original names for later reference
    # This is done AFTER filtering and processing the data
    column_mapping = {}
    cleaned_columns = {}
    
    import re
    for col in df.columns:
        # Store original name
        original_col = col
        # Clean the column name: replace special characters but keep the unit information
        # Replace brackets with underscores and clean up special characters
        cleaned = col.replace('[', '_').replace(']', '').replace('°', 'deg').replace('/', '_')
        cleaned = cleaned.replace(' ', '_')  # Replace spaces with underscores
        # Remove multiple consecutive underscores
        cleaned = re.sub(r'_+', '_', cleaned).strip('_')
        cleaned_columns[col] = cleaned
        column_mapping[cleaned] = original_col
    
    # Rename columns to cleaned versions
    df = df.rename(columns=cleaned_columns)
    
    # Store the column mapping in the dataframe for later use
    df.attrs['column_mapping'] = column_mapping
    df.attrs['cleaned_columns'] = cleaned_columns
    
    return df


# Header with logo and title side by side - fixed width container, left-aligned
st.markdown("""
<div style="max-width: 1000px; margin: 0;">
    <div style="display: flex; align-items: flex-start; gap: 20px;">
        <div style="flex-shrink: 0;">
            <img src="https://raw.githubusercontent.com/Bricketjosh/H2OHL/refs/heads/main/UM_H2OHL_Logo.png" width="200" style="pointer-events: none; display: block;">
        </div>
        <div style="flex: 1;">
            <h1 style="margin-top: 0; margin-bottom: 0;">H2OHL - Wasserqualität im Großraum Lübeck</h1>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")
st.write("")

# Partner logos in white box with black border - fixed width container, left-aligned
st.markdown("""
<div style="max-width: 900px; margin: 0;">
    <div style="background-color: white; border: 2px solid black; padding: 5px 10px; border-radius: 5px; display: flex; align-items: center; justify-content: space-around; gap: 10px;">
        <a href="https://www.th-luebeck.de/" target="_blank" style="text-decoration: none; flex: 0 0 120px; display: flex; justify-content: center;">
            <img src="https://raw.githubusercontent.com/Bricketjosh/H2OHL/refs/heads/main/Logo_TH.svg.png" width="120" style="pointer-events: auto; display: block;">
        </a>
        <a href="https://www.luebeck.de/de/index.html" target="_blank" style="text-decoration: none; flex: 0 0 175px; display: flex; justify-content: center;">
            <img src="https://raw.githubusercontent.com/Bricketjosh/H2OHL/refs/heads/main/Logo_HL.svg" width="175" style="pointer-events: auto; display: block;">
        </a>
        <a href="https://www.swhl.de/?srsltid=AfmBOoqaZwfb0rqO_kz1y9aCzFmow-wBsqZvHMM13Zp2cpyy06I9_PYW" target="_blank" style="text-decoration: none; flex: 0 0 120px; display: flex; justify-content: center;">
            <img src="https://raw.githubusercontent.com/Bricketjosh/H2OHL/refs/heads/main/Logo_SW.webp" width="120" style="pointer-events: auto; display: block;">
        </a>
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")
st.write("")

st.write(
    """H2OHL ist ein Studentenprojekt der Technischen Hochschule Lübeck 
    im Rahmen des Moduls Umweltmonitoring (WiSe 2025/26). \\
    Ziel ist es eine Monitoring- App zu entwickeln, die bereitgestellte \\
    Daten über die Wasserqualität der verschiedenen Gewässer im Großraum \\
    Lübeck sammeln, bündeln und darstellen soll. \\
    \\
    Beteiligte Studenten: Joshua S. & Alisa R. \\
    \\
    Das Modul Umweltmonitoring (WiSe 2025/26) steht unter Aufsicht von \\
    Vertretern der Technischen Hochschule Lübeck, der Hansestadt Lübeck und der \\
    Stadtwerke Lübeck.
    \\
    \\
    \\
    \\
    **Datenquellen:** \\
    \\
        [Lübecker Kreisverband der Sportfischer e.V.] (www.angeln-in-luebeck.de) \\
        Datenherausgeber: [Günter Werner / Thomas Kramp] \\
        \\
        [Labor Prof. Dr. Heymann] [TH-Lübeck] (Homepage einfügen) \\
        Datenherausgeber: [Einfügen] \\
        \\
    Datenlizenz: (Einfügen)"""  # noqa: E501
)

st.write("")
st.write("")

st.markdown(
    """<p style='color: red;'>
    <strong>H2OHL ist immer noch WIP!</strong><br><br>
    </p>""",
    unsafe_allow_html=True
)

# Changelog section (collapsible with hierarchical structure: Year > Month > Day)
with st.expander("📋 Changelog", expanded=False):
    with st.expander("📅 2026", expanded=False):
        with st.expander("Januar", expanded=False):
            with st.expander("21.01.2026", expanded=False):
                st.markdown("""
                - Sauerstoffsättigung-Grenzwertlogik angepasst: Werte unter Grenzwert werden als kritisch markiert
                """)
            
            with st.expander("16.01.2026", expanded=False):
                st.markdown("""
                - Header-Layout überarbeitet: Logo und Titel nebeneinander angeordnet
                - Partner-Logos in weißer Box mit schwarzem Rahmen hinzugefügt (TH Lübeck, HL, Stadtwerke)
                - Kontextinformationen-Sektion hinzugefügt (Messwert, CAS-Nr., Grenzwert, Kontextinfo)
                - Kontextinfo-Darstellung optimiert: Label und Text in separaten Zeilen
                - Trennlinie (schwarz/weiß) zwischen Header und Karte eingefügt
                - Info-Tooltips zu Download-Buttons ergänzt
                - Diagramm-Export als HTML implementiert
                - Changelog mit hierarchischer Struktur (Jahr → Monat → Tag) erweitert
                """)
            
            with st.expander("15.01.2026", expanded=False):
                st.markdown("""
                - WIP-Status-Hinweis farblich hervorgehoben (rot)
                - CSV-Download-Funktionalität erweitert (Gesamtzeitraum + ausgewählter Zeitraum)
                - Diagramm-Export-Funktion hinzugefügt
                - Grenzwert-Handling und Formatierungsfunktionen implementiert
                - Zeitauswahl-Logik verbessert (Jahresauswahl, benutzerdefiniert)
                - Textformatierung und Leerzeichen-Handling optimiert
                - Unit-Extraktion aus Spaltennamen verbessert
                - OpenData-Nutzungshinweise ergänzt
                - Tabellenansicht-Tooltip im Diagramm-Bereich hinzugefügt
                """)
    
    st.markdown("""
    <div style="margin-top: 15px; padding: 10px; background-color: #f0f0f0; border-radius: 5px; font-size: 0.85em; color: black;">
        <strong>Version:</strong> WiSe 2025/26 (Work in Progress)<br>
        <strong>Letzte Aktualisierung:</strong> 21.01.2026
    </div>
    """, unsafe_allow_html=True)

# Dual color separator bars (black and white)
st.markdown("""
<div style="display: flex; flex-direction: column; margin: 20px 0;">
    <div style="height: 2px; background-color: black;"></div>
    <div style="height: 2px; background-color: white;"></div>
</div>
""", unsafe_allow_html=True)

st.subheader("Interaktive Karte")

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
    # Ermittele verfügbare Jahre aus den Messdaten
    available_years = sorted(measurements.index.year.unique(), reverse=True)
    
    # Erstelle die Dropdown-Optionen: feste Optionen + dynamische Jahre
    time_options = ["Gesamtzeitraum", "Letzte 365 Tage"] + [str(year) for year in available_years] + ["Benutzerdefiniert"]
    
    # Dropdown für Zeitraum-Auswahl
    time_option = st.selectbox(
        "Zeitraum auswählen",
        time_options
    )
    
    end = datetime.datetime.today()
    
    if time_option == "Gesamtzeitraum":
        # Nutze min und max Daten aus den Messungen
        start = measurements.index.min().to_pydatetime()
        end = measurements.index.max().to_pydatetime()
    elif time_option == "Letzte 365 Tage":
        start = end - datetime.timedelta(days=365)
    elif time_option == "Benutzerdefiniert":
        start, end = st.date_input("Zeitraum", (end - datetime.timedelta(days=365), end), format="DD.MM.YYYY")
    else:
        # Es handelt sich um eine Jahresauswahl
        try:
            selected_year = int(time_option)
            start = datetime.datetime(selected_year, 1, 1)
            end = datetime.datetime(selected_year, 12, 31)
        except ValueError:
            st.error(f"Ungültiges Jahr: {time_option}")
            st.stop()
        
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
exclude_cols = {"Nummer", "Breitengrad", "Längengrad", "Quelle", "Gewässer", "Bemerkung"}
numeric_candidates = [
    c for c in measurements.select_dtypes(include="number").columns if c not in exclude_cols
]

if not numeric_candidates:
    st.error("Keine numerischen Messwerte zum Anzeigen gefunden")
    st.stop()

# Get the original column names for display
column_mapping = measurements.attrs.get('column_mapping', {})
# Create display names by reversing the mapping
display_names = {cleaned: column_mapping.get(cleaned, cleaned) for cleaned in numeric_candidates}

# Dropdown zum Auswählen des Messwerts (show original names)
measurement_choice_display = st.selectbox(
    "Messwert auswählen", 
    options=list(display_names.values()),
    index=0
)

# Get the cleaned column name from the display name
measurement_choice = [k for k, v in display_names.items() if v == measurement_choice_display][0]

# Load limit values and check if selected measurement has a limit
try:
    limit_values = get_limit_values()
    limit_row = limit_values[limit_values["Messwert_cleaned"] == measurement_choice]
    
    if not limit_row.empty:
        limit = limit_row.iloc[0]["Grenzwert"]
        cas_nr = limit_row.iloc[0]["CAS-Nr"]
        
        # Display limit information
        st.write("")
        st.write("")
        st.subheader("Grenzwerte")
        st.info("💡 Die Grenzwertanzeige hat noch KEINE Aussagekraft, da die tatsächlichen Werte noch nicht recherchiert und eingefügt wurden!.")
        col1, col2, col3 = st.columns(3)
        with col1:
            # Extract unit from the original column name
            unit = extract_unit(measurement_choice_display)
            st.metric("Grenzwert", f"{format_limit_value(limit)} {unit}" if unit else format_limit_value(limit))
        with col2:
            st.metric("CAS-Nr.", cas_nr if pd.notna(cas_nr) and cas_nr != "" else "N/A")
        with col3:
            st.write("")  # Platzhalter für symmetrisches Layout
        
        # Get the latest measurement value and show its status
        if measurement_choice in filtered.columns and not filtered.empty:
            latest_value = filtered[measurement_choice].iloc[-1]
            tolerance = 0.05
            status_color = get_status_color(latest_value, limit, tolerance, measurement_choice_display)
            
            if status_color == "green":
                color_display = "🟢 Grün (OK)"
                background_color = "#00FF00"
            elif status_color == "yellow":
                color_display = "🟡 Gelb (Warnung)"
                background_color = "#FFFF00"
            else:  # red
                color_display = "🔴 Rot (Grenzwert erreicht/überschritten)"
                background_color = "#FF0000"
            
            unit = extract_unit(measurement_choice_display)
            value_display = f"{format_value_with_unit(latest_value, measurement_choice_display)} {unit}" if unit else format_value_with_unit(latest_value, measurement_choice_display)
            st.markdown(f"**Neuester Messwert: {value_display} | Status: {color_display}**")
    else:
        st.info(f"Keine Grenzwerte für '{measurement_choice}' definiert")
except Exception as e:
    st.warning(f"Grenzwerte konnten nicht geladen werden: {str(e)}")

# Chart section with header
st.write("")
st.write("")
st.subheader("Diagramm/Tabelle")
st.info("💡 Oben rechts in der Ecke des Diagramms kann man zwischen **Diagramm- und Tabellenansicht** wechseln. Außerdem kann man dort auch beides im **Fullscreen** anzeigen lassen. Fahre mit der Maus über die Datenpunkte im Graphen, um zusätzliche Infos in einem Tooltip anzeigen zu lassen.")

# Ensure the selected column exists in 'filtered' (might be empty) — if not present
# try to add it (will produce NaN rows) so the chart is always renderable.
if measurement_choice not in filtered.columns:
    filtered[measurement_choice] = pd.Series(dtype="float64")

# Check if there are any non-null values to plot
if filtered[measurement_choice].notna().sum() == 0:
    st.warning(f"⚠️ Keine Daten für '{measurement_choice}' im gewählten Zeitraum vorhanden.")
    st.stop()

# Create a display column for the selected measurement
filtered[f"{measurement_choice}_display"] = filtered[measurement_choice].apply(
    lambda x: format_value_with_unit(x, measurement_choice_display)
)

# Create a cleaned Bemerkung column that shows "N/A" instead of null
if "Bemerkung" in filtered.columns:
    filtered["Bemerkung_display"] = filtered["Bemerkung"].apply(
        lambda x: x if pd.notna(x) and str(x).strip() != "" else "N/A"
    )

# Add limit and status information to tooltip if limit exists
limit = None
try:
    limit_values = get_limit_values()
    limit_row = limit_values[limit_values["Messwert_cleaned"] == measurement_choice]
    if not limit_row.empty:
        limit = limit_row.iloc[0]["Grenzwert"]
except Exception:
    pass

if limit is not None:
    # Create columns for limit display and status
    unit = extract_unit(measurement_choice_display)
    filtered["Grenzwert"] = f"{format_limit_value(limit)} {unit}".strip() if unit else format_limit_value(limit)
    
    # Create status column
    def get_status_display(value):
        status_color = get_status_color(value, limit, tolerance=0.05, measurement_name=measurement_choice_display)
        if status_color == "green":
            return "🟢 OK"
        elif status_color == "yellow":
            return "🟡 Warnung"
        else:
            return "🔴 Grenzwert überschritten"
    
    filtered["Status"] = filtered[measurement_choice].apply(get_status_display)
    
    # Create tooltip list based on measurement type
    # For Sichttiefe, add Bemerkung column
    tooltip_list = [
        alt.Tooltip("Zeit:T", title="Zeit"), 
        alt.Tooltip("Uhrzeit:N", title="Uhrzeit"),
        alt.Tooltip(f"{measurement_choice}_display:N", title=measurement_choice_display)
    ]
    
    # Check if this is Sichttiefe (cleaned name would be "Sichttiefe_m")
    if "Sichttiefe" in measurement_choice and "Bemerkung_display" in filtered.columns:
        tooltip_list.append(alt.Tooltip("Bemerkung_display:N", title="Bemerkung"))
    
    tooltip_list.extend([
        alt.Tooltip("Grenzwert:N", title="Grenzwert"), 
        alt.Tooltip("Status:N", title="Status")
    ])
    
    # Create main chart with primary X-axis (Zeit) and Y-axis (measurement values)
    # Now using cleaned column names without special characters
    chart = (
        alt.Chart(filtered)
        .mark_line(point=True)
        .encode(
            x=alt.X("Zeit:T", title="Zeit [Intervall]", axis=alt.Axis(format="%d.%m.%Y")),
            y=alt.Y(f"{measurement_choice}:Q", title=measurement_choice_display),
            tooltip=tooltip_list
        )
    )
else:
    # Create tooltip list based on measurement type
    # For Sichttiefe, add Bemerkung column
    tooltip_list = [
        alt.Tooltip("Zeit:T", title="Zeit"), 
        alt.Tooltip("Uhrzeit:N", title="Uhrzeit"),
        alt.Tooltip(f"{measurement_choice}_display:N", title=measurement_choice_display)
    ]
    
    # Check if this is Sichttiefe (cleaned name would be "Sichttiefe_m")
    if "Sichttiefe" in measurement_choice and "Bemerkung_display" in filtered.columns:
        tooltip_list.append(alt.Tooltip("Bemerkung_display:N", title="Bemerkung"))
    
    # Create main chart without limit/status if no limit defined
    # Now using cleaned column names without special characters
    chart = (
        alt.Chart(filtered)
        .mark_line(point=True)
        .encode(
            x=alt.X("Zeit:T", title="Zeit [Intervall]", axis=alt.Axis(format="%d.%m.%Y")),
            y=alt.Y(f"{measurement_choice}:Q", title=measurement_choice_display),
            tooltip=tooltip_list
        )
    )

st.altair_chart(chart, use_container_width=True)

# Context information section
st.write("")
st.write("")
st.subheader("Kontextinformationen")

# Load infobox data
try:
    infobox_df = pd.read_csv(
        "https://raw.githubusercontent.com/Bricketjosh/H2OHL/refs/heads/main/Infobox_Messwerte.csv",
        sep=";",
        decimal=",",
    )
    infobox_df.columns = infobox_df.columns.str.strip()
    
    # Find matching row for selected measurement
    matching_row = infobox_df[infobox_df["Messwert"] == measurement_choice_display]
    
    if not matching_row.empty:
        row_data = matching_row.iloc[0]
        
        # First row: Messwert (full width)
        st.write(f"**Messwert:** {measurement_choice_display}")
        
        # Second row: CAS-Nr and Grenzwert in columns
        col1, col2 = st.columns(2)
        
        with col1:
            if pd.notna(row_data.get("CAS-Nr")) and row_data.get("CAS-Nr") != "":
                st.write(f"**CAS-Nr:** {row_data.get('CAS-Nr')}")
            else:
                st.write("**CAS-Nr:** -")
        
        with col2:
            if pd.notna(row_data.get("Grenzwert")) and row_data.get("Grenzwert") != "":
                st.write(f"**Grenzwert:** {row_data.get('Grenzwert')}")
            else:
                st.write("**Grenzwert:** -")
        
        st.write("")  # Leerzeile zwischen CAS-Nr./Grenzwert und Kontextinfo
        
        # Third row: Kontextinfo (full width)
        if "Kontextinfo" in infobox_df.columns:
            if pd.notna(row_data.get("Kontextinfo")) and row_data.get("Kontextinfo") != "":
                st.write("**Kontextinfo:**")
                st.write(row_data.get('Kontextinfo'))
    else:
        st.info(f"Keine Kontextinformationen für '{measurement_choice_display}' verfügbar.")
except Exception as e:
    st.warning(f"Kontextinformationen konnten nicht geladen werden: {str(e)}")

# Downloads section
st.write("")
st.write("")
st.subheader("Downloads")
st.info("💡 Bitte die Tooltips beachten, die erscheinen, wenn man mit der Maus über die Knöpfe fährt.")

# Download buttons for CSV files
try:
    csv_url = f"https://raw.githubusercontent.com/Bricketjosh/H2OHL/main/Messwerte/{number}_Messwerte.csv"
    csv_data = pd.read_csv(csv_url, sep=";", decimal=",")
    csv_string = csv_data.to_csv(index=False, sep=";", decimal=",")
    st.download_button(
        label="📥 CSV Download - Alle Messpunktwerte",
        data=csv_string,
        file_name=f"Station_{number}_Messwerte.csv",
        mime="text/csv",
        help="Komplette CSV-Datei herunterladen"
    )
    
    # Download button for filtered CSV (selected time range)
    csv_data_filtered = csv_data.copy()
    csv_data_filtered['Tag'] = pd.to_datetime(csv_data_filtered['Tag'], dayfirst=True)
    mask_download = (csv_data_filtered['Tag'] >= start_ts) & (csv_data_filtered['Tag'] <= end_ts)
    csv_data_filtered = csv_data_filtered[mask_download]
    csv_data_filtered['Tag'] = csv_data_filtered['Tag'].dt.strftime('%d-%m-%y')
    csv_string_filtered = csv_data_filtered.to_csv(index=False, sep=";", decimal=",")
    st.download_button(
        label="📥 CSV Download - Messpunktwerte des Zeitraums",
        data=csv_string_filtered,
        file_name=f"Station_{number}_Messwerte_{start_ts.strftime('%Y%m%d')}-{end_ts.strftime('%Y%m%d')}.csv",
        mime="text/csv",
        help=f"CSV-Datei für Zeitraum {start_ts.strftime('%d.%m.%Y')} - {end_ts.strftime('%d.%m.%Y')}"
    )
except Exception:
    pass

# Download button for the chart
try:
    # Create a higher resolution version for export
    chart_export = chart.properties(
        width=1200,
        height=600,
        title={
            "text": f"Station {number} - {measurement_choice_display}",
            "subtitle": f"Zeitraum: {start_ts.strftime('%d.%m.%Y')} - {end_ts.strftime('%d.%m.%Y')}"
        }
    ).configure_axis(
        labelFontSize=14,
        titleFontSize=16
    ).configure_title(
        fontSize=18,
        subtitleFontSize=14
    )
    
    # Export as HTML with embedded Vega-Lite spec (can be opened in browser and saved as image)
    html_string = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
        <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
        <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
    </head>
    <body>
        <div id="vis"></div>
        <script type="text/javascript">
            vegaEmbed('#vis', {chart_export.to_json()}, {{"actions": {{"export": true, "source": false, "editor": false}}}});
        </script>
    </body>
    </html>
    """
    
    st.download_button(
        label="📊 Diagramm als HTML herunterladen",
        data=html_string,
        file_name=f"Station_{number}_{measurement_choice}_{start_ts.strftime('%Y%m%d')}-{end_ts.strftime('%Y%m%d')}.html",
        mime="text/html",
        help="Diagramm als HTML herunterladen - öffnen Sie die Datei im Browser und nutzen Sie das ⋮-Menü rechts oben im Diagramm zum Export als PNG/SVG"
    )
except Exception as e:
    st.warning(f"Diagramm-Download konnte nicht erstellt werden: {str(e)}")

