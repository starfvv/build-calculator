import streamlit as st
import pulp as pl
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
import io

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
    if usar_exotico:
        prob += pl.lpSum(exo[a] for a in arquetipos.keys()) == 1
    else:
        prob += pl.lpSum(exo[a] for a in arquetipos.keys()) == 0

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
            expr.append(30 * (1 if prim == s else 0) * x[a])
            expr.append(25 * (1 if sec == s else 0) * x[a])
            if s in t[a]:
                expr.append(20 * t[a][s])
            rest = x[a]
            if prim == s: rest -= x[a]
            if sec == s: rest -= x[a]
            if s in t[a]: rest -= t[a][s]
            expr.append(5 * rest)
            expr.append(30 * (1 if prim == s else 0) * exo[a])
            expr.append(20 * (1 if sec == s else 0) * exo[a])
            if s in t_exo[a]:
                expr.append(13 * t_exo[a][s])
            rest_exo = exo[a]
            if prim == s: rest_exo -= exo[a]
            if sec == s: rest_exo -= exo[a]
            if s in t_exo[a]: rest_exo -= t_exo[a][s]
            expr.append(5 * rest_exo)
        expr.append(10 * mods10[s])
        expr.append(5 * mods5[s])
        stat[s] = pl.lpSum(expr)

    for s, min_val in minimos.items():
        prob += stat[s] >= min_val

    prob += pl.lpSum(stat[s] for s in estadisticas) == 90 * pl.lpSum(x[a] for a in arquetipos.keys()) + \
            78 * pl.lpSum(exo[a] for a in arquetipos.keys()) + 10 * pl.lpSum(mods10[s] for s in estadisticas) + \
            5 * pl.lpSum(mods5[s] for s in estadisticas)

    if prioridad:
        prob += stat[prioridad]

    prob.solve(pl.PULP_CBC_CMD(msg=False))

    if pl.LpStatus[prob.status] != "Optimal":
        return None

    piezas = {a: int(x[a].value()) for a in arquetipos.keys()}
    exotico = None
    for a in arquetipos.keys():
        if int(exo[a].value()) == 1:
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
    resultado["modificadores10"] = {s: int(mods10[s].value()) for s in estadisticas if mods10[s].value() > 0}
    resultado["modificadores5"] = {s: int(mods5[s].value()) for s in estadisticas if mods5[s].value() > 0}
    resultado["estadisticas_finales"] = {s: int(stat[s].value()) for s in estadisticas}

    return resultado

img = Image.open("images/logo_credo.png")
st.image(img, use_container_width=True)

st.markdown(
    "<h1 style='text-align: center;'>Calculadora de arquetipos</h1>",
    unsafe_allow_html=True
)

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

prioridad = st.selectbox("Estadística a priorizar", ["Ninguna"] + estadisticas, index=0)
prioridad = None if prioridad == "Ninguna" else prioridad

if "resultado" not in st.session_state:
    st.session_state.resultado = None

if st.button("Calcular combinación óptima"):
    res = build_calc(minimos, num_mods10=num_mods10, num_mods5=num_mods5,
                     usar_exotico=exotic, prioridad=prioridad)
    if res is None:
        st.error("No se encontró ninguna combinación posible con esos mínimos.")
    else:
        st.session_state.resultado = res

def exportar_todo_2x2(df_piezas, df_terciarias, df_mods, df_stats, minimos):
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    plt.subplots_adjust(hspace=0.6, wspace=0.4)
    axes = axes.flatten()
    cell_fontsize = 12
    header_fontsize = 14

    def plot_table(ax, df, title):
        ax.axis('off')
        ax.set_title(title, fontsize=header_fontsize, fontweight='bold')
        if not df.empty:
            # Crear colores alternos por fila
            n_rows, n_cols = df.shape
            colors = [["#f0f0f0" if i % 2 == 0 else "#ffffff" for j in range(n_cols)] for i in range(n_rows)]
            table = ax.table(cellText=df.values,
                             colLabels=df.columns,
                             cellLoc='center',
                             loc='center',
                             colColours=["#d9d9d9"]*n_cols,
                             cellColours=colors)
            table.auto_set_font_size(False)
            table.set_fontsize(cell_fontsize)
            table.scale(1, 1.5)  # Ajusta alto de filas
        else:
            ax.text(0.5, 0.5, "No hay datos", ha='center', va='center', fontsize=cell_fontsize)

    plot_table(axes[0], df_piezas, "Cantidad de piezas por arquetipo")
    plot_table(axes[1], df_terciarias, "Estadísticas terciarias por arquetipo")
    plot_table(axes[2], df_mods, "Modificadores asignados")
    plot_table(axes[3], df_stats, "Estadísticas finales")

    plt.suptitle("Resultado del cálculo", fontsize=18, fontweight='bold')
    minimos_str = ", ".join([f"{k}: {v}" for k, v in minimos.items()])
    plt.figtext(0.5, 0.93, f"Mínimos aplicados: {minimos_str}", ha="center", fontsize=14)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

if st.session_state.resultado:
    res = st.session_state.resultado

    st.subheader("Cantidad de piezas por arquetipo")
    df_piezas = pd.DataFrame({"Arquetipo": list(res["piezas"].keys()),
                              "Cantidad": list(res["piezas"].values())})
    st.dataframe(df_piezas.to_dict(orient="records"))
    if res.get("exotico"):
        st.write(f"Arquetipo exótico: {res['exotico']}")

    st.subheader("Estadísticas terciarias por arquetipo")
    tercios = []
    for a in res["terciarias"]:
        for s in res["terciarias"][a]:
            if res["terciarias"][a][s] > 0:
                tercios.append({"Arquetipo": a, "Terciaria": s, "Cantidad": res["terciarias"][a][s]})
    df_terciarias = pd.DataFrame(tercios)
    if not df_terciarias.empty:
        st.dataframe(df_terciarias.to_dict(orient="records"))
    else:
        st.write("No hay estadísticas terciarias asignadas.")

    st.subheader("Modificadores asignados (+10 y +5)")
    mods = [{"Estadística": s, "Cantidad +10": res["modificadores10"].get(s,0),
             "Cantidad +5": res["modificadores5"].get(s,0)} for s in estadisticas 
            if s in res["modificadores10"] or s in res["modificadores5"]]
    df_mods = pd.DataFrame(mods)
    if not df_mods.empty:
        st.dataframe(df_mods.to_dict(orient="records"))
    else:
        st.write("No se han asignado modificadores.")

    st.subheader("Estadísticas finales")
    df_stats = pd.DataFrame({"Estadística": [s for s in res["estadisticas_finales"].keys()],
                             "Valor final": list(res["estadisticas_finales"].values())})
    total = df_stats["Valor final"].sum()
    df_stats = pd.concat([df_stats, pd.DataFrame({"Estadística": ["Total"], "Valor final": [total]})],
                         ignore_index=True)
    st.dataframe(df_stats.to_dict(orient="records"))

    buf = exportar_todo_2x2(df_piezas, df_terciarias, df_mods, df_stats, minimos)
    st.download_button("📥 Descargar resultado como imagen", data=buf, file_name="build_resultado.png", mime="image/png")







