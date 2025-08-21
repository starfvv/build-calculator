import streamlit as st
import pulp as pl
import pandas as pd
from PIL import Image
from io import BytesIO
import matplotlib.pyplot as plt

def build_calc(minimos, num_mods10=5, num_mods5=0, usar_exotico=False, prioridad=None):
    estadisticas = ["Salud", "CQC", "Granada", "Super", "Clase", "Armas"]
    arquetipos = {
        "Artillero": ("Armas", "Granada"),
        "Bastion": ("Salud", "Clase"),
        "Especialista": ("Clase", "Armas"),
        "Granadero": ("Granada", "Super"),
        "Parangon": ("Super", "CQC"),
        "Camorrista": ("CQC", "Salud"),
    }

    prob = pl.LpProblem("Build_Armor", pl.LpMaximize if prioridad else pl.LpStatusOptimal)
    x = pl.LpVariable.dicts("pieces", arquetipos.keys(), lowBound=0, upBound=5, cat="Integer")
    exo = pl.LpVariable.dicts("exotic", arquetipos.keys(), lowBound=0, upBound=1, cat="Integer")
    prob += pl.lpSum(x[a] + exo[a] for a in arquetipos.keys()) == 5
    prob += pl.lpSum(exo[a] for a in arquetipos.keys()) == (1 if usar_exotico else 0)

    t = {}
    t_exo = {}
    for a, (prim, sec) in arquetipos.items():
        t[a] = {}
        t_exo[a] = {}
        for s in estadisticas:
            if s != prim and s != sec:
                t[a][s] = pl.LpVariable(f"terciaria_{a}_{s}", lowBound=0, upBound=5, cat="Integer")
                t_exo[a][s] = pl.LpVariable(f"terciaria_exo_{a}_{s}", lowBound=0, upBound=1, cat="Integer")
        prob += pl.lpSum(t[a][s] for s in t[a].keys()) == x[a]
        prob += pl.lpSum(t_exo[a][s] for s in t_exo[a].keys()) == exo[a]

    mods10 = pl.LpVariable.dicts("mod10", estadisticas, lowBound=0, upBound=5, cat="Integer")
    mods5 = pl.LpVariable.dicts("mod5", estadisticas, lowBound=0, upBound=2, cat="Integer")
    prob += pl.lpSum(mods10[s] for s in estadisticas) == num_mods10
    prob += pl.lpSum(mods5[s] for s in estadisticas) <= num_mods5

    stat = {s: 0 for s in estadisticas}
    for s in estadisticas:
        expr = []
        for a, (prim, sec) in arquetipos.items():
            expr.append(30*(prim==s)*x[a])
            expr.append(25*(sec==s)*x[a])
            if s in t[a]: expr.append(20*t[a][s])
            rest = x[a]
            if prim==s: rest -= x[a]
            if sec==s: rest -= x[a]
            if s in t[a]: rest -= t[a][s]
            expr.append(5*rest)
            expr.append(30*(prim==s)*exo[a])
            expr.append(20*(sec==s)*exo[a])
            if s in t_exo[a]: expr.append(13*t_exo[a][s])
            rest_exo = exo[a]
            if prim==s: rest_exo -= exo[a]
            if sec==s: rest_exo -= exo[a]
            if s in t_exo[a]: rest_exo -= t_exo[a][s]
            expr.append(5*rest_exo)
        expr.append(10*mods10[s])
        expr.append(5*mods5[s])
        stat[s] = pl.lpSum(expr)

    for s, min_val in minimos.items():
        prob += stat[s] >= min_val

    prob += pl.lpSum(stat[s] for s in estadisticas) == 90*pl.lpSum(x[a] for a in arquetipos.keys()) + \
            78*pl.lpSum(exo[a] for a in arquetipos.keys()) + 10*pl.lpSum(mods10[s] for s in estadisticas) + \
            5*pl.lpSum(mods5[s] for s in estadisticas)
    
    if prioridad:
        prob += stat[prioridad]

    prob.solve(pl.PULP_CBC_CMD(msg=False))
    if pl.LpStatus[prob.status] != "Optimal":
        return None
    
    piezas = {a: int(x[a].value()) for a in arquetipos.keys()}
    exotico = None
    for a in arquetipos.keys():
        if int(exo[a].value())==1:
            exotico = a
            break

    terciarias_res = {}
    for a, (prim, sec) in arquetipos.items():
        d = {}
        for s in estadisticas:
            if s != prim and s != sec:
                d[s] = int(t[a][s].value()) + int(t_exo[a][s].value())
        terciarias_res[a] = d

    resultado = {}
    resultado["piezas"] = piezas
    resultado["exotico"] = exotico
    resultado["terciarias"] = terciarias_res
    resultado["modificadores10"] = {s:int(mods10[s].value()) for s in estadisticas if mods10[s].value()>0}
    resultado["modificadores5"] = {s:int(mods5[s].value()) for s in estadisticas if mods5[s].value()>0}
    resultado["estadisticas_finales"] = {s:int(stat[s].value()) for s in estadisticas}
    return resultado

