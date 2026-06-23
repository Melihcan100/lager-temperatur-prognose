import streamlit as st
import pandas as pd

# Konfiguration der Seite
st.set_page_config(page_title="Lager-Temperatur-Prognose", layout="wide")

# Beispiel-Daten für den Forecast (deine Logik hier ergänzen)
def run_forecast(start_temps, future_outdoor):
    # Dummy-Funktion zur Demonstration
    return [t + 0.5 for t in start_temps], [0.1] * len(start_temps)

# 1. Logo einfügen
col_logo, col_title = st.columns([1, 4])
with col_logo:
    # Stelle sicher, dass die Datei im gleichen Ordner liegt
    try:
        st.image("hartmann_logo.png", width=160)
    except FileNotFoundError:
        st.warning("Logo 'hartmann_logo.png' nicht gefunden.")

with col_title:
    st.header("Lager-Temperatur-Prognose")

st.markdown("""
Dieses Tool simuliert die thermische Trägheit der Lagergassen **G01, G02**.
""")

# 2. Sidebar mit Startwerten
with st.sidebar:
    st.header("Startwerte (Heute)")
    start_out = st.number_input("Außentemperatur (°C)", value=32.0, step=0.1)
    start_g01 = st.number_input("Gasse 1 (G01) (°C)", value=28.5, step=0.1)
    
    # Korrektur Syntaxfehler Zeile 105
    default_outdoor = [32.0, 32.0, 32.0, 32.0, 32.0, 32.0]

# 3. Daten-Eingabe (Beispiel für den DataFrame)
data = {
    "Datum": ["2026-06-24", "2026-06-25"],
    "Wochentag": ["Mittwoch", "Donnerstag"],
    "Prognose Außen (°C)": [30.0, 29.5]
}
df = pd.DataFrame(data)

# 4. Data Editor mit neuer Syntax (width='stretch')
edited_df = st.data_editor(
    df,
    column_config={
        "Wochentag": st.column_config.TextColumn("Wochentag", disabled=True),
        "Datum": st.column_config.TextColumn("Datum", disabled=True),
    },
    disabled=("Datum", "Wochentag"),
    hide_index=True,
    width='stretch' 
)

# 5. Berechnung (Korrigierter Zugriff auf Spalten)
if st.button("Prognose berechnen"):
    # Zugriff auf einzelne Spalte statt .tolist() auf das gesamte DF
    future_outdoor = edited_df['Prognose Außen (°C)'].tolist()
    dates_list = edited_df['Datum'].tolist()
    
    start_temps = [start_g01] * len(future_outdoor)
    
    predictions, uncertainties = run_forecast(start_temps, future_outdoor)
    
    # 6. Auswertung
    st.subheader("Prognoseauswertung der Lagergassen")
    result_df = pd.DataFrame({
        "Datum": dates_list,
        "Prognose (°C)": predictions
    })
    st.dataframe(result_df, width='stretch')
