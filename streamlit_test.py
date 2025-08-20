import streamlit as st
import pulp as pl
import pandas as pd
from PIL import Image

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

st.title("Simulador de armaduras")
st.write("Indica los mínimos para cada estadística:")

estadisticas = ["Salud", "CQC", "Granada", "Super", "Clase", "Armas"]
minimos = {}
for s in estadisticas:
    minimos[s] = st.number_input(s, 0, 200, 0)

exotic = st.checkbox("Usar un exótico en la build")
num_mods10 = st.selectbox("Número de modificadores (+10 cada uno)", [0,1,2,3,4,5], index=0)
num_mods5 = st.selectbox("Número de modificadores (+5 cada uno)", [0,1,2,3,4,5], index=0)
prioridad = st.selectbox("Estadística a priorizar con puntos sobrantes", ["Ninguna"] + estadisticas, index=0)
prioridad = None if prioridad == "Ninguna" else prioridad

def mostrar_resultado(res):
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
    if tercios:
        st.dataframe(pd.DataFrame(tercios).to_dict(orient="records"))
    else:
        st.write("No hay estadísticas terciarias asignadas.")

    st.subheader("Modificadores asignados (+10 y +5)")
    mods = [{"Estadística": s, "Cantidad +10": res["modificadores10"].get(s,0),
             "Cantidad +5": res["modificadores5"].get(s,0)} for s in estadisticas if s in res["modificadores10"] or s in res["modificadores5"]]
    if mods:
        st.dataframe(pd.DataFrame(mods).to_dict(orient="records"))
    else:
        st.write("No se han asignado modificadores.")

    st.subheader("Estadísticas finales")
    df_stats = pd.DataFrame({"Estadística": [s for s in res["estadisticas_finales"].keys()],
                             "Valor final": list(res["estadisticas_finales"].values())})
    total = df_stats["Valor final"].sum()
    df_stats = pd.concat([df_stats, pd.DataFrame({"Estadística": ["Total"], "Valor final": [total]})],
                         ignore_index=True)
    st.dataframe(df_stats.to_dict(orient="records"))


if st.button("Calcular combinación óptima"):
    res = build_calc(minimos, num_mods10=num_mods10, num_mods5=num_mods5,
                     usar_exotico=exotic, prioridad=prioridad)
    if res is None:
        st.error("No se encontró ninguna combinación posible con esos mínimos.")
    else:

        mostrar_resultado(res)