def exportar_imagen(df_piezas, df_terciarias, df_mods, df_stats, minimos):
    fig, axs = plt.subplots(2,2, figsize=(12,10))
    axs = axs.flatten()
    for ax in axs: ax.axis('off')
    axs[0].table(cellText=df_piezas.values, colLabels=df_piezas.columns, loc='center')
    axs[1].table(cellText=df_terciarias.values, colLabels=df_terciarias.columns, loc='center')
    axs[2].table(cellText=df_mods.values, colLabels=df_mods.columns, loc='center')
    axs[3].table(cellText=df_stats.values, colLabels=df_stats.columns, loc='center')
    fig.suptitle(f"Resultado del cálculo\nMínimos: {minimos}", fontsize=16)
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    return buf

def mostrar_resultado(res, minimos):
    piezas_data = []
    for a, cant in res["piezas"].items():
        total_cant = cant + (1 if res.get("exotico")==a else 0)
        piezas_data.append({"Arquetipo": a, "Cantidad": f"{total_cant} *" if res.get("exotico")==a else total_cant})
    df_piezas = pd.DataFrame(piezas_data)
    tercios_data = []
    for a in res["terciarias"]:
        for s, v in res["terciarias"][a].items():
            if v>0: tercios_data.append({"Arquetipo": a, "Terciaria": s, "Cantidad": v})
    df_terciarias = pd.DataFrame(tercios_data)
    mods_data = []
    estadisticas = ["Salud", "CQC", "Granada", "Super", "Clase", "Armas"]
    for s in estadisticas:
        mods_data.append({"Estadística": s, "Cantidad +10": res["modificadores10"].get(s,0),
                          "Cantidad +5": res["modificadores5"].get(s,0)})
    df_mods = pd.DataFrame(mods_data)
    df_stats = pd.DataFrame({"Estadística": list(res["estadisticas_finales"].keys()),
                             "Valor final": list(res["estadisticas_finales"].values())})
    total = df_stats["Valor final"].sum()
    df_stats = pd.concat([df_stats, pd.DataFrame({"Estadística":["Total"], "Valor final":[total]})], ignore_index=True)
    st.subheader("Cantidad de piezas por arquetipo")
    st.dataframe(df_piezas, hide_index=True)
    st.subheader("Estadísticas terciarias por arquetipo")
    st.dataframe(df_terciarias, hide_index=True)
    st.subheader("Modificadores asignados (+10 y +5)")
    st.dataframe(df_mods, hide_index=True)
    st.subheader("Estadísticas finales")
    st.dataframe(df_stats, hide_index=True)
    return df_piezas, df_terciarias, df_mods, df_stats

img = Image.open("images/logo_credo.png")
st.image(img, use_container_width=True)
st.markdown("<h1 style='text-align: center;'>Calculadora de arquetipos</h1>", unsafe_allow_html=True)

with st.expander("ℹ️ Tutorial de la aplicación"):
    st.markdown("""
    Esta aplicación calcula una combinación de arquetipos que cumpla con las estadísticas mínimas indicadas por ti.
    - Los arquetipos utilizados son los existentes, a día de hoy, en el juego.  
      Cada arquetipo está determinado por una estadística primaria y una secundaria:
        * Artillero: Arma + Granada  
        * Bastión: Salud + Clase  
        * Especialista: Clase + Armas  
        * Granadero: Granada + Super  
        * Parangón: Super + CQC  
        * Camorrista: CQC + Salud
    - Cada pieza de armadura dispone de una estadística terciaria aleatoria entre las otras 4 estadísticas restantes.                 
    - Las armaduras consideradas para el cálculo son Tier 5, ya que siempre tienen la siguiente distribución:
        * 30 puntos en la estadística primaria  
        * 25 puntos en la estadística secundaria  
        * 20 puntos en la estadística terciaria
    - Existe la posibilidad de usar armaduras de Tier 4, que pueden caer con 75 de estadísticas como máximo.  
    - Permite incluir un exótico en el cálculo (Tier 2):  
        * 30 puntos en la estadística primaria  
        * 20 puntos en la estadística secundaria  
        * 13 puntos en la estadística terciaria
    - Si quieres, es posible añadir modificadores mayores (+10) y menores (+5).  
    - Por último, puedes elegir la estadística prioritaria a maximizar si los mínimos permiten superar esos valores.
    """)

st.write("Indica los mínimos requeridos para cada estadística:")
estadisticas = ["Salud", "CQC", "Granada", "Super", "Clase", "Armas"]
minimos = {}
for s in estadisticas:
    minimos[s] = st.number_input(s, 0, 200, 0)

exotic = st.checkbox("¿Quieres usar un exótico?")
col1, col2 = st.columns(2)
with col1:
    num_mods10 = st.selectbox("Número de modificadores +10", list(range(6)), index=0)
with col2:
    num_mods5 = st.selectbox("Número de modificadores +5", list(range(0,(5-num_mods10)+1)), index=0)
prioridad = st.selectbox("Estadística a priorizar", ["Ninguna"]+estadisticas, index=0)
prioridad = None if prioridad=="Ninguna" else prioridad

if st.button("Calcular combinación óptima"):
    res = build_calc(minimos, num_mods10=num_mods10, num_mods5=num_mods5, usar_exotico=exotic, prioridad=prioridad)
    if res is None:
        st.error("No se encontró ninguna combinación posible con esos mínimos.")
    else:
        df_piezas, df_terciarias, df_mods, df_stats = mostrar_resultado(res, minimos)
        buf = exportar_imagen(df_piezas, df_terciarias, df_mods, df_stats, minimos)
        st.download_button("📥 Descargar resultado", data=buf, file_name="resultado.png", mime="image/png", on_click="ignore")


