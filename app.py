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

WEEKEND_OFFSET = -0.4 

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
    base_error = (1.0 - r2_score) * 4.5 
    return base_error * np.sqrt(step + 1)

# -----------------------------------------------------------------------------
# 3. PROGNOSE-ALGORITHMUS
# -----------------------------------------------------------------------------
def run_forecast(start_temps, future_outdoor_temps, dates_list):
    horizon = len(future_outdoor_temps)
    
    predictions = {gasse: list() for gasse in PARAMS.keys()}
    uncertainties = {gasse: list() for gasse in PARAMS.keys()}
    
    current_state = start_temps.copy()
    
    for t in range(horizon):
        t_aussen = future_outdoor_temps[t]
        current_date = datetime.strptime(dates_list[t], "%Y-%m-%d")
        
        is_weekend = current_date.weekday() >= 5
        cal_effect = WEEKEND_OFFSET if is_weekend else 0.0
        
        for gasse, params in PARAMS.items():
            t_next = (params['konstante'] + 
                      (params['beta_aussen'] * t_aussen) + 
                      (params['beta_innen'] * current_state[gasse]) + 
                      cal_effect)
            
            error = calculate_prediction_error(t, params['r2'])
            
            predictions[gasse].append(t_next)
            uncertainties[gasse].append(error)
            current_state[gasse] = t_next
            
    return predictions, uncertainties

