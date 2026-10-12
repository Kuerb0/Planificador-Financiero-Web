"""Página Test de riesgo."""
from ui import *  # noqa: F401,F403  (st, np, pd, go, fin y utilidades comunes)


def pag_test():
    titulo_pagina("🧭", "Test de riesgo", "Tolerancia al riesgo financiero (cuestionario de Grable y Lytton, 13 preguntas)")
    perfiles = fin.leer_perfiles()
    usuarios = list(perfiles["usuarios"])
    mn, mx = fin.puntuacion_min_max()
    st.markdown('<div class="resumen">Son <b>13 preguntas</b> y tardas unos 3 minutos. No hay respuestas buenas ni '
                'malas: sirve para saber cuánto riesgo aceptas con tu dinero. Al final se guarda tu perfil y la '
                'pestaña Cartera te sugiere un reparto.</div>', unsafe_allow_html=True)

    with st.form("form_test"):
        nombre = st.text_input("Usuario", value=perfiles.get("activo") or "", key="t_nombre",
                               help="Si ya existe, se actualiza su perfil. Si es nuevo, se crea.")
        resp = []
        for i, (preg, opts) in enumerate(fin.TEST, 1):
            sel = st.radio(f"{i}. {preg}", [t for t, _ in opts], index=None, key=f"t_{i}")
            resp.append(dict(opts).get(sel) if sel else None)
        enviado = st.form_submit_button("Calcular y guardar perfil", type="primary")

    if enviado:
        if not nombre.strip():
            st.error("Escribe un nombre de usuario.")
        elif any(r is None for r in resp):
            faltan = [str(i + 1) for i, r in enumerate(resp) if r is None]
            st.error(f"Faltan por responder: {', '.join(faltan)}")
        else:
            res = fin.evaluar_test(resp)
            fin.guardar_perfil(nombre.strip(), res, resp)
            st.success(f"Perfil de {nombre.strip()} guardado: {res['nivel']} ({res['puntuacion']} puntos).")
            perfiles = fin.leer_perfiles()
            usuarios = list(perfiles["usuarios"])

    st.subheader("Perfiles guardados")
    if not usuarios:
        st.info("Aún no hay ningún perfil guardado.")
        return
    filas = []
    for u, p in perfiles["usuarios"].items():
        filas.append({"Usuario": u + (" ★" if u == perfiles.get("activo") else ""), "Fecha": p["fecha"],
                      "Puntos": p["puntuacion"], "Nivel": p["nivel"], "% renta variable sugerido": p["rv_sugerida"]})
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")

    sel = st.selectbox("Ver / usar usuario", usuarios, index=usuarios.index(perfiles.get("activo"))
                       if perfiles.get("activo") in usuarios else 0, key="t_ver")
    p = perfiles["usuarios"][sel]
    pos = (p["puntuacion"] - mn) / (mx - mn) * 100
    st.markdown(f'<div class="medidor"><i style="left:calc({pos:.1f}% - 2px)"></i></div>'
                '<div style="display:flex;justify-content:space-between;font-size:.85rem;opacity:.75;margin-top:-18px">'
                '<span>Prudente</span><span>Equilibrado</span><span>Arriesgado</span></div>', unsafe_allow_html=True)
    t_res, t_des, t_evo, t_vivir = st.tabs(["📊 Tu resultado", "🧠 Desglose por pregunta", "📈 Evolución",
                                            "🎢 Cómo lo habrías vivido"])
    with t_res:
        k = st.columns(3)
        k[0].metric("Puntuación", f"{p['puntuacion']} / {mx}")
        k[1].metric("Nivel", p["nivel"])
        k[2].metric("% renta variable sugerido", f"{p['rv_sugerida']} %")
        st.write(p["descripcion"])
        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button("Usar este perfil", key="t_usar"):
            fin.usuario_activo(sel)
            st.rerun()
        if b2.button("Borrar perfil", key="t_borrar"):
            fin.borrar_perfil(sel)
            st.rerun()
        st.markdown("**Todos los perfiles**")
        explica("Nota de cada usuario sobre la escala del test. Las franjas son los niveles oficiales de Grable y Lytton.")
        nombres_u = list(perfiles["usuarios"])
        fu = go.Figure()
        for lo, hi, col_n, nm_n in ((mn, 18.5, "rgba(76,154,255,.12)", "Bajo"), (18.5, 22.5, "rgba(46,196,166,.12)", "Medio-bajo"),
                                    (22.5, 28.5, "rgba(128,128,128,.12)", "Medio"), (28.5, 32.5, "rgba(245,165,36,.12)", "Medio-alto"),
                                    (32.5, mx, "rgba(213,94,0,.12)", "Alto")):
            fu.add_hrect(y0=lo, y1=hi, fillcolor=col_n, line_width=0, annotation_text=nm_n, annotation_position="top left")
        fu.add_bar(x=nombres_u, y=[perfiles["usuarios"][u]["puntuacion"] for u in nombres_u], marker_color=C_CAP,
                   hovertemplate="%{x}: %{y} puntos<extra></extra>")
        fu.update_layout(yaxis_range=[mn, mx], yaxis_title="Puntuación")
        st.plotly_chart(estilo(fu, 340, "no"), width="stretch")

    with t_des:
        explica("Cuántos puntos has puesto en cada pregunta (de 1 a 4 o de 1 a 5). Barras largas = respuestas más "
                "arriesgadas; cortas = más prudentes. Sirve para ver en qué situaciones eres más audaz.")
        resp_g = p.get("respuestas")
        if not resp_g or len(resp_g) != len(fin.TEST):
            st.info("Este perfil no guarda las respuestas por pregunta. Repite el test para verlas.")
        else:
            maxs = [max(pp for _, pp in o) for _, o in fin.TEST]
            etiquetas_q = [f"{i}. " + (q_[:48] + "…" if len(q_) > 48 else q_) for i, (q_, _) in enumerate(fin.TEST, 1)]
            fq = go.Figure()
            fq.add_bar(y=etiquetas_q, x=maxs, orientation="h", marker_color="rgba(128,128,128,.25)", name="Máximo posible")
            fq.add_bar(y=etiquetas_q, x=resp_g, orientation="h", marker_color=C_INT, name="Tu respuesta")
            fq.update_layout(barmode="overlay", yaxis_autorange="reversed", xaxis_title="Puntos")
            st.plotly_chart(estilo(fq, 520), width="stretch")
            rel = [(r_ / m_, i) for i, (r_, m_) in enumerate(zip(resp_g, maxs))]
            top = max(rel)[1]
            baj = min(rel)[1]
            st.markdown(f"- Donde más riesgo aceptas: **{fin.TEST[top][0]}**\n- Donde más prudente eres: **{fin.TEST[baj][0]}**")

    with t_evo:
        hist = p.get("historial") or []
        explica("Si repites el test con el tiempo, aquí ves cómo cambia tu tolerancia al riesgo. Suele moverse tras "
                "una crisis, un cambio de trabajo o de situación familiar.")
        if len(hist) < 2:
            st.info("Solo hay un resultado guardado. Cuando repitas el test (mismo usuario) aparecerá aquí la evolución.")
        else:
            hd = pd.DataFrame(hist)
            fe = go.Figure(go.Scatter(x=hd["fecha"], y=hd["puntuacion"], mode="lines+markers",
                                      line=dict(color=C_CAP, width=3), marker=dict(size=10)))
            fe.update_layout(yaxis_range=[mn, mx], yaxis_title="Puntuación", xaxis_title="")
            st.plotly_chart(estilo(fe, 320, "no"), width="stretch")
            st.dataframe(hd.rename(columns={"fecha": "Fecha", "puntuacion": "Puntuación"}), hide_index=True, width="stretch")

    with t_vivir:
        explica("Para ponerle cifras al reparto sugerido: qué le habría pasado en los peores años de la historia "
                "(índice mundial en dólares con la renta fija al Euribor actual, sin rebalanceos).")
        ret_t, _, err_t = datos_indice(fin.INDICE_DEFECTO)
        if ret_t is None:
            st.info(f"No se han podido cargar los datos del índice: {err_t}")
        else:
            tp_t, _ = tipos_actuales()
            rf_t = rf_efectivo(tp_t.get("euribor12m") if tp_t.get("euribor12m") is not None else 0.025)
            w_t = p["rv_sugerida"] / 100
            r_cart = w_t * ret_t + (1 - w_t) * rf_t
            q1_, q2_ = st.columns(2)
            q1_.metric("Peor año de tu cartera sugerida", pct(float(r_cart.min()), 1), delta=f"en {int(r_cart.idxmin())}",
                       delta_color="off")
            q2_.metric("Años con pérdidas", f"{int((r_cart < 0).sum())} de {len(r_cart)}")
            peor = r_cart.nsmallest(5).reset_index()
            peor.columns = ["Año", "Rentabilidad de tu cartera"]
            peor["Con 10.000 € quedarían"] = 10_000 * (1 + peor["Rentabilidad de tu cartera"])
            ft = go.Figure(go.Bar(x=r_cart.index, y=r_cart.values * 100,
                                  marker_color=np.where(r_cart.values >= 0, C_CAP, C_INT)))
            ft.update_layout(xaxis_title="", yaxis_title=f"Rentabilidad del año con {p['rv_sugerida']} % en bolsa (%)")
            st.plotly_chart(estilo(ft, 320, "no"), width="stretch")
            st.dataframe(peor, hide_index=True, width="stretch", column_config={
                "Rentabilidad de tu cartera": st.column_config.NumberColumn(format="percent"),
                "Con 10.000 € quedarían": st.column_config.NumberColumn(format="%.0f €")})
            st.caption("Si ver estos años te incomoda, probablemente te convenga menos bolsa de la sugerida.")
    st.caption("El cuestionario de Grable y Lytton (1999) mide cuánto riesgo aceptas, no cuánto te conviene. "
               "El reparto sugerido es una referencia orientativa; no sustituye a un asesor.")
