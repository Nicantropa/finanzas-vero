import streamlit as st
import pandas as pd
import requests  # Para conectar a internet

# ==========================================
# 1. CONFIGURACIÓN DE RESPALDO (OFFLINE)
# ==========================================
# Si fallan TODAS las conexiones (internet caído), usa esto:
DEFAULT_CONFIG = {
    "TASAS": {
        "COP_EUR": 0.00023, 
        "USD_EUR": 0.92      
    },
    "PROPIEDAD": {
        "INGRESOS": {"Arriendo Apto": 1680000},
        "GASTOS": {
            "Hipoteca BBVA": 1700000,
            "Administración": 203000,
            "Parqueadero": 70000,
            "Internet": 72000,
            "Luz (Promedio)": 80000,
            "Agua (Promedio)": 62000
        }
    },
    "DEUDAS_RECURRENTES": [
        {"Concepto": "Bancolombia Dorada Pesos",   "Moneda": "COP", "Pago_Usual": 1185000.0},
        {"Concepto": "Bancolombia Dorada Dólares", "Moneda": "USD", "Pago_Usual": 94.0},
        {"Concepto": "Bancolombia Ecard Pesos",    "Moneda": "COP", "Pago_Usual": 134000.0},
        {"Concepto": "Bancolombia Ecard Dólares",  "Moneda": "USD", "Pago_Usual": 10.0},
        {"Concepto": "Banco de Bogotá",            "Moneda": "COP", "Pago_Usual": 840000.0},
        {"Concepto": "Nequi",                      "Moneda": "COP", "Pago_Usual": 181000.0}, # A veces es 0
    ]
}