# -----------------------------------------------------------------------------
# 4. BENUTZEROBERFLÄCHE UND APP-LOGIK
# -----------------------------------------------------------------------------
st.title("🌡️ Prädiktives Zeitreihen-Tool für die Lagerlogistik")
st.markdown("""
Dieses Tool simuliert die thermische Trägheit der Lagergassen **G01, G02 und G03** auf Basis 
einer erweiterten autoregressiven Modellierung (ARX). Es berücksichtigt Lags, historische Koeffizienten 
sowie **Kalendereffekte** (reduzierte Wärmelast an Wochenenden). 
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
    max_temp_limit = st.slider("Kritische Maximaltemperatur (°C)", 20.0, 35.0, 28.0)
    st.caption("Orientiert am OSHA Action Limit (28°C) für Hitzestress.")

if 'input_df' not in st.session_state:
    base_date = datetime.today()
    
    default_outdoor = list(max(15.0, 32.0 - (i * 0.7)) for i in range(14))
    date_strings = list((base_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 15))
    weekday_strings = list((base_date + timedelta(days=i)).strftime("%A") for i in range(1, 15))
    
    st.session_state.input_df = pd.DataFrame({
        'Datum': date_strings,
        'Wochentag': weekday_strings,
        'Prognose Außen (°C)': default_outdoor
    })

col1, col2 = st.columns((1.2, 2))

with col1:
    st.subheader("Wetterprognose (Manuelle Eingabe)")
    st.caption("Editieren Sie die numerischen Werte in 'Prognose Außen'. Das Modell berechnet Echtzeit-Updates.")
    
    edited_df = st.data_editor(
        st.session_state.input_df,
        column_config={
            "Prognose Außen (°C)": st.column_config.NumberColumn(
                "Außen (°C)",
                min_value=-20.0,
                max_value=50.0,
                step=0.5,
                format="%.1f"
            ),
            "Wochentag": st.column_config.TextColumn("Wochentag", disabled=True),
            "Datum": st.column_config.TextColumn("Datum", disabled=True)
        },
        disabled=("Datum", "Wochentag"),
        hide_index=True,
        use_container_width=True
    )
    future_outdoor = edited_df['Prognose Außen (°C)'].tolist()
    
    # KORREKTUR 1
    dates_list = edited_df['Datum'].tolist()

predictions, uncertainties = run_forecast(start_temps, future_outdoor, dates_list)

with col2:
    st.subheader("Prognoseauswertung der Lagergassen")
    
    fig = go.Figure()
    colors = {'G01': '#EF553B', 'G02': '#00CC96', 'G03': '#AB63FA'}
    fill_colors = {'G01': 'rgba(239,85,59,0.15)', 'G02': 'rgba(0,204,150,0.15)', 'G03': 'rgba(171,99,250,0.15)'}
    
    for gasse in PARAMS.keys():
        y_vals = np.array(predictions[gasse])
        errors = np.array(uncertainties[gasse])
        
        upper_bound = y_vals + errors
        lower_bound = y_vals - errors
        
        fig.add_trace(go.Scatter(
            x=dates_list + dates_list[::-1],
            y=list(upper_bound) + list(lower_bound)[::-1],
            fill='toself',
            fillcolor=fill_colors[gasse], 
            line=dict(color='rgba(255,255,255,0)'),
            hoverinfo="skip",
            showlegend=False,
            name=f'{gasse} Intervall'
        ))
        
        fig.add_trace(go.Scatter(
            x=dates_list,
            y=y_vals,
            mode='lines+markers',
            name=f'{gasse} Prognose',
            line=dict(color=colors[gasse], width=3)
        ))

    fig.add_hline(y=max_temp_limit, line_dash="dot", line_color="red", line_width=2,
                  annotation_text=f"Maximalwert Limit ({max_temp_limit}°C)", 
                  annotation_position="bottom right")

    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Datum",
        yaxis_title="Innentemperatur (°C)",
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 5. AUSWERTUNG & HANDLUNGSEMPFEHLUNGEN
# -----------------------------------------------------------------------------
st.divider()
st.subheader("Operative Analyse und Risiko-Management-Matrix")

warnings_generated = list()
results_table = list()

for idx, date in enumerate(dates_list):
    # KORREKTUR 2
    weekday = edited_df['Wochentag'].iloc[idx]
    daily_row = {"Datum": date, "Wochentag": weekday[:2], "Außen": f"{future_outdoor[idx]:.1f} °C"}
    max_gasse_temp = 0
    kritische_gassen = list()
    
    for gasse in PARAMS.keys():
        temp = predictions[gasse][idx]
        error = uncertainties[gasse][idx]
        daily_row[f"{gasse} Prognose"] = f"{temp:.1f} °C (±{error:.1f})"
        
        if temp > max_gasse_temp:
            max_gasse_temp = temp
            
        if temp > max_temp_limit:
            kritische_gassen.append(gasse)
            
    if len(kritische_gassen) > 0:
        gassen_str = ", ".join(kritische_gassen)
        action = f"KRITISCH: Notkühlung {gassen_str}. OSHA-Akklimatisierung starten!"
        if idx < 4: 
            warnings_generated.append(f"Am **{date}** wird in **{gassen_str}** das Limit von {max_temp_limit}°C durchbrochen.")
    elif max_gasse_temp >= max_temp_limit - 1.5:
        action = "Präventiv: Freie Nachtauskühlung maximieren. HVLS-Ventilatoren aktivieren."
    else:
        action = "Normalbetrieb: Keine regulatorischen Maßnahmen erforderlich."
        
    daily_row["Empfehlung"] = action
    results_table.append(daily_row)

if warnings_generated:
    st.error("⚠️ **AKUTE WARNUNG: Thermische Grenzwertüberschreitung prognostiziert!**")
    for w in warnings_generated:
        st.write("- " + w)
else:
    st.success("✅ Sämtliche prädizierten Temperaturen verbleiben im regulatorisch sicheren Toleranzband.")

st.markdown("##### Kinetische Degradations-Metriken (Gesamter Horizont)")
col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("MKT Gasse 1", f"{calculate_mkt(predictions['G01']):.2f} °C")
col_m2.metric("MKT Gasse 2", f"{calculate_mkt(predictions['G02']):.2f} °C")
col_m3.metric("MKT Gasse 3", f"{calculate_mkt(predictions['G03']):.2f} °C")

st.dataframe(pd.DataFrame(results_table), use_container_width=True)
