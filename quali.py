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
    \\
    \\
    Im Rahmen des NUtzens von OpenData, stellen wir die hier verwendeten Daten zur Verfügung.\\ 
    In der oberen rechten Ecke des Diagrams kann man zwischen Diagram- und Tabellenansicht\\
    umschalten und dort auch die dort angezeigten Daten herunterladen.\\
    \\
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
        WIP! [Labor Prof. Dr. Heymann] (Homepage einfügen) \\
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
        col1, col2, col3 = st.columns(3)
        with col1:
            # Extract unit from the original column name
            unit = extract_unit(measurement_choice_display)
            st.metric("Grenzwert", f"{format_limit_value(limit)} {unit}" if unit else format_limit_value(limit))
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
            
            unit = extract_unit(measurement_choice_display)
            value_display = f"{format_value_with_unit(latest_value, measurement_choice_display)} {unit}" if unit else format_value_with_unit(latest_value, measurement_choice_display)
            st.markdown(f"**Neuester Messwert: {value_display} | Status: {color_display}**")
    else:
        st.info(f"Keine Grenzwerte für '{measurement_choice}' definiert")
except Exception as e:
    st.warning(f"Grenzwerte konnten nicht geladen werden: {str(e)}")

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
        status_color = get_status_color(value, limit, tolerance=0.05)
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
            x=alt.X("Zeit:T", title="Zeit"),
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
            x=alt.X("Zeit:T", title="Zeit"),
            y=alt.Y(f"{measurement_choice}:Q", title=measurement_choice_display),
            tooltip=tooltip_list
        )
    )

st.altair_chart(chart, use_container_width=True)
