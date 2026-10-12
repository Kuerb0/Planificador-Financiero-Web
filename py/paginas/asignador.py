"""Página Asignador de carteras."""
from ui import *  # noqa: F401,F403  (st, np, pd, go, fin y utilidades comunes)


def pag_asignador():
    titulo_pagina("🧩", "Asignador", "Qué porcentaje de bolsa te conviene según tu perfil de riesgo y el tiempo que te queda")
    with st.expander("ℹ️ Cómo se calcula"):
        st.markdown(
            "1. **Tu nota del test** (Grable-Lytton) se convierte en una **nota T**: la escala estándar de la psicometría, "
            "con media 50 y desviación 10. Con ±5 desviaciones cubre justo de 0 a 100, así que esa nota se lee "
            "directamente como **% de renta variable ideal** (0 = todo renta fija, 100 = todo bolsa; los extremos son "
            "muy improbables).\n"
            "2. **El tiempo ajusta ese ideal.** Para cada tramo de años que queda se miran todas las ventanas del "
            "pasado y se calcula el **mal escenario anualizado** (el 1 de cada 20 peor, en TIR anualizada) de cada "
            "reparto. Se recomienda la **mayor bolsa, sin pasar de tu ideal, cuyo mal escenario no baje de un "
            "suelo anual** (2 % por defecto, más o menos la inflación).\n"
            "3. Con pocos años, mucha bolsa tiene un mal escenario muy malo, así que se recorta; con muchos años "
            "el mal escenario mejora y se llega a tu ideal. La curva se suaviza con una media móvil.\n"
            "4. Según te acercas al final, la recomendación **baja sola** (senda de desriesgo).")
    perfiles = fin.leer_perfiles()
    usuarios = list(perfiles["usuarios"])
    mn, mx = fin.puntuacion_min_max()
    tipos, _ = tipos_actuales()
    rf_def = tipos.get("euribor12m") if tipos.get("euribor12m") is not None else 0.025
    with st.container(border=True):
        a1, a2, a3 = st.columns([2, 2, 2])
        opciones = usuarios + ["Introducir la nota a mano"]
        ya = perfiles.get("activo")
        quien = a1.selectbox("Perfil", opciones, index=(opciones.index(ya) if ya in opciones else len(opciones) - 1),
                             key="s_user", help="Usa la nota del test de riesgo guardada para esa persona.")
        if quien in usuarios:
            puntos = int(perfiles["usuarios"][quien]["puntuacion"])
            a2.metric("Nota del test", f"{puntos} / {mx}")
        else:
            puntos = a2.number_input(f"Nota del test ({mn}-{mx})", mn, mx, 25, 1, key="s_pts")
            if not usuarios:
                a2.caption("Aún no hay perfiles: haz el test de riesgo para guardar tu nota.")
        horiz = a3.slider("¿Cuántos años faltan para necesitar el dinero?", 1, 30, 10, 1, key="s_h",
                          help="Tu preferencia temporal: cuanto menos tiempo, menos bolsa conviene.")
        with st.expander("Opciones avanzadas: escala, años hasta el ideal, riesgo aceptado e índice"):
            b1, b2, b3 = st.columns(3)
            media = b1.number_input("Media de la escala", 10.0, 45.0, float(fin.NORMA_TEST[0]), 0.5, key="s_mu",
                                    help="Nota media de la población. No hay normas publicadas de la escala: por "
                                         "defecto se deduce de los tramos oficiales (normal = 23-28).")
            sd = b2.number_input("Desviación de la escala", 2.0, 12.0, float(fin.NORMA_TEST[1]), 0.5, key="s_sd",
                                 help="Cuanto menor, más se acercan las notas extremas al 0 % o al 100 % de bolsa.")
            suelo = b3.number_input("Suelo del mal escenario (% anual)", -5.0, 8.0, 2.0, 0.5, key="s_suelo",
                                    help="El mal escenario de cada reparto, expresado como rentabilidad anual, no "
                                         "puede quedar por debajo de esto. Más alto = más prudente.") / 100
            c1, c2 = st.columns(2)
            q_mal = c1.selectbox("Qué es un «mal escenario»", ["1 de cada 20 (percentil 5)", "1 de cada 10 (percentil 10)",
                                                              "1 de cada 100 (percentil 1)"], key="s_q",
                                 help="Cuántas ventanas históricas peores se dejan fuera.")
            suav_a = c2.slider("Suavizado de la curva (años)", 0, 5, 3, 1, key="s_suav",
                               help="Media móvil sobre los años que quedan. 0 = sin suavizar (puede haber saltos).")
            d1, d2, d3 = st.columns(3)
            indice = d1.selectbox("Índice de bolsa", list(fin.INDICES), key="s_idx")
            r_rf = rf_efectivo(d2.number_input("Rentabilidad de la renta fija (% al año, nominal)", -1.0, 15.0,
                                               round(rf_def * 100, 2), 0.1, key="s_rf") / 100)
            estr = d3.radio("Estrategia al invertir", ["Buy and hold", "DCA (aportaciones semanales)"], key="s_estr")
    w_ideal, t, perc = fin.rv_ideal_desde_puntos(puntos, media, sd)
    w_ideal = round(w_ideal, 4)
    pesos = tuple(sorted(set([i / 50 for i in range(51)] + [w_ideal])))
    raw, suav, err = curvas_plazos(indice, round(r_rf, 6), pesos, "dca" if estr.startswith("DCA") else "hold")
    if suav is None or suav.empty:
        st.error(f"No se han podido calcular las probabilidades: {err or 'histórico demasiado corto'}")
        return
    q_pct = {"1 de cada 20": 5, "1 de cada 10": 10, "1 de cada 100": 1}[q_mal.split(" (")[0]]
    tabla_me = tabla_mal_escenario(indice, round(r_rf, 6), pesos, q_pct)
    if tabla_me is None or tabla_me.empty:
        st.error("No se ha podido calcular el mal escenario: histórico demasiado corto.")
        return
    senda = fin.senda_mal_escenario(tabla_me, w_ideal, suelo, suavizado=int(suav_a) * 2)
    rv_hoy = min(fin.rv_en(senda, horiz), w_ideal)
    pr_ideal = float(fin._fila_plazo(suav, horiz * 52)[min(suav.columns, key=lambda c: abs(c - w_ideal))])
    pr_rec = float(fin._fila_plazo(suav, horiz * 52)[min(suav.columns, key=lambda c: abs(c - rv_hoy))])

    st.markdown(
        f'<div class="resumen">Con tu nota ({puntos}) tu reparto ideal sería <b>{pct(w_ideal, 0)} en bolsa</b>. '
        f'Como solo te quedan <b>{horiz} año{"s" if horiz > 1 else ""}</b>, lo razonable es empezar con '
        f'<b>{pct(rv_hoy, 0)} en bolsa y {pct(1 - rv_hoy, 0)} en renta fija</b>'
        + (", sin recortes." if rv_hoy >= w_ideal - 1e-9 else
           f" (recorte de {pct(w_ideal - rv_hoy, 0)} por el poco tiempo) y bajarlo según te acerques al final")
        + f'. Probabilidad de acabar con menos de lo invertido: <b>{pct(pr_rec, 1)}</b> '
        f'(con el ideal sería {pct(pr_ideal, 1)}).</div>', unsafe_allow_html=True)

    m = st.columns(5)
    m[0].metric("Nota T", f"{t:.0f}", help="Escala estándar: media 50, desviación 10. Se lee como % de bolsa ideal.")
    m[1].metric("Percentil", f"{perc * 100:.0f} %", help="Qué porcentaje de la población tendría una nota menor.")
    m[2].metric("Bolsa ideal", pct(w_ideal, 0))
    m[3].metric("Bolsa recomendada hoy", pct(rv_hoy, 0), delta=f"{(rv_hoy - w_ideal) * 100:+.0f} puntos"
                if rv_hoy < w_ideal - 1e-9 else None, delta_color="off")
    m[4].metric("Suelo del mal escenario", pct(suelo, 1) + " anual",
                help="El mal escenario de tu reparto, en rentabilidad anual, no baja de aquí.")

    t_rec, t_sim, t_mat = st.tabs(["🎯 Recomendación", "🧪 Simulación dinámica", "🗂️ Perfiles y plazos"])
    with t_rec:
        g1, g2 = st.columns(2, gap="large")
        with g1:
            st.markdown("**De tu nota al reparto ideal**")
            explica("La campana es la población; tu nota (línea naranja) se lee directamente como % de bolsa.")
            xs = np.linspace(0, 100, 401)
            dens = np.exp(-0.5 * ((xs - 50) / 10) ** 2) / (10 * np.sqrt(2 * np.pi))
            fb = go.Figure()
            fb.add_scatter(x=xs, y=dens, mode="lines", fill="tozeroy", fillcolor="rgba(76,154,255,.18)",
                           line=dict(color=C_CAP, width=2.5), name="Población", hoverinfo="skip")
            fb.add_vline(x=float(np.clip(t, 0, 100)), line_color=C_INT, line_width=3,
                         annotation_text=f"Tú: {pct(w_ideal, 0)} bolsa", annotation_position="top")
            fb.update_layout(xaxis_title="Nota T = % de renta variable ideal", yaxis=dict(visible=False))
            st.plotly_chart(estilo(fb, 380, "no"), width="stretch")
        with g2:
            st.markdown("**¿Cuánta bolsa según los años que quedan?**")
            explica("Cada punto sale del mal escenario histórico de ese plazo. La línea discontinua es tu ideal; el punto "
                    "marca dónde estás ahora.")
            fs = go.Figure()
            fs.add_scatter(x=senda["anios"], y=senda["rv"] * 100, mode="lines", line=dict(color=C_INT, width=3.5),
                           name="Recomendado")
            fs.add_hline(y=w_ideal * 100, line_dash="dash", line_color="#8B93A7", annotation_text="Tu ideal")
            fs.add_scatter(x=[horiz], y=[rv_hoy * 100], mode="markers", marker=dict(size=13, color=C_CAP,
                           line=dict(width=2, color="white")), name="Tu situación")
            fs.update_layout(xaxis_title="Años que quedan", yaxis_title="% en bolsa", yaxis_range=[0, 100])
            st.plotly_chart(estilo(fs, 380), width="stretch")

        st.markdown("**Tu plan año a año**")
        explica(f"Cada año se mira la cartera con la que entras (la que quedó del año anterior) y se calcula su mal "
                f"escenario con los años que quedan. Si baja del suelo ({pct(suelo, 1)} anual), se recorta justo lo "
                "necesario y esa nueva cartera es la de entrada del año siguiente.")
        filas = []
        w_in = w_ideal
        for k in range(horiz):
            rest = horiz - k
            me = fin.mal_escenario_de(tabla_me, w_in, rest)
            w_out = min(w_in, fin.rv_en(senda, rest), w_ideal)
            filas.append({"Año": k + 1, "Años que quedan": rest, "Entras con": w_in, "Mal escenario de esa cartera": me,
                          "Ajustas a": w_out, "Renta fija": 1 - w_out})
            w_in = w_out
        plan = pd.DataFrame(filas)
        fp = go.Figure()
        fp.add_bar(x=plan["Año"], y=plan["Ajustas a"] * 100, name="Bolsa", marker_color=C_INT)
        fp.add_bar(x=plan["Año"], y=plan["Renta fija"] * 100, name="Renta fija", marker_color=C_CAP)
        fp.update_layout(barmode="stack", xaxis_title="Año del plan", yaxis_title="%", yaxis_range=[0, 100])
        h1, h2 = st.columns([2, 3], gap="large")
        with h1:
            st.plotly_chart(estilo(fp, 340), width="stretch")
        with h2:
            st.dataframe(plan.drop(columns=["Renta fija"]), hide_index=True, width="stretch", height=340, column_config={
                "Entras con": st.column_config.NumberColumn("Entras con (bolsa)", format="percent"),
                "Mal escenario de esa cartera": st.column_config.NumberColumn("Mal escenario (anual)", format="percent",
                                                                              help="Rentabilidad anual del 1 de cada 20 "
                                                                                   "peor a los años que quedan."),
                "Ajustas a": st.column_config.NumberColumn("Ajustas a (bolsa)", format="percent")})

        st.download_button("⬇️ Descargar el plan (CSV)", plan.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           file_name="plan_asignador.csv", mime="text/csv", key="s_dl")

    # ================================================================ simulación dinámica
    with t_sim:
        explica("Aquí la cartera es la que realmente tendrías: cada año su peso en bolsa se mueve con el mercado "
                "(si la bolsa sube, pesa más). Cada año se mira esa cartera, se calcula su mal escenario con los años "
                "que quedan y, si baja del suelo, se recorta a la mayor bolsa que lo cumple. Se prueba con cada "
                "ventana histórica o con miles de futuros posibles.")
        s1, s2, s3 = st.columns(3)
        H_sim = int(s1.slider("Años del plan", 3, 29, min(max(horiz, 3), 29), 1, key="s_hsim"))
        met_sim = s2.radio("Método", ["Ventanas históricas", "Monte Carlo (5.000)"], key="s_msim",
                           help="Ventanas históricas: cada semana de inicio posible del pasado. Monte Carlo: sortea "
                                "años reales de la bolsa.")
        inv = s3.number_input("Dinero invertido (€)", 100, 50_000_000, 10_000, 500, key="s_inv")
        if met_sim.startswith("Ventanas"):
            try:
                R = fin.matriz_rentabilidades(serie_semanal(indice), H_sim)
            except Exception as e:
                st.error(f"No hay histórico suficiente para ese plazo: {e}")
                R = None
        else:
            ret_a, _, err_a = datos_indice(indice)
            R = None if ret_a is None else 1 + fin.muestras_bloques(ret_a.values, 5000, H_sim, bloque_mc())
        if R is not None:
            sim = fin.simular_dinamico(R, w_ideal, r_rf, tabla_me, suelo)
            senda_h = fin.senda_mal_escenario(tabla_me, w_ideal, suelo, suavizado=int(suav_a) * 2)
            pesos_plan = [min(fin.rv_en(senda_h, H_sim - y), w_ideal) for y in range(H_sim)]
            variantes = {"Dinámica (tu cartera real)": sim["final"],
                         "Plan fijo (rebalancea cada año)": fin.simular_senda(R, pesos_plan, r_rf),
                         f"Siempre {pct(w_ideal, 0)} en bolsa": fin.simular_fijo(R, w_ideal, r_rf)}
            filas_v = []
            for nombre, x in variantes.items():
                tir = x ** (1 / H_sim) - 1
                filas_v.append({"Estrategia": nombre, "Mal escenario": inv * float(np.percentile(x, 5)),
                                "Caso típico": inv * float(np.median(x)), "Buen escenario": inv * float(np.percentile(x, 95)),
                                "TIR típica": float(np.median(tir)), "TIR mal escenario": float(np.percentile(tir, 5)),
                                "Prob. de perder": float(np.mean(x < 1))})
            st.markdown("**Resultado final de cada estrategia**")
            st.dataframe(pd.DataFrame(filas_v), hide_index=True, width="stretch", column_config={
                **{c: st.column_config.NumberColumn(format="%.0f €") for c in
                   ["Mal escenario", "Caso típico", "Buen escenario"]},
                **{c: st.column_config.NumberColumn(format="percent") for c in
                   ["TIR típica", "TIR mal escenario", "Prob. de perder"]}})
            k1, k2, k3 = st.columns(3)
            k1.metric("Recortes por trayectoria (media)", f"{sim['recortes'].mean():.1f}",
                      help="Cuántos años, de media, hay que recortar bolsa porque la cartera real se pasa de riesgo.")
            k2.metric("Bolsa media al principio", pct(float(sim["pesos"][:, 0].mean()), 0))
            k3.metric("Bolsa media al final", pct(float(sim["pesos"][:, -1].mean()), 0))
            e1, e2 = st.columns(2, gap="large")
            with e1:
                st.markdown("**¿Cómo evoluciona la bolsa de tu cartera?**")
                explica("Banda: 8 de cada 10 trayectorias. Línea: la mediana. Sube cuando el mercado sube y se recorta "
                        "cuando se pasa de riesgo.")
                anios_x = np.arange(1, H_sim + 1)
                pw = np.percentile(sim["pesos"], [10, 50, 90], axis=0) * 100
                fw = go.Figure()
                fw.add_scatter(x=anios_x, y=pw[2], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
                fw.add_scatter(x=anios_x, y=pw[0], mode="lines", fill="tonexty", fillcolor="rgba(76,154,255,.25)",
                               line=dict(width=0), name="8 de cada 10 casos")
                fw.add_scatter(x=anios_x, y=pw[1], mode="lines", line=dict(color=C_INT, width=3), name="Mediana")
                fw.add_scatter(x=anios_x, y=np.array(pesos_plan) * 100, mode="lines", line=dict(color="#8B93A7", dash="dash"),
                               name="Plan fijo")
                fw.update_layout(xaxis_title="Año del plan", yaxis_title="% en bolsa", yaxis_range=[0, 100])
                st.plotly_chart(estilo(fw, 380), width="stretch")
            with e2:
                st.markdown("**¿Qué resultados finales son más probables?**")
                explica("Distribución del dinero final de cada estrategia (en múltiplos de lo invertido).")
                fh = go.Figure()
                cols_h = [C_CAP, C_INT, "#8B93A7"]
                for (nombre, x), colr in zip(variantes.items(), cols_h):
                    fh.add_histogram(x=x, nbinsx=40, name=nombre, opacity=0.55, marker_color=colr)
                fh.add_vline(x=1, line_dash="dash", line_color="#D55E00", annotation_text="Lo invertido")
                fh.update_layout(barmode="overlay", xaxis_title="Veces el dinero invertido", yaxis_title="Nº de casos")
                st.plotly_chart(estilo(fh, 380), width="stretch")
            st.caption("Cada trayectoria es una ventana histórica (solapadas) o un futuro sorteado. La renta fija rinde "
                       "un tipo constante. Sin impuestos ni costes de rebalanceo.")

    # ================================================================ perfiles y plazos
    with t_mat:
        st.markdown("**Bolsa recomendada según tu nota y los años que quedan**")
        explica("Cada fila es una nota del test; cada columna, los años que faltan. Así ves de un vistazo cómo "
                "cambian el ideal y el recorte por plazo.")
        notas = [15, 19, 23, 26, 29, 33, 38, 43]
        horizs = [1, 2, 3, 5, 7, 10, 15, 20, 25, 30]
        ideales = {n_: round(fin.rv_ideal_desde_puntos(n_, media, sd)[0], 4) for n_ in notas}
        pesos_m = tuple(sorted(set([i / 50 for i in range(51)] + list(ideales.values()) + [w_ideal])))
        tab_m = tabla_mal_escenario(indice, round(r_rf, 6), pesos_m, q_pct)
        if tab_m is not None and not tab_m.empty:
            z, txt = [], []
            for n_ in notas:
                sd_m = fin.senda_mal_escenario(tab_m, ideales[n_], suelo, suavizado=int(suav_a) * 2)
                fila_m = [min(fin.rv_en(sd_m, h_), ideales[n_]) * 100 for h_ in horizs]
                z.append(fila_m)
                txt.append([f"{v_:.0f}" for v_ in fila_m])
            hm = go.Figure(go.Heatmap(z=z, x=[f"{h_} a." for h_ in horizs], y=[f"Nota {n_} (ideal {ideales[n_] * 100:.0f} %)" for n_ in notas],
                                      text=txt, texttemplate="%{text}", colorscale=[[0, "#14532D"], [1, "#F5A524"]],
                                      zmin=0, zmax=100, colorbar=dict(title="% bolsa"),
                                      hovertemplate="%{y} · %{x}: %{z:.0f} % en bolsa<extra></extra>"))
            hm.update_layout(xaxis_title="Años que quedan", yaxis_autorange="reversed")
            st.plotly_chart(estilo(hm, 420, "no"), width="stretch")
        if usuarios:
            st.markdown("**Perfiles guardados, con tu plazo actual**")
            filas_u = []
            for u in usuarios:
                pu = int(perfiles["usuarios"][u]["puntuacion"])
                wi = round(fin.rv_ideal_desde_puntos(pu, media, sd)[0], 4)
                pw_u = tuple(sorted(set(pesos + (wi,))))
                tab_u = tabla_mal_escenario(indice, round(r_rf, 6), pw_u, q_pct)
                sd_u = fin.senda_mal_escenario(tab_u, wi, suelo, suavizado=int(suav_a) * 2)
                filas_u.append({"Perfil": u, "Nota": pu, "Nivel": perfiles["usuarios"][u]["nivel"],
                                "Bolsa ideal": wi, f"Recomendada a {horiz} años": min(fin.rv_en(sd_u, horiz), wi)})
            st.dataframe(pd.DataFrame(filas_u), hide_index=True, width="stretch", column_config={
                "Bolsa ideal": st.column_config.NumberColumn(format="percent"),
                f"Recomendada a {horiz} años": st.column_config.NumberColumn(format="percent")})
        else:
            st.info("Cuando guardes perfiles en el test de riesgo, aquí podrás compararlos.")

    st.caption("Orientativo: usa probabilidades históricas de perder dinero (ventanas semanales solapadas, suavizadas "
               "con media móvil de 52 semanas), sin impuestos ni comisiones. No es asesoramiento financiero.")
