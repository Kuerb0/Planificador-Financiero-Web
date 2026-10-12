"""Página Cartera."""
from ui import *  # noqa: F401,F403  (st, np, pd, go, fin y utilidades comunes)


def pag_cartera():
    titulo_pagina("📈", "Cartera", "Cuánto podrías tener en el futuro repartiendo tu dinero entre renta fija y variable")
    with st.expander("ℹ️ Cómo funciona la simulación"):
        st.markdown("- **Monte Carlo**: sortea miles de veces años reales de la bolsa para crear futuros posibles; "
                    "la mediana es el «caso típico» y el P5/P95 los extremos razonables.\n"
                    "- **Ventanas históricas**: repite periodos reales completos (p. ej. empezar en 1990, en 1991…).\n"
                    "- **Buy and hold** invierte todo el primer día; **promediar** va añadiendo ahorro con el tiempo.\n"
                    "- La renta fija usa tipos actuales del BCE o la curva histórica según el modo elegido.")
    tipos, errs_tipos = tipos_actuales()
    if errs_tipos:
        with st.expander("⚠️ No se han podido leer todos los tipos de interés del BCE", expanded=True):
            for k, e in errs_tipos.items():
                st.write(f"**{ {'euribor12m': 'Euribor 12m', 'bono10': 'Bono euro 10 años'}[k] }**: {e}")
            st.caption("Puedes seguir con un tipo manual (en «Opciones avanzadas»). El detalle técnico queda en "
                       "errores.log. Prueba «Actualizar datos de mercado» en la barra lateral.")

    perfiles = fin.leer_perfiles()
    activo = perfiles.get("activo")
    perfil = perfiles["usuarios"].get(activo) if activo else None

    st.session_state.setdefault("c_rv", 60)
    with st.container(border=True):
        e1, e2 = st.columns([3, 2])
        estrategia = e1.radio("Estrategia", ["Promediar (aportaciones periódicas)", "Buy and hold (todo de golpe)"],
                              horizontal=True, key="c_estr",
                              help="Promediar (DCA): inviertes un capital hoy y vas añadiendo ahorro cada año o cada "
                                   "mes, así compras a precios distintos. Buy and hold: inviertes todo el primer día "
                                   "y no tocas nada hasta el final.")
        hold = estrategia.startswith("Buy")
        if hold:
            frecuencia = "Anual"
            e2.caption("Buy and hold: se invierte solo el capital inicial y se deja crecer sin añadir ni vender.")
        else:
            frecuencia = e2.radio("Las aportaciones son", ["Mensuales", "Anuales"], horizontal=True, key="c_frec")
        m_apo = 12 if frecuencia == "Mensuales" else 1
        a1, a2, a3, a4 = st.columns(4)
        inicial = a1.number_input("Dinero que inviertes hoy (€)", 0, 50_000_000, 10_000, 1_000, key="c_ini")
        aporte_in = a2.number_input("Ahorro que añades cada año (€)", 0, 5_000_000, 3_000, 500, key="c_apo",
                                    disabled=hold, help="Se reparte en cuotas iguales según la frecuencia elegida.")
        aporte = 0 if hold else aporte_in
        H = a3.number_input("¿Durante cuántos años?", 1, 30, 10, 1, key="c_H")
        w_pct = a4.slider("% en renta variable (bolsa)", 0, 100, key="c_rv", step=5,
                          help="El resto va a renta fija (más estable, menos rentable).")
        if perfil:
            st.button(f"Usar el reparto sugerido para {activo} ({perfil['nivel']}): {perfil['rv_sugerida']} % bolsa",
                      on_click=lambda: st.session_state.update(c_rv=int(perfil["rv_sugerida"])),
                      help="Basado en tu test de riesgo. Es orientativo.")
        else:
            st.caption("Haz el test de riesgo (menú de la izquierda) y te sugeriré un reparto.")

        with st.expander("Opciones avanzadas: índice, método y renta fija"):
            b1, b2, b3 = st.columns([2, 1, 1])
            indice = b1.selectbox("Índice de bolsa", list(fin.INDICES), key="c_idx",
                                  help="En dólares y con dividendos, sin convertir a euros. El «Mundo largo» "
                                       "empalma MSCI World (1973-2008) con el ETF Vanguard Total World (desde 2009).")
            metodo = b2.selectbox("Método", ["Monte Carlo (bootstrap)", "Ventanas históricas"], key="c_met",
                                  help="Monte Carlo: sortea años del histórico miles de veces. "
                                       "Ventanas: repite periodos reales consecutivos.")
            if metodo.startswith("Monte"):
                modo_rf = "Tipo constante"
                b3.selectbox("Renta fija", ["Tipo constante"], key="c_modo_mc", disabled=True)
            else:
                modo_rf = b3.selectbox("Renta fija", fin.MODOS_RF, key="c_modo",
                                       help="Tipo constante: rinde siempre lo mismo. Carry histórico: cada año gana "
                                            "el bono a 10 años de ese momento. Vencimiento objetivo: el año 1 compras "
                                            "un bono a H años, el 2 a H−1… y todo vence el último año.")
            r1, r2 = st.columns(2)
            fuente = r1.selectbox("¿Cuánto rinde la renta fija?",
                                  ["Euribor 12m actual", "Bono euro 10 años actual", "Manual"], key="c_fuente",
                                  help="Solo se usa en el modo «Tipo constante».")
            if fuente == "Euribor 12m actual" and tipos.get("euribor12m") is not None:
                r_const = tipos["euribor12m"]
            elif fuente == "Bono euro 10 años actual" and tipos.get("bono10") is not None:
                r_const = tipos["bono10"]
            else:
                r_const = r2.number_input("Tipo anual manual (%)", -1.0, 15.0, 2.5, 0.1, key="c_rman") / 100
            r_const_nom = r_const
            r_const = rf_efectivo(r_const)
            if modo_rf == "Tipo constante":
                r2.caption(f"La renta fija rinde un **{pct(r_const_nom)}** al año"
                           + (f" (**{pct(r_const)}** real, con un {pct(infl_euro_esperada(), 1)} de inflación "
                              "esperada del euro)" if modo_real() else "") + ".")
            else:
                r2.caption("En este modo el rendimiento sale de la curva histórica del BCE (desde 2004).")

    ret, nivel, err = datos_indice(indice)
    if err or ret is None:
        st.error(f"No se han podido descargar los datos del índice: {err}")
        return
    curva = None
    if modo_rf != "Tipo constante":
        curva, e2 = datos_curva()
        if curva is None:
            st.error(f"Hace falta la curva de tipos del BCE para este modo: {e2}")
            return
    w = w_pct / 100
    H = int(H)
    aportado = inicial + aporte * H

    if metodo.startswith("Monte"):
        tray = montecarlo(ret.values, H, w, r_const, inicial, aporte, n=5000, m=m_apo)
        etiqueta = f"5.000 simulaciones (bloques de {bloque_mc()} años)"
        idx = None
    else:
        tray_df, idx = fin.ventanas_historicas(ret, curva, H, w, modo_rf, inicial, aporte, r_const, m_apo,
                                               infl_rf=inflacion_rf())
        if tray_df.empty:
            st.warning("No hay años suficientes en el histórico para ese horizonte con estos datos. "
                       "Reduce el horizonte o usa el modo «Tipo constante».")
            return
        tray = tray_df.values
        etiqueta = f"{len(tray_df)} periodos históricos reales"
    res = fin.resumen_trayectorias(tray, aportado, inicial, aporte, H, m_apo)

    if hold:
        intro = (f'Si inviertes <b>{eur(inicial)}</b> hoy, todo de golpe, y lo dejas <b>{H} años</b> sin tocarlo '
                 f'({w_pct} % en bolsa y {100 - w_pct} % en renta fija)')
    else:
        cada = "cada mes" if m_apo == 12 else "cada año"
        intro = (f'Si inviertes <b>{eur(inicial)}</b> hoy y añades <b>{eur(aporte)} al año</b> '
                 f'(repartidos {cada}) durante <b>{H} años</b> ({w_pct} % en bolsa y {100 - w_pct} % en renta fija)')
    st.markdown(
        f'<div class="resumen">{intro}, habrás puesto <b>{eur(aportado)}</b>. En un caso típico tendrías '
        f'<b>{eur(res["mediana"])}</b>; en un mal escenario (1 de cada 20), <b>{eur(res["p5"])}</b>; y en uno '
        f'bueno (1 de cada 20), <b>{eur(res["p95"])}</b>. Probabilidad de acabar con menos de lo que pusiste: '
        f'<b>{pct(res["prob_perdida"], 1)}</b>.</div>', unsafe_allow_html=True)

    m = st.columns(5)
    m[0].metric("Pondrás en total", eur(aportado))
    m[1].metric("Caso típico", eur(res["mediana"]), delta=f"{res['multiplo_mediana']:.2f}× lo aportado",
                delta_color="off", help="La mitad de los casos acaba por encima y la mitad por debajo (mediana).")
    m[2].metric("Mal escenario", eur(res["p5"]), help="Solo 1 de cada 20 casos acaba peor que esto (percentil 5).")
    m[3].metric("Buen escenario", eur(res["p95"]), help="Solo 1 de cada 20 casos acaba mejor que esto (percentil 95).")
    m[4].metric("Prob. de perder", pct(res["prob_perdida"], 1), help="Probabilidad de acabar con menos de lo aportado")

    t_cartera, t_plazos, t_obj = st.tabs(["📈 Tu cartera", "🗓️ A distintos plazos", "🎯 Objetivo y riesgos"])
    st.info("¿Quieres comparar repartos o estrategias, o ver el histórico del índice? Tienes las páginas "
            "**Comparador** y **Mercado** en el menú de la izquierda.", icon="ℹ️")

    # ------------------------------------------------------------ tu cartera
    with t_cartera:
        st.caption(f"{etiqueta}, con datos {ret.index.min()}–{ret.index.max()} (índice en dólares).")
        años = np.arange(1, H + 1)
        fig = go.Figure()
        if idx is not None:
            for fila, s0 in zip(tray, idx):
                fig.add_scatter(x=años, y=fila, mode="lines", line=dict(width=1, color="rgba(76,154,255,.35)"),
                                name=f"Inicio {s0}", hovertemplate=f"Inicio {s0}: %{{y:,.0f}} €<extra></extra>",
                                showlegend=False)
        else:
            p = np.percentile(tray, [5, 25, 75, 95], axis=0)
            fig.add_scatter(x=años, y=p[3], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
            fig.add_scatter(x=años, y=p[0], mode="lines", fill="tonexty", fillcolor="rgba(76,154,255,.15)",
                            line=dict(width=0), name="9 de cada 10 casos caen aquí")
            fig.add_scatter(x=años, y=p[2], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
            fig.add_scatter(x=años, y=p[1], mode="lines", fill="tonexty", fillcolor="rgba(76,154,255,.32)",
                            line=dict(width=0), name="La mitad de los casos cae aquí")
        fig.add_scatter(x=años, y=np.median(tray, axis=0), mode="lines", name="Caso típico",
                        line=dict(color=C_MEDIA, width=3))
        ap = np.cumsum(np.full(H, float(aporte))) + inicial
        fig.add_scatter(x=años, y=ap, mode="lines", name="Lo que has puesto", line=dict(color="#8B93A7", dash="dash"))
        fig.update_layout(xaxis_title="Años", yaxis_title="€")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("**¿Cómo crece mi dinero?**")
            explica("La línea naranja es el caso típico. Las zonas azules muestran cuánto puede variar el resultado.")
            st.plotly_chart(estilo(fig, 400), width="stretch")
        with c2:
            st.markdown("**¿Qué resultados finales son más probables?**")
            explica("Cuanto más alta la barra, más veces salió ese resultado. La línea naranja marca lo que pusiste.")
            hh = go.Figure(go.Histogram(x=tray[:, -1], nbinsx=40, marker_color=C_CAP, name="Casos"))
            hh.add_vline(x=aportado, line_dash="dash", line_color=C_INT, annotation_text="Lo que pusiste",
                         annotation_position="top")
            hh.update_layout(xaxis_title="€ al final", yaxis_title="Nº de casos")
            st.plotly_chart(estilo(hh, 400, "no"), width="stretch")

    # ------------------------------------------------------------ percentiles por horizonte
    with t_plazos:
        st.markdown("**¿Cuánto tendría según el plazo?**")
        explica("Monte Carlo con tu mismo reparto, mirando 1, 2, 3, 5… hasta 30 años. Cada grupo de barras es un "
                "plazo: de «mal escenario» (rojizo) a «buen escenario» (verde). La línea gris es lo que habrías puesto.")
        Hmax = max(30, H)
        mc = montecarlo(ret.values, Hmax, w, r_const, inicial, aporte, n=5000, m=m_apo)
        horizontes = [h for h in (1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 35, 40) if h <= Hmax]
        pcts = [(5, "Mal escenario (P5)", "#D55E00"), (25, "Algo peor que lo típico (P25)", "#F5A524"),
                (50, "Caso típico (P50)", "#4C9AFF"), (75, "Algo mejor que lo típico (P75)", "#2EC4A6"),
                (95, "Buen escenario (P95)", "#009E73")]
        etiquetas = [f"{h} años" for h in horizontes]
        pf = go.Figure()
        for q, nombre, color in pcts:
            pf.add_bar(x=etiquetas, y=[float(np.percentile(mc[:, h - 1], q)) for h in horizontes], name=nombre,
                       marker_color=color)
        pf.add_scatter(x=etiquetas, y=[inicial + aporte * h for h in horizontes], mode="lines+markers",
                       name="Lo que habrías puesto", line=dict(color="#8B93A7", dash="dash"))
        pf.update_layout(barmode="group", yaxis_title="€ acumulados", xaxis_title="Plazo")
        st.plotly_chart(estilo(pf, 440), width="stretch")
        tabla = pd.DataFrame({"Plazo": etiquetas,
                              "Pones en total": [inicial + aporte * h for h in horizontes],
                              "Mal escenario": [float(np.percentile(mc[:, h - 1], 5)) for h in horizontes],
                              "Caso típico": [float(np.percentile(mc[:, h - 1], 50)) for h in horizontes],
                              "Buen escenario": [float(np.percentile(mc[:, h - 1], 95)) for h in horizontes],
                              "Prob. de perder": [float(np.mean(mc[:, h - 1] < inicial + aporte * h))
                                                  for h in horizontes]})
        st.dataframe(tabla, hide_index=True, width="stretch", column_config={
            **{c: st.column_config.NumberColumn(format="%.0f €") for c in
               ["Pones en total", "Mal escenario", "Caso típico", "Buen escenario"]},
            "Prob. de perder": st.column_config.NumberColumn(format="percent")})
        st.caption(f"5.000 simulaciones con la renta fija al {pct(r_const)} constante. "
                   f"Sigues añadiendo {eur(aporte)} cada año.")

    # ------------------------------------------------------------ objetivo y riesgos
    with t_obj:
        st.markdown("**¿Qué probabilidad hay de llegar a mi objetivo?**")
        explica("Escribe la cantidad que te gustaría tener al final. Se cuenta en qué parte de los futuros posibles la "
                "alcanzas, y puedes ver todo en euros de hoy descontando la inflación.")
        o1, o2 = st.columns(2)
        meta = o1.number_input("Objetivo al final (€)", 100, 100_000_000, int(max(round(aportado * 1.5, -3), 1000)),
                               1_000, key="c_meta")
        if modo_real():
            infl_c = 0.0
            o2.caption("Estás en **modo real**: todas las cifras ya están en dinero de hoy.")
        else:
            infl_c = o2.number_input("Inflación para ver euros de hoy (% anual)", 0.0, 10.0, 2.0, 0.25,
                                     key="c_infl") / 100
        finales = tray[:, -1]
        deflactor = (1 + infl_c) ** H
        r1 = st.columns(4)
        r1[0].metric("Probabilidad de llegar", pct(float(np.mean(finales >= meta)), 0),
                     help="Parte de las trayectorias que acaba en el objetivo o por encima.")
        r1[1].metric("Caso típico en euros de hoy", eur(res["mediana"] / deflactor),
                     help=f"El caso típico ({eur(res['mediana'])}) descontando una inflación del {pct(infl_c)}.")
        r1[2].metric("Mal escenario en euros de hoy", eur(res["p5"] / deflactor))
        r1[3].metric("Objetivo en euros de hoy", eur(meta / deflactor),
                     help="Lo que valdrían hoy esos euros futuros.")
        pr = [float(np.mean(finales >= x)) for x in np.linspace(finales.min(), np.percentile(finales, 99), 60)]
        xs_o = np.linspace(finales.min(), np.percentile(finales, 99), 60)
        fo = go.Figure(go.Scatter(x=xs_o, y=np.array(pr) * 100, mode="lines", fill="tozeroy",
                                  line=dict(color=C_CAP, width=3), fillcolor="rgba(76,154,255,.15)",
                                  hovertemplate="Llegar a %{x:,.0f} €: %{y:.0f} % de probabilidad<extra></extra>"))
        fo.add_vline(x=meta, line_dash="dash", line_color=C_INT, annotation_text="Tu objetivo")
        fo.update_layout(xaxis_title="Cantidad final (€)", yaxis_title="Probabilidad de llegar (%)", yaxis_range=[0, 100])
        st.markdown("**Probabilidad de alcanzar cada cantidad**")
        st.plotly_chart(estilo(fo, 340, "no"), width="stretch")

        st.markdown("**¿Cómo habría ido empezando en el peor momento?**")
        explica("Con periodos reales: los años de inicio con peor y mejor resultado final (índice en dólares, renta "
                "fija a tipo constante). Sirve para ver el riesgo de «empezar justo antes de una crisis».")
        try:
            tdf, idx_h = fin.ventanas_historicas(ret, None, H, w, "Tipo constante", inicial, aporte, r_const, m_apo)
        except Exception as e:
            fin.registrar_error("Cartera peores inicios", e)
            tdf, idx_h = pd.DataFrame(), None
        if idx_h is not None and not tdf.empty:
            fin_h = pd.DataFrame({"Inicio": idx_h, "Final": tdf.values[:, -1]})
            fin_h["Múltiplo"] = fin_h["Final"] / aportado
            cc1, cc2 = st.columns(2)
            cfg = {"Final": st.column_config.NumberColumn(format="%.0f €"),
                   "Múltiplo": st.column_config.NumberColumn(format="%.2f×")}
            cc1.markdown("Peores inicios")
            cc1.dataframe(fin_h.nsmallest(5, "Final"), hide_index=True, width="stretch", column_config=cfg)
            cc2.markdown("Mejores inicios")
            cc2.dataframe(fin_h.nlargest(5, "Final"), hide_index=True, width="stretch", column_config=cfg)
        else:
            st.info("No hay años suficientes en el histórico para ese plazo.")

        st.markdown("**Exportar**")
        per = pd.DataFrame({"Año": np.arange(1, H + 1)})
        for q_ in (5, 25, 50, 75, 95):
            per[f"P{q_}"] = np.percentile(tray, q_, axis=0)
        per["Aportado"] = inicial + aporte * np.arange(1, H + 1)
        st.download_button("⬇️ Descargar percentiles por año (CSV)", per.to_csv(index=False, sep=";", decimal=",")
                           .encode("utf-8-sig"), "percentiles_cartera.csv", "text/csv", key="c_dl")

    st.caption("Resultados orientativos basados en el pasado; no son asesoramiento financiero. El índice está en "
               f"dólares (sin convertir a euros), sin comisiones ni impuestos, {etiqueta_modo()}.")
