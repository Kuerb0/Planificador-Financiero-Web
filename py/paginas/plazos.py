"""Página Plazos y probabilidad de perder."""
from ui import *  # noqa: F401,F403  (st, np, pd, go, fin y utilidades comunes)


def _color_mezcla(w):
    """Del azul (0 % bolsa) al naranja (100 % bolsa)."""
    c0, c1 = (76, 154, 255), (245, 165, 36)
    return "rgb({},{},{})".format(*[int(c0[k] + (c1[k] - c0[k]) * w) for k in range(3)])


def pag_plazos():
    titulo_pagina("⏳", "Plazos y riesgo", "¿Cuántos años hacen falta para que sea raro perder dinero?")
    with st.expander("ℹ️ Qué significa esta página"):
        st.markdown("Se miran **todas las ventanas posibles del pasado** (aunque se solapen) de cada duración y "
                    "se cuenta en cuántas acabarías con menos dinero del que pusiste. Cuanto más largo el plazo, "
                    "menos ventanas pierden. La curva se suaviza con una media móvil de 52 semanas y la rentabilidad "
                    "se expresa como TIR anualizada.")
    tipos, _ = tipos_actuales()
    rf_def = tipos.get("euribor12m") if tipos.get("euribor12m") is not None else 0.025
    st.session_state.setdefault("p_rv", 60)
    with st.container(border=True):
        p2, p4 = st.columns([2, 3])
        w_pct = p2.slider("Tu reparto: % en bolsa (el resto, renta fija)", 0, 100, key="p_rv", step=5)
        estrategia_ph = p4
        with st.expander("Opciones avanzadas: índice y renta fija"):
            p1, p3 = st.columns(2)
            indice = p1.selectbox("Índice de bolsa", list(fin.INDICES), key="p_idx",
                                  help="En dólares y con dividendos. Cuanto más largo es el histórico, más fiable.")
            r_rf = rf_efectivo(p3.number_input("Rentabilidad de la renta fija (% al año, nominal)", -1.0, 15.0,
                                               round(rf_def * 100, 2), 0.1, key="p_rf") / 100)
        estrategia = estrategia_ph.radio("Estrategia", ["Buy and hold (todo el primer día)",
                                             "DCA (aportaciones iguales cada semana)"], horizontal=True,
                              key="p_estr",
                              help="Buy and hold: inviertes todo el dinero el primer día y esperas. DCA: repartes el "
                                   "mismo dinero en aportaciones iguales cada semana durante todo el plazo.")
    ret, nivel, err = datos_indice(indice)
    if err or nivel is None:
        st.error(f"No se han podido descargar los datos del índice: {err}")
        return
    w = w_pct / 100
    dca = estrategia.startswith("DCA")
    pesos = tuple(sorted(set([i / 10 for i in range(11)] + [w])))
    raw, suav, err2 = curvas_plazos(indice, round(r_rf, 6), pesos, "dca" if dca else "hold")
    if suav is None or suav.empty:
        st.error(f"No se han podido calcular las curvas semanales: {err2 or 'histórico demasiado corto'}")
        return
    nom = "DCA" if dca else "Buy and hold"

    def prob(anios, col=w):
        h = int(round(anios * 52))
        return float(suav.loc[h, col]) if h in suav.index else None
    frases = []
    for h in (1, 5, 10, 20):
        p = prob(h)
        if p is not None:
            frases.append(f"en <b>{h} año{'s' if h > 1 else ''}</b>, el <b>{pct(p, 0)}</b>")
    st.markdown(f'<div class="resumen">{nom} con {w_pct} % en bolsa. Veces que habrías perdido dinero: '
                + "; ".join(frases) + ". Cuanto más tiempo mantienes la inversión, más raro es acabar por debajo de "
                "lo que pusiste.</div>", unsafe_allow_html=True)
    n_sem = len(serie_semanal(indice))
    indep = ", ".join(f"{h} años → {fin.ventanas_independientes(n_sem, h * 52)}" for h in (5, 10, 20)
                      if fin.ventanas_independientes(n_sem, h * 52) > 0)
    st.caption(f"⚠️ Las ventanas se solapan: con {n_sem / 52:.0f} años de historia solo hay estas ventanas que no "
               f"comparten datos: {indep}. Las probabilidades a plazos largos se apoyan en muy pocos casos "
               "independientes; tómalas como orientación, no como certeza.")

    t_prob, t_tabla, t_rent, t_mas = st.tabs(["📉 Probabilidad de perder", "🔢 Tabla de equivalencias",
                                              "📊 TIR según el plazo (buy and hold)", "🔬 Más análisis"])

    with t_prob:
        st.markdown(f"**¿Cuántas veces habrías perdido dinero según el plazo? ({nom})**")
        explica("Una curva por cada reparto entre bolsa y renta fija, del azul (0 % bolsa) al naranja (100 % bolsa). "
                "Se calcula para cada plazo semana a semana (de 1 semana a 30 años) con ventanas que empiezan cada "
                "semana y se solapan, y se suaviza con la media móvil de 52 plazos. Solo se dibujan los puntos con 52 "
                "semanas completas, por eso las curvas empiezan en unos 6 meses.")
        g = go.Figure()
        for c in suav.columns:
            es_tuyo = abs(c - w) < 1e-9
            g.add_scatter(x=suav.index / 52, y=suav[c] * 100, mode="lines",
                          name=f"Tu reparto ({int(round(c * 100))} % bolsa)" if es_tuyo else f"{int(round(c * 100))} % bolsa",
                          line=dict(color=_color_mezcla(c), width=4.5 if es_tuyo else 1.8),
                          hovertemplate=f"{int(round(c * 100))} % bolsa · %{{x:.1f}} años: %{{y:.1f}} %<extra></extra>")
        if st.checkbox("Mostrar también tu reparto sin suavizar", key="p_raw"):
            g.add_scatter(x=raw.index / 52, y=raw[w] * 100, mode="lines", name="Tu reparto sin suavizar",
                          line=dict(color="rgba(255,255,255,.45)", width=1, dash="dot"))
        g.update_layout(xaxis_title="Años que mantienes la inversión", yaxis_title="Veces que habrías perdido dinero (%)",
                        yaxis_range=[0, max(5.0, float(suav.max().max()) * 100 * 1.05)])
        st.plotly_chart(estilo(g, 480), width="stretch")

        st.markdown("**¿Cuántos años necesito?**")
        riesgo = st.select_slider("Quiero que la probabilidad de perder sea como mucho…",
                                  options=[0, 1, 2, 5, 10, 20], value=5, key="p_max", format_func=lambda x: f"{x} %")

        def anios_txt(col):
            sem = fin.semanas_para_riesgo(suav[col], riesgo / 100)
            return num(sem / 52, 1) + " años" if sem else "No se alcanza en el histórico"
        k1, k2 = st.columns(2)
        k1.metric(f"Tu reparto ({w_pct} % bolsa)", anios_txt(w))
        k2.metric("100 % bolsa", anios_txt(1.0))
        st.caption("Con plazos largos casi todas las ventanas comparten años, así que hay pocas realmente distintas. "
                   "Tómalo como una pauta, no como una garantía.")

    with t_tabla:
        explica(f"Años ↔ probabilidad de perder dinero ({nom}), para cada reparto. Cada columna es un porcentaje en bolsa.")
        filas = {}
        for y in range(1, 31):
            h = y * 52
            if h in suav.index:
                filas[y] = {f"{int(round(c * 100))} % bolsa": float(suav.loc[h, c]) for c in suav.columns}
        if filas:
            tabla = pd.DataFrame(filas).T
            tabla.index.name = "Años"
            tabla = tabla.reset_index()
            st.dataframe(tabla, hide_index=True, width="stretch", height=480, column_config={
                c: st.column_config.NumberColumn(format="percent") for c in tabla.columns if c != "Años"})

    with t_rent:
        explica("TIR anualizada de cada ventana (la rentabilidad anual constante que convierte lo invertido en lo "
                "obtenido), con buy and hold, ventanas que empiezan cada año y tu reparto.")
        base_n = np.concatenate([[1.0], np.cumprod(1 + ret.values)])
        df = fin.ventanas_moviles(base_n, list(range(1, 31)), w, r_rf, 1)
        if df.empty:
            st.info("El histórico de este índice es demasiado corto.")
        else:
            x = df.anios
            b = go.Figure()
            b.add_scatter(x=x, y=df.mejor * 100, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
            b.add_scatter(x=x, y=df.peor * 100, mode="lines", fill="tonexty", fillcolor="rgba(76,154,255,.12)",
                          line=dict(width=0), name="Entre la peor y la mejor ventana")
            b.add_scatter(x=x, y=df.p95 * 100, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
            b.add_scatter(x=x, y=df.p5 * 100, mode="lines", fill="tonexty", fillcolor="rgba(76,154,255,.28)",
                          line=dict(width=0), name="9 de cada 10 ventanas")
            b.add_scatter(x=x, y=df.mediana * 100, mode="lines", line=dict(color=C_MEDIA, width=3),
                          name="Ventana típica")
            b.add_hline(y=0, line_dash="dash", line_color="#8B93A7")
            b.update_layout(xaxis_title="Años que mantienes la inversión", yaxis_title="TIR anualizada (%)")
            st.plotly_chart(estilo(b, 420), width="stretch")
            ind = df.set_index("anios")["independientes"]
            st.caption("Ventanas sin datos en común detrás de cada plazo: "
                       + ", ".join(f"{h} años → {int(ind[h])}" for h in (5, 10, 20, 30) if h in ind.index)
                       + ". Con tan pocas, los extremos (mejor y peor) dependen de uno o dos episodios concretos.")
    with t_mas:
        v_sem = serie_semanal(indice)
        # ------------------------------------------------ pérdida máxima
        st.markdown("**¿Cuánto podría llegar a perder?**")
        explica(f"Valor de 100 € invertidos con tu reparto ({w_pct} % bolsa) según los años, en distintos escenarios "
                "históricos (1 de cada 100, 1 de cada 20, la mitad, 1 de cada 20 mejores). Buy and hold.")
        ys_m = np.arange(1, 20.01, 0.5)
        fm = go.Figure()
        estilos_m = [(1, "Muy mal (1 de cada 100)", "#D55E00"), (5, "Mal (1 de cada 20)", "#F5A524"),
                     (50, "Típico", "#4C9AFF"), (95, "Muy bien (1 de cada 20)", "#009E73")]
        tablas_m = {}
        for q_, nom_q, col_q in estilos_m:
            tq = fin.mal_escenario(v_sem, [w], r_rf, ys_m, q_)
            if tq.empty:
                continue
            vals = 100 * (1 + tq[w].values) ** tq.index.values
            tablas_m[nom_q] = pd.Series(vals, index=tq.index)
            fm.add_scatter(x=tq.index, y=vals, mode="lines", name=nom_q, line=dict(color=col_q, width=2.5))
        fm.add_hline(y=100, line_dash="dash", line_color="#8B93A7", annotation_text="Lo invertido")
        fm.update_layout(xaxis_title="Años que mantienes la inversión", yaxis_title="Valor de 100 € invertidos")
        st.plotly_chart(estilo(fm, 400), width="stretch")

        # ------------------------------------------------ prob. de caída grande
        st.markdown("**¿Y perder más de un porcentaje concreto?**")
        explica("Probabilidad de acabar con menos de lo invertido menos X %, según los años. Un 10 % significa que "
                "100 € se quedan en menos de 90 €.")
        ys_c = np.arange(1, 10.01, 0.5)
        fc = go.Figure()
        for u_, col_c in ((0.0, "#4C9AFF"), (0.1, "#F5A524"), (0.2, "#D55E00"), (0.3, "#A78BFA")):
            fc.add_scatter(x=ys_c, y=fin.prob_caida_mayor(v_sem, w, r_rf, ys_c, u_) * 100, mode="lines",
                           name="Perder dinero" if u_ == 0 else f"Perder más del {int(u_ * 100)} %",
                           line=dict(color=col_c, width=2.5))
        fc.update_layout(xaxis_title="Años que mantienes la inversión", yaxis_title="Probabilidad (%)")
        st.plotly_chart(estilo(fc, 360), width="stretch")

        # ------------------------------------------------ comparar índices
        st.markdown("**¿Cambia según el índice?**")
        explica("La probabilidad de perder (buy and hold) con tu mismo reparto para otros índices. Con menos "
                "histórico los resultados son menos fiables.")
        elegidos = st.multiselect("Índices a comparar", list(fin.INDICES), default=[indice], key="p_cmp")
        fi = go.Figure()
        for nombre_i in elegidos:
            _, sv_i, e_i = curvas_plazos(nombre_i, round(r_rf, 6), (w,), "hold")
            if sv_i is None or sv_i.empty:
                st.warning(f"{nombre_i}: {e_i or 'sin datos'}")
                continue
            fi.add_scatter(x=sv_i.index / 52, y=sv_i[w] * 100, mode="lines", name=nombre_i.split(":")[0])
        fi.update_layout(xaxis_title="Años que mantienes la inversión", yaxis_title="Veces que habrías perdido (%)")
        st.plotly_chart(estilo(fi, 380), width="stretch")

        if tablas_m:
            exp = pd.DataFrame(tablas_m)
            exp.index.name = "Años"
            st.download_button("⬇️ Descargar valores por plazo (CSV)",
                               exp.reset_index().to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                               "plazos_escenarios.csv", "text/csv", key="p_dl")

    st.caption(f"Datos: {nivel.index[0]:%m/%Y}–{nivel.index[-1]:%m/%Y} ({len(ret)} años completos, en dólares, con "
               "dividendos). Pérdida = acabar con menos dinero que el total invertido"
               + (" en dinero de hoy (perder poder adquisitivo). " if modo_real() else ", sin contar la inflación. ")
               + "Resultados orientativos; no son asesoramiento financiero.")