# ==========================================
# 2. FUNCIONES DE CONEXIÓN ROBUSTA
# ==========================================
@st.cache_data(ttl=3600)
def obtener_tasas_robustas():
    """
    Intenta obtener tasas de 2 fuentes diferentes.
    Si la primera falla, intenta la segunda.
    """
    
    # --- INTENTO 1: Frankfurter API (Banco Central Europeo) ---
    try:
        # Usamos 'latest' para que traiga el último día hábil automáticamente
        url = "https://api.frankfurter.app/latest?from=USD&to=EUR,COP"
        resp = requests.get(url, timeout=3) # Timeout corto para no esperar mucho
        
        if resp.status_code == 200:
            data = resp.json()
            tasa_usd_eur = data['rates']['EUR']
            
            # Frankfurter a veces no tiene COP directo, calculamos triangulando
            # Si tengo 1 USD -> X COP, y 1 USD -> Y EUR...
            # Entonces 1 COP = Y / X EUR
            if 'COP' in data['rates']:
                cop_per_usd = data['rates']['COP']
                tasa_cop_eur = tasa_usd_eur / cop_per_usd
            else:
                # Si falla COP en Frankfurter, forzamos error para ir al plan B
                raise ValueError("COP no disponible en Frankfurter")

            return {
                "USD_EUR": tasa_usd_eur, 
                "COP_EUR": tasa_cop_eur, 
                "FUENTE": "Frankfurter (BCE)"
            }
            
    except Exception as e:
        print(f"Fallo API 1: {e}")

    # --- INTENTO 2: Open Exchange Rates (Plan B - Muy estable) ---
    try:
        # Esta API actualiza cada 24h y es muy fiable para LATAM
        url_backup = "https://open.er-api.com/v6/latest/USD"
        resp = requests.get(url_backup, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            # Esta API base es USD.
            # 1 USD = X EUR
            # 1 USD = Y COP
            usd_to_eur = data['rates']['EUR']
            usd_to_cop = data['rates']['COP']
            
            # Calculamos cuánto vale 1 COP en EUR
            # Regla de 3: (1 COP * USD_EUR) / USD_COP
            cop_to_eur = usd_to_eur / usd_to_cop
            
            return {
                "USD_EUR": usd_to_eur, 
                "COP_EUR": cop_to_eur,
                "FUENTE": "Open-ER API (Respaldo)"
            }

    except Exception as e:
        print(f"Fallo API 2: {e}")
    
    # Si todo falla, retornamos None para usar valores manuales
    return None

# ==========================================
# 3. FUNCIONES LÓGICAS
# ==========================================
def convertir_a_euros(monto, moneda, tasa_cop, tasa_usd):
    if moneda == "COP": return monto * tasa_cop
    elif moneda == "USD": return monto * tasa_usd
    return 0.0

def calcular_deficit_propiedad(ingresos_dict, gastos_dict):
    total_ing = sum(ingresos_dict.values())
    total_gas = sum(gastos_dict.values())
    balance = total_gas - total_ing
    return max(0, balance), total_gas, total_ing

# ==========================================
# 4. INTERFAZ GRÁFICA
# ==========================================
def main():
    st.set_page_config(page_title="Finanzas Blindadas", layout="centered")
    st.title("⚡ Calculadora Financiera")

    # --- Lógica de Carga de Tasas ---
    datos_api = obtener_tasas_robustas()
    
    if datos_api:
        valor_cop = datos_api["COP_EUR"]
        valor_usd = datos_api["USD_EUR"]
        fuente = datos_api["FUENTE"]
        estado_msg = f"🟢 Conectado a: {fuente}"
        help_msg = "Datos obtenidos automáticamente del mercado."
    else:
        # Fallback a valores manuales (Offline)
        valor_cop = DEFAULT_CONFIG["TASAS"]["COP_EUR"]
        valor_usd = DEFAULT_CONFIG["TASAS"]["USD_EUR"]
        estado_msg = "🔴 Modo Offline (Sin conexión)"
        help_msg = "No se pudo conectar a internet. Usando valores guardados."

    # --- Sidebar ---
    with st.sidebar:
        st.header("💱 Tasas de Cambio")
        st.caption(estado_msg)
        
        # Inputs editables
        tasa_cop = st.number_input("COP a EUR", value=valor_cop, format="%.6f", help=help_msg)
        tasa_usd = st.number_input("USD a EUR", value=valor_usd, format="%.4f", help=help_msg)
        
        st.divider()
        st.info(f"**Referencia:**\n1 EUR ≈ ${1/tasa_cop:,.0f} COP")

    # --- BLOQUE 1: PROPIEDAD ---
    st.subheader("1. 🏠 Balance Propiedad")
    with st.expander("📝 Revisar Recibos del Apartamento", expanded=True):
        c1, c2 = st.columns(2)
        ingresos_dinamicos = {}
        gastos_dinamicos = {}

        with c1:
            st.caption("Ingresos")
            for k, v in DEFAULT_CONFIG["PROPIEDAD"]["INGRESOS"].items():
                ingresos_dinamicos[k] = st.number_input(f"{k}", value=v, step=10000)
        with c2:
            st.caption("Gastos")
            for k, v in DEFAULT_CONFIG["PROPIEDAD"]["GASTOS"].items():
                gastos_dinamicos[k] = st.number_input(f"{k}", value=v, step=5000)

    deficit, t_gastos, t_ingresos = calcular_deficit_propiedad(ingresos_dinamicos, gastos_dinamicos)

    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("Gastos Apto", f"${t_gastos:,.0f}")
    col_kpi2.metric("Arriendo", f"${t_ingresos:,.0f}")
    col_kpi3.metric("Déficit", f"${deficit:,.0f}", delta="Ok" if deficit == 0 else "- Poner dinero", delta_color="inverse")

    # --- BLOQUE 2: DEUDAS ---
    st.divider()
    st.subheader("2. 💳 Deudas Bancarias")
    
    df_config = pd.DataFrame(DEFAULT_CONFIG["DEUDAS_RECURRENTES"])
    df_config = df_config.rename(columns={"Pago_Usual": "Pago Este Mes"})

    column_cfg = {
        "Moneda": st.column_config.SelectboxColumn("Moneda", options=["COP", "USD"], required=True, width="small"),
        "Pago Este Mes": st.column_config.NumberColumn("Pago Este Mes", min_value=0.0, format="$%f")
    }

    df_final_deudas = st.data_editor(
        df_config, column_config=column_cfg, use_container_width=True, hide_index=True, num_rows="dynamic"
    )

    # --- BLOQUE 3: RESULTADOS ---
    st.divider()
    st.header("💶 Resumen Total")

    total_eur = 0
    detalles = []

    for _, row in df_final_deudas.iterrows():
        monto = row["Pago Este Mes"]
        if monto > 0:
            conv = convertir_a_euros(monto, row["Moneda"], tasa_cop, tasa_usd)
            total_eur += conv
            detalles.append(f"{row['Concepto']}: €{conv:,.2f}")

    if deficit > 0:
        conv_def = convertir_a_euros(deficit, "COP", tasa_cop, tasa_usd)
        total_eur += conv_def
        detalles.append(f"🏠 Déficit Propiedad: €{conv_def:,.2f}")

    c_fin1, c_fin2 = st.columns([1, 2])
    with c_fin1:
        st.metric(label="TOTAL A TRANSFERIR", value=f"€{total_eur:,.2f}")
    with c_fin2:
        if detalles:
            st.write("**Desglose:**")
            for item in detalles:
                st.write(f"- {item}")
        else:
            st.success("¡Sin deudas pendientes!")

if __name__ == "__main__":
    main()