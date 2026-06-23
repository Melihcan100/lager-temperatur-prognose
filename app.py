import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 1. KONFIGURATION UND METADATENGRUNDLAGE
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Lagerlogistik Temperatur-Prognose", layout="wide")

PARAMS = {
    'G01': {'beta_aussen': 0.180665, 'beta_innen': 0.367569, 'konstante': 11.477976, 'r2': 0.7993},
    'G02': {'beta_aussen': 0.125014, 'beta_innen': 0.480714, 'konstante': 9.575989, 'r2': 0.8673},
    'G03': {'beta_aussen': 0.119122, 'beta_innen': 0.409141, 'konstante': 10.611084, 'r2': 0.8411}
}

# -----------------------------------------------------------------------------
# 2. PHYSIKALISCHE KERNFUNKTIONEN
# -----------------------------------------------------------------------------
def calculate_mkt(temperatures_celsius):
    delta_H = 83.14472 
    R = 0.008314472    
    temps_k = np.array(temperatures_celsius) + 273.15
    exponents = np.exp(-delta_H / (R * temps_k))
    mean_exponent = np.mean(exponents)
    if mean_exponent == 0:
        return np.nan
    mkt_k = (delta_H / R) / (-np.log(mean_exponent))
    return mkt_k - 273.15

def calculate_prediction_error(step, r2_score):
    # Fehlerfortpflanzung des AR(1) Modells
    base_error = (1.0 - r2_score) * 4.5 
    return base_error * np.sqrt(step + 1)

# -----------------------------------------------------------------------------
# 3. PROGNOSE-ALGORITHMUS (Korrigiert für exakte ARX-Abbildung)
# -----------------------------------------------------------------------------
def run_forecast(start_temps, future_outdoor_temps):
    horizon = len(future_outdoor_temps)
    
    predictions = {gasse: list() for gasse in PARAMS.keys()}
    uncertainties = {gasse: list() for gasse in PARAMS.keys()}
    
    current_state = start_temps.copy()
    
    for t in range(horizon):
        t_aussen = future_outdoor_temps[t]
        
        for gasse, params in PARAMS.items():
            # Die reine AR(1) Gleichung ohne störende Kalendereffekte für physikalische Präzision
            t_next = (params['konstante'] + 
                      (params['beta_aussen'] * t_aussen) + 
                      (params['beta_innen'] * current_state[gasse]))
            
            error = calculate_prediction_error(t, params['r2'])
            
            predictions[gasse].append(t_next)
            uncertainties[gasse].append(error)
            current_state[gasse] = t_next
            
    return predictions, uncertainties

# -----------------------------------------------------------------------------
# 4. BENUTZEROBERFLÄCHE UND APP-LOGIK
# -----------------------------------------------------------------------------
col_title, col_logo = st.columns([1, 2])

with col_title:
    st.title("🌡️ Prädiktives Zeitreihen-Tool für die Lagerlogistik (7-Tage Fokus)")

with col_logo:
    # Fügt das Hartmann-Logo oben rechts ein (Bilddatei muss im selben Ordner liegen)
    try:
        st.image("hartmann_logo.png", width=160)
    except:
        pass # Ignoriere den Fehler, falls das Logo nicht vorhanden ist

st.markdown("""
Dieses Tool simuliert die thermische Trägheit der Lagergassen **G01, G02 und G03** auf Basis 
einer erweiterten autoregressiven Modellierung (ARX). Das Modell wurde für einen präzisen 
**7-Tage-Horizont** kalibriert.
""")

with st.sidebar:
    st.header("Startwerte (Heute)")
    st.markdown("Sensordaten des aktuellen Tages zur Initialisierung des iterativen Modells.")
    start_out = st.number_input("Außentemperatur (°C)", value=32.0, step=0.5)
    start_g01 = st.number_input("Gasse 1 (G01) (°C)", value=28.5, step=0.1)
    start_g02 = st.number_input("Gasse 2 (G02) (°C)", value=26.5, step=0.1)
    start_g03 = st.number_input("Gasse 3 (G03) (°C)", value=24.5, step=0.1)
    
    start_temps = {'G01': start_g01, 'G02': start_g02, 'G03': start_g03}
    
    st.divider()
    st.header("Schwellenwert-Management")
    max_temp_limit = st.slider("Kritische Maximaltemperatur (°C)", 20.0, 35.0, 25.0)
    st.caption("Orientiert am regulatorischen Limit (25°C) für GDP-Lagerung.")

if 'input_df' not in st.session_state:
    base_date = datetime.today()
    
    # Exaktes 7-Tage Stresstest-Szenario aus den Referenzdaten
    default_outdoor = [32.0, 32.0, 32.0, 32.0, 32.0, 3
