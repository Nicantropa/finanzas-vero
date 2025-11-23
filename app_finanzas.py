import streamlit as st
import pandas as pd
import requests  # Librería para conectar a internet

# ==========================================
# 1. CONFIGURACIÓN POR DEFECTO (RESPALDO)
# ==========================================
# Estos valores se usarán si falla la conexión a internet
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
        {"Concepto": "Bancolombia Dorada Pesos",   "Moneda": "COP", "Pago_Usual": 150000.0},
        {"Concepto": "Bancolombia Dorada Dólares", "Moneda": "USD", "Pago_Usual": 50.0},
        {"Concepto": "Bancolombia Ecard Pesos",    "Moneda": "COP", "Pago_Usual": 80000.0},
        {"Concepto": "Bancolombia Ecard Dólares",  "Moneda": "USD", "Pago_Usual": 25.0},
        {"Concepto": "Banco de Bogotá",            "Moneda": "COP", "Pago_Usual": 200000.0},
        {"Concepto": "Nequi",                      "Moneda": "COP", "Pago_Usual": 0.0},
    ]
}

# ==========================================
# 2. FUNCIONES DE CONEXIÓN (API)
# ==========================================
# Usamos @st.cache_data para no llamar a la API en cada clic (ahorra recursos)
@st.cache_data(ttl=3600) # Actualizar cada hora (3600 segundos)
def obtener_tasas_api():
    """
    Consulta la API gratuita de Frankfurter para obtener tasas reales.
    Retorna un diccionario con las tasas nuevas o None si falla.
    """
    try:
        # 1. Obtener USD a EUR
        url_usd = "https://api.frankfurter.app/latest?from=USD&to=EUR"
        resp_usd = requests.get(url_usd, timeout=5)
        tasa_usd = resp_usd.json()['rates']['EUR']

        # 2. Obtener COP a EUR (La API puede no tener COP directo a veces, 
        # pero intentamos. Si falla, calculamos cruzado).
        # Nota: Frankfurter a veces no tiene todas las latinas directo.
        # Alternativa fiable: 1 EUR en COP y dividimos.
        url_eur_cop = "https://api.frankfurter.app/latest?from=EUR&to=COP"
        resp_cop = requests.get(url_eur_cop, timeout=5)
        val_eur_en_cop = resp_cop.json()['rates']['COP']
        tasa_cop = 1 / val_eur_en_cop # Invertimos para tener factor COP->EUR

        return {"USD_EUR": tasa_usd, "COP_EUR": tasa_cop}
    
    except Exception as e:
        print(f"Error conectando a API: {e}")
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
    st.set_page_config(page_title="Mis Finanzas Live", layout="centered")
    st.title("⚡ Calculadora Financiera (En Vivo)")

    # --- Carga de Tasas ---
    # Intentamos obtener tasas de internet
    tasas_live = obtener_tasas_api()
    
    # Decidimos qué valores usar (Live o Backup)
    if tasas_live:
        valor_cop = tasas_live["COP_EUR"]
        valor_usd = tasas_live["USD_EUR"]
        estado_api = "🟢 Tasas actualizadas desde internet"
    else:
        valor_cop = DEFAULT_CONFIG["TASAS"]["COP_EUR"]
        valor_usd = DEFAULT_CONFIG["TASAS"]["USD_EUR"]
        estado_api = "🔴 Sin conexión - Usando tasas guardadas"

    # --- Sidebar ---
    with st.sidebar:
        st.header("💱 Tasas de Hoy")
        st.caption(estado_api)
        
        # Los valores por defecto del input ahora son los que trajo la API
        tasa_cop = st.number_input("COP a EUR", value=valor_cop, format="%.6f")
        tasa_usd = st.number_input("USD a EUR", value=valor_usd, format="%.4f")
        
        st.divider()
        st.info(f"Ref: 1 EUR ≈ {1/tasa_cop:,.0f} COP")

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
    st.header("💶 Total a Transferir")

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
        st.metric(label="TOTAL EN EUROS", value=f"€{total_eur:,.2f}")
    with c_fin2:
        if detalles:
            st.write("**Desglose:**")
            for item in detalles:
                st.write(f"- {item}")
        else:
            st.success("¡Todo en orden! No hay pagos pendientes.")

if __name__ == "__main__":
    main()