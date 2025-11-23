import streamlit as st
import pandas as pd

# ==========================================
# 1. CONFIGURACIÓN CENTRAL (TU "BASE DE DATOS" DE VALORES USUALES)
# ==========================================
# Aquí es donde defines tus promedios.
# Si el otro mes tu promedio de luz sube a 90.000, lo cambias aquí y listo.

DEFAULT_CONFIG = {
    "TASAS": {
        "COP_EUR": 0.00023,  # Valor de referencia
        "USD_EUR": 0.92      # Valor de referencia
    },
    "PROPIEDAD": {
        "INGRESOS": {
            "Arriendo Apto": 1680000  # Valor contrato
        },
        "GASTOS": {
            # Pon aquí el valor EXACTO de tus facturas fijas
            # y el valor PROMEDIO de tus facturas variables.
            "Hipoteca BBVA": 1700000,
            "Administración": 203000,
            "Parqueadero": 70000,
            "Internet": 72000,
            "Luz (Promedio)": 80000,  # Valor editable en la app
            "Agua (Promedio)": 62000  # Valor editable en la app
        }
    },
    "DEUDAS_RECURRENTES": [
        # Pon aquí lo que "usualmente" pagas de mínimo. 
        # Si varía mucho, puedes dejar un estimado o 0.
        {"Concepto": "Bancolombia Dorada Pesos",   "Moneda": "COP", "Pago_Usual": 150000.0},
        {"Concepto": "Bancolombia Dorada Dólares", "Moneda": "USD", "Pago_Usual": 50.0},
        {"Concepto": "Bancolombia Ecard Pesos",    "Moneda": "COP", "Pago_Usual": 80000.0},
        {"Concepto": "Bancolombia Ecard Dólares",  "Moneda": "USD", "Pago_Usual": 25.0},
        {"Concepto": "Banco de Bogotá",            "Moneda": "COP", "Pago_Usual": 200000.0},
        {"Concepto": "Nequi",                      "Moneda": "COP", "Pago_Usual": 0.0}, # A veces es 0
    ]
}

# ==========================================
# 2. FUNCIONES LÓGICAS (BACKEND)
# ==========================================
def convertir_a_euros(monto, moneda, tasa_cop, tasa_usd):
    if moneda == "COP": return monto * tasa_cop
    elif moneda == "USD": return monto * tasa_usd
    return 0.0

def calcular_deficit_propiedad(ingresos_dict, gastos_dict):
    total_ing = sum(ingresos_dict.values())
    total_gas = sum(gastos_dict.values())
    balance = total_gas - total_ing
    # Si balance > 0, falta plata (Déficit). Si < 0, sobra (Ganancia).
    return max(0, balance), total_gas, total_ing

# ==========================================
# 3. INTERFAZ (FRONTEND)
# ==========================================
def main():
    st.set_page_config(page_title="Mis Finanzas Rápidas", layout="centered")
    
    st.title("⚡ Calculadora Financiera Rápida")
    st.markdown("Los valores inician con tu **promedio habitual**. Edita solo lo que cambió este mes.")

    # --- Sidebar: Tasas ---
    with st.sidebar:
        st.header("💱 Tasas de Hoy")
        # Precargamos las tasas del config también
        tasa_cop = st.number_input("COP a EUR", value=DEFAULT_CONFIG["TASAS"]["COP_EUR"], format="%.6f")
        tasa_usd = st.number_input("USD a EUR", value=DEFAULT_CONFIG["TASAS"]["USD_EUR"], format="%.2f")
        st.divider()
        st.info("💡 Tip: Solo edita las casillas si el valor real de este mes es diferente al precargado.")

    # --- BLOQUE 1: PROPIEDAD (Valores Precargados) ---
    st.subheader("1. 🏠 Balance Propiedad")
    
    # Usamos un expander para que no ocupe espacio si los valores son los de siempre
    with st.expander("📝 Revisar Recibos del Apartamento", expanded=True):
        c1, c2 = st.columns(2)
        
        ingresos_dinamicos = {}
        gastos_dinamicos = {}

        # Generamos inputs automáticamente basados en el CONFIG
        with c1:
            st.caption("Ingresos")
            for k, v in DEFAULT_CONFIG["PROPIEDAD"]["INGRESOS"].items():
                ingresos_dinamicos[k] = st.number_input(f"{k}", value=v, step=10000)
        
        with c2:
            st.caption("Gastos")
            for k, v in DEFAULT_CONFIG["PROPIEDAD"]["GASTOS"].items():
                gastos_dinamicos[k] = st.number_input(f"{k}", value=v, step=5000)

    # Cálculo inmediato
    deficit, t_gastos, t_ingresos = calcular_deficit_propiedad(ingresos_dinamicos, gastos_dinamicos)

    # Feedback visual rápido
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("Gastos Apto", f"${t_gastos:,.0f}")
    col_kpi2.metric("Arriendo", f"${t_ingresos:,.0f}")
    col_kpi3.metric("Déficit (A cubrir)", f"${deficit:,.0f}", 
                    delta="Ok" if deficit == 0 else "- Poner dinero", delta_color="inverse")

    # --- BLOQUE 2: DEUDAS (Tabla Precargada) ---
    st.divider()
    st.subheader("2. 💳 Deudas Bancarias")
    st.caption("Ajusta los montos si tu pago mínimo cambió este mes.")

    # Convertimos la lista del config en un DataFrame
    df_config = pd.DataFrame(DEFAULT_CONFIG["DEUDAS_RECURRENTES"])
    
    # Renombramos columna interna 'Pago_Usual' a 'Pago Este Mes' para la tabla
    df_config = df_config.rename(columns={"Pago_Usual": "Pago Este Mes"})

    # Configuración de la tabla editable
    column_cfg = {
        "Moneda": st.column_config.SelectboxColumn("Moneda", options=["COP", "USD"], required=True, width="small"),
        "Pago Este Mes": st.column_config.NumberColumn("Pago Este Mes", min_value=0.0, format="$%f")
    }

    # EL TRUCO: Pasamos df_config con datos. El usuario edita sobre esos datos.
    df_final_deudas = st.data_editor(
        df_config, 
        column_config=column_cfg, 
        use_container_width=True, 
        hide_index=True,
        num_rows="dynamic" # Permite añadir filas si sale una deuda nueva
    )

    # --- BLOQUE 3: RESULTADOS EN EUROS ---
    st.divider()
    st.header("💶 Total a Transferir")

    total_eur = 0
    detalles = []

    # 1. Sumar Bancos
    for _, row in df_final_deudas.iterrows():
        monto = row["Pago Este Mes"]
        if monto > 0:
            conv = convertir_a_euros(monto, row["Moneda"], tasa_cop, tasa_usd)
            total_eur += conv
            detalles.append(f"{row['Concepto']}: €{conv:,.2f}")

    # 2. Sumar Déficit Propiedad
    if deficit > 0:
        conv_def = convertir_a_euros(deficit, "COP", tasa_cop, tasa_usd)
        total_eur += conv_def
        detalles.append(f"🏠 Déficit Propiedad: €{conv_def:,.2f}")

    # Mostrar Totales
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