"""Página Comparador."""
from ui import *  # noqa: F401,F403  (st, np, pd, go, fin y utilidades comunes)


def pag_comparador():
    titulo_pagina("⚖️", "Comparador", "Compara repartos bolsa/renta fija, estrategias y formas de modelar la renta fija")
    tipos, _ = tipos_actuales()
    with st.container(border=True):
        a1, a2, a3, a4 = st.columns(4)
        inicial = a1.number_input("Dinero que inviertes hoy (€)", 0, 50_000_000, 10_000, 1_000, key="k_ini")
        aporte = a2.number_input("Ahorro que añades cada año (€)", 0, 5_000_000, 3_000, 500, key="k_apo")
        H = int(a3.number_input("¿Durante cuántos años?", 1, 30, 10, 1, key="k_H"))
        frecuencia = a4.radio("Las aportaciones son", ["Mensuales", "Anuales"], horizontal=True, key="k_frec")
        m_apo = 12 if frecuencia == "Mensuales" else 1
        w_pct = st.slider("% en bolsa (pestañas 2 y 3)", 0, 100, 60, 5, key="k_rv",
                          help="La primera pestaña recorre todos los repartos; las otras usan este.")
        with st.expander("Opciones avanzadas: índice y renta fija"):
            b1, b3 = st.columns(2)
            indice = b1.selectbox("Índice de bolsa", list(fin.INDICES), key="k_idx")
            fuente = b3.selectbox("¿Cuánto rinde la renta fija?",
                                  ["Euribor 12m actual", "Bono euro 10 años actual", "Manual"], key="k_fuente")
            if fuente == "Euribor 12m actual" and tipos.get("euribor12m") is not None:
                r_const = tipos["euribor12m"]
            elif fuente == "Bono euro 10 años actual" and tipos.get("bono10") is not None:
                r_const = tipos["bono10"]
            else:
                r_const = b3.number_input("Tipo anual manual (%)", -1.0, 15.0, 2.5, 0.1, key="k_rman") / 100
            r_const = rf_efectivo(r_const)
    ret, nivel, err = datos_indice(indice)
    if err or ret is None:
        st.error(f"No se han podido descargar los datos del índice: {err}")
        return
    w = w_pct / 100
    aportado = inicial + aporte * H
    t_rep, t_est, t_rf, t_ab, t_fee = st.tabs(["⚖️ Reparto bolsa / renta fija", "🛒 Todo de golpe vs promediando",
                                               "🏦 Formas de modelar la renta fija", "👥 Cartera A vs B",
                                               "💸 Comisiones"])
    with t_rep:
        st.markdown("**¿Y si cambio el reparto entre bolsa y renta fija?**")
        explica("Cada punto es un reparto (0 % a 100 % en bolsa). Más a la derecha = más sube y baja. "
                "La línea continua es el caso típico; la de puntos, el mal escenario.")
        fr = frontera(ret.values, r_const, H, inicial, aporte, m=m_apo)
        f2 = go.Figure()
        f2.add_scatter(x=fr["Vol. anual"] * 100, y=fr["Mediana final"], mode="lines+markers+text",
                       text=[f"{int(x)} %" for x in fr["% renta variable"]], textposition="top center",
                       line=dict(color=C_CAP, width=3), name="Caso típico")
        f2.add_scatter(x=fr["Vol. anual"] * 100, y=fr["P5 final"], mode="lines+markers",
                       line=dict(color="#D55E00", width=2, dash="dot"), name="Mal escenario")
        f2.update_layout(xaxis_title="Cuánto sube y baja al año (%)", yaxis_title="€ al final")
        st.plotly_chart(estilo(f2, 380), width="stretch")
        fr_t = fr.rename(columns={"Vol. anual": "Sube y baja (anual)", "Mediana final": "Caso típico",
                                  "P5 final": "Mal escenario", "TIR mediana": "Rentab. anual típica"})
        st.dataframe(fr_t, hide_index=True, width="stretch", column_config={
            "Sube y baja (anual)": st.column_config.NumberColumn(format="percent"),
            "Peor año": st.column_config.NumberColumn(format="percent"),
            "Caso típico": st.column_config.NumberColumn(format="%.0f €"),
            "Mal escenario": st.column_config.NumberColumn(format="%.0f €"),
            "Prob. pérdida": st.column_config.NumberColumn(format="percent"),
            "Rentab. anual típica": st.column_config.NumberColumn(format="percent")})
        lim_p = st.select_slider("Quiero que la probabilidad de perder sea como mucho…", options=[0, 1, 2, 5, 10, 20],
                                 value=5, key="k_limp", format_func=lambda x: f"{x} %")
        ok_r = fr[fr["Prob. pérdida"] <= lim_p / 100]
        if ok_r.empty:
            st.info("Ningún reparto cumple ese límite con estos datos. Sube el límite o el número de años.")
        else:
            mejor = ok_r.sort_values("% renta variable").iloc[-1]
            st.success(f"Con ese límite, el reparto con más bolsa es **{int(mejor['% renta variable'])} % en bolsa**: "
                       f"caso típico {eur(mejor['Mediana final'])} y mal escenario {eur(mejor['P5 final'])}.")

    with t_est:
        if aporte <= 0:
            st.info("Pon un ahorro anual mayor que 0 para comparar con las aportaciones periódicas.")
        else:
            st.markdown("**¿Todo de golpe (buy and hold) o promediando?**")
            explica(f"Mismo dinero total ({eur(aportado)}) y mismo reparto. Todo de golpe: lo inviertes el primer día "
                    "y no tocas nada. Promediar: tu capital de hoy más las aportaciones periódicas que has elegido. "
                    "Todo de golpe suele ganar de media porque el dinero está más tiempo en el mercado, pero "
                    "promediar reduce el riesgo de entrar justo antes de una caída y no exige tener todo el dinero ya.")
            mc_h = montecarlo(ret.values, H, w, r_const, aportado, 0, n=5000, m=1)
            mc_p = montecarlo(ret.values, H, w, r_const, inicial, aporte, n=5000, m=m_apo)
            cmp_f = go.Figure()
            for nombre, mcx, color in (("Todo de golpe (buy and hold)", mc_h, C_CAP), ("Promediando", mc_p, C_INT)):
                cmp_f.add_bar(x=["Mal escenario", "Caso típico", "Buen escenario"],
                              y=[float(np.percentile(mcx[:, -1], q)) for q in (5, 50, 95)], name=nombre,
                              marker_color=color)
            cmp_f.update_layout(barmode="group", yaxis_title=f"€ al cabo de {H} años")
            st.plotly_chart(estilo(cmp_f, 360), width="stretch")
            st.dataframe(pd.DataFrame({
                "Estrategia": ["Todo de golpe (buy and hold)", "Promediando"],
                "Mal escenario": [float(np.percentile(x[:, -1], 5)) for x in (mc_h, mc_p)],
                "Caso típico": [float(np.percentile(x[:, -1], 50)) for x in (mc_h, mc_p)],
                "Buen escenario": [float(np.percentile(x[:, -1], 95)) for x in (mc_h, mc_p)],
                "Prob. de perder": [float(np.mean(x[:, -1] < aportado)) for x in (mc_h, mc_p)]}),
                hide_index=True, width="stretch", column_config={
                    **{c: st.column_config.NumberColumn(format="%.0f €") for c in
                       ["Mal escenario", "Caso típico", "Buen escenario"]},
                    "Prob. de perder": st.column_config.NumberColumn(format="percent")})

    with t_rf:
        st.markdown("**Tres formas de modelar la renta fija**")
        explica("Con periodos históricos reales. «Tipo constante»: rinde siempre lo mismo. «Carry»: cada año gana "
                "el bono a 10 años de ese momento. «Vencimiento objetivo» compra cada año un bono que vence al "
                "final del plazo (a H años, luego H−1…) con la curva del BCE de ese momento.")
        cv, e_cv = datos_curva()
        filas = []
        for mo in (fin.MODOS_RF if cv is not None else []):
            dd, _ = fin.ventanas_historicas(ret, cv, H, w, mo, inicial, aporte, r_const, m_apo,
                                            infl_rf=inflacion_rf())
            if dd.empty:
                continue
            s1 = fin.resumen_trayectorias(dd.values, aportado, inicial, aporte, H, m_apo)
            filas.append({"Renta fija": mo, "Periodos": len(dd), "Mal escenario": s1["p5"],
                          "Caso típico": s1["mediana"], "Buen escenario": s1["p95"],
                          "Prob. de perder": s1["prob_perdida"]})
        if filas:
            st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch", column_config={
                **{c: st.column_config.NumberColumn(format="%.0f €") for c in
                   ["Mal escenario", "Caso típico", "Buen escenario"]},
                "Prob. de perder": st.column_config.NumberColumn(format="percent")})
        else:
            st.info(f"No hay datos de la curva del BCE para esta comparación. {e_cv or ''}")

    with t_ab:
        explica("Compara dos repartos con el mismo dinero, plazo y aportaciones. La línea es el caso típico y la banda, "
                "9 de cada 10 casos.")
        u1, u2 = st.columns(2)
        wa = u1.slider("Cartera A: % en bolsa", 0, 100, 40, 5, key="k_wa")
        wb = u2.slider("Cartera B: % en bolsa", 0, 100, 80, 5, key="k_wb")
        mcs = {"A": montecarlo(ret.values, H, wa / 100, r_const, inicial, aporte, n=5000, m=m_apo),
               "B": montecarlo(ret.values, H, wb / 100, r_const, inicial, aporte, n=5000, m=m_apo)}
        pesos_lbl = {"A": wa, "B": wb}
        cols_ab = {"A": C_CAP, "B": C_INT}
        años_ab = np.arange(1, H + 1)
        fab = go.Figure()
        for k_, mcx in mcs.items():
            p_ = np.percentile(mcx, [5, 50, 95], axis=0)
            fab.add_scatter(x=años_ab, y=p_[2], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
            fab.add_scatter(x=años_ab, y=p_[0], mode="lines", fill="tonexty",
                            fillcolor="rgba(76,154,255,.15)" if k_ == "A" else "rgba(245,165,36,.15)",
                            line=dict(width=0), showlegend=False, hoverinfo="skip")
            fab.add_scatter(x=años_ab, y=p_[1], mode="lines", name=f"{k_} ({pesos_lbl[k_]} % bolsa)",
                            line=dict(color=cols_ab[k_], width=3))
        fab.add_scatter(x=años_ab, y=inicial + aporte * años_ab, mode="lines", name="Lo que pones",
                        line=dict(color="#8B93A7", dash="dash"))
        fab.update_layout(xaxis_title="Años", yaxis_title="€")
        st.plotly_chart(estilo(fab, 380), width="stretch")
        st.dataframe(pd.DataFrame([{
            "Cartera": f"{k_} ({pesos_lbl[k_]} % bolsa)", "Mal escenario": float(np.percentile(x[:, -1], 5)),
            "Caso típico": float(np.median(x[:, -1])), "Buen escenario": float(np.percentile(x[:, -1], 95)),
            "Prob. de perder": float(np.mean(x[:, -1] < aportado)),
            "TIR típica": float(np.median((x[:, -1] / aportado) ** (1 / H) - 1))} for k_, x in mcs.items()]),
            hide_index=True, width="stretch", column_config={
                **{c: st.column_config.NumberColumn(format="%.0f €") for c in
                   ["Mal escenario", "Caso típico", "Buen escenario"]},
                "Prob. de perder": st.column_config.NumberColumn(format="percent"),
                "TIR típica": st.column_config.NumberColumn(format="percent")})

    with t_fee:
        explica("Las comisiones se llevan una parte de la rentabilidad cada año. Aquí se resta a la bolsa la comisión "
                "anual (TER) y se compara lo que tendrías al final. Un 1 % parece poco, pero compuesto durante años "
                "pesa mucho.")
        fees = [0.0, 0.1, 0.5, 1.0, 1.5, 2.0]
        sel_fees = st.multiselect("Comisiones anuales a comparar (%)", fees, default=[0.0, 0.5, 1.5], key="k_fees")
        filas_f, fig_f = [], go.Figure()
        base_med = None
        for fe in sorted(sel_fees):
            mcf = montecarlo(ret.values - fe / 100, H, w, r_const, inicial, aporte, n=5000, m=m_apo)
            med = float(np.median(mcf[:, -1]))
            if base_med is None:
                base_med = med
            filas_f.append({"Comisión": f"{fe:.1f} %", "Caso típico": med, "Mal escenario": float(np.percentile(mcf[:, -1], 5)),
                            "Pierdes por comisiones": base_med - med})
            fig_f.add_scatter(x=np.arange(1, H + 1), y=np.median(mcf, axis=0), mode="lines", name=f"{fe:.1f} %")
        fig_f.update_layout(xaxis_title="Años", yaxis_title="€ (caso típico)")
        if filas_f:
            st.plotly_chart(estilo(fig_f, 360), width="stretch")
            st.dataframe(pd.DataFrame(filas_f), hide_index=True, width="stretch", column_config={
                c: st.column_config.NumberColumn(format="%.0f €") for c in
                ["Caso típico", "Mal escenario", "Pierdes por comisiones"]})
            st.caption("La comisión se aplica a la parte en bolsa. Misma semilla en todos los casos, así la "
                       "diferencia se debe solo a la comisión.")

    st.caption("Resultados orientativos basados en el pasado; no son asesoramiento financiero.")
