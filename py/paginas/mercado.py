"""Página Mercado."""
from ui import *  # noqa: F401,F403  (st, np, pd, go, fin y utilidades comunes)


def pag_mercado():
    titulo_pagina("public", "Mercado", "Cómo se ha comportado la bolsa en el pasado: la base de todas las simulaciones")
    st.info("Aquí ves los datos reales que usan Cartera, Comparador y Plazos y riesgo. El pasado no garantiza el "
            "futuro, pero sirve para saber cuánto puede subir y bajar la bolsa.", icon=":material/info:")
    with st.container(border=True):
        bloque("Datos de partida")
        indice = st.selectbox("Índice de bolsa", list(fin.INDICES), key="mk_idx",
                              help="En dólares y con dividendos, sin convertir a euros. El «Mundo largo» empalma "
                                   "MSCI World (1973-2008) con el ETF Vanguard Total World (desde 2009).")
    ret, nivel, err = datos_indice(indice)
    if err or ret is None:
        st.error(f"No se han podido descargar los datos del índice: {err}")
        return
    st.caption(f"Datos {ret.index.min()}–{ret.index.max()} (índice en dólares, con dividendos, {etiqueta_modo()}).")
    t_hist, t_caida, t_dec, t_cmp, t_tipos = st.tabs([":material/show_chart: Histórico", ":material/trending_down: Caídas", ":material/calendar_month: Décadas y plazos",
                                                      ":material/compare_arrows: Comparar índices", ":material/account_balance: Tipos de interés"])
    with t_hist:
        cagr = (nivel.iloc[-1] / nivel.iloc[0]) ** (1 / ((nivel.index[-1] - nivel.index[0]).days / 365.25)) - 1
        caida = (nivel / nivel.cummax() - 1)
        k = st.columns(4)
        k[0].metric("Rentabilidad media anual", pct(cagr, 1), help="Rentabilidad anual compuesta de todo el histórico")
        k[1].metric("Variación típica de un año", pct(float(ret.std(ddof=1)), 1),
                    help="Volatilidad: cuánto se aleja un año de la media. Cuanto más alta, más sube y baja.")
        k[2].metric("Peor año", pct(float(ret.min()), 1), delta=f"en {int(ret.idxmin())}", delta_color="off")
        k[3].metric("Mayor caída desde máximos", pct(float(caida.min()), 1),
                    delta=f"en {caida.idxmin():%m/%Y}", delta_color="off")
        h1, h2 = st.columns([3, 2], gap="large")
        with h1:
            st.markdown("**¿Cómo ha evolucionado el índice?**")
            explica("Lo que valdrían 100 € invertidos al principio. Escala logarítmica: una misma subida en "
                    "porcentaje se ve igual de alta al principio que al final.")
            g = go.Figure(go.Scatter(x=nivel.index, y=nivel.values, mode="lines", line=dict(color=C_CAP, width=2.5),
                                     fill="tozeroy", fillcolor="rgba(76,154,255,.12)", name="Valor de 100 €",
                                     hovertemplate="%{x|%m/%Y}: %{y:,.0f} €<extra></extra>"))
            g.update_layout(yaxis_type="log", yaxis_title="Valor de 100 € invertidos", xaxis_title="")
            st.plotly_chart(estilo(g, 360, "no"), width="stretch")
        with h2:
            st.markdown("**¿Cuánto subió o bajó cada año?**")
            explica("Azul: año de subida. Naranja: año de bajada.")
            b = go.Figure(go.Bar(x=ret.index, y=ret.values * 100,
                                 marker_color=np.where(ret.values >= 0, C_CAP, C_INT)))
            b.update_layout(xaxis_title="", yaxis_title="Rentabilidad del año (%)")
            st.plotly_chart(estilo(b, 360, "no"), width="stretch")

    # ------------------------------------------------------------ caídas
    with t_caida:
        explica("Cuánto ha estado el índice por debajo de su máximo anterior. Cada hueco es una crisis; lo que importa "
                "es cuánto cayó y cuánto tardó en recuperarse.")
        dd = (nivel / nivel.cummax() - 1) * 100
        fd = go.Figure(go.Scatter(x=dd.index, y=dd.values, mode="lines", fill="tozeroy", line=dict(color=C_INT, width=2),
                                  fillcolor="rgba(245,165,36,.25)",
                                  hovertemplate="%{x|%m/%Y}: %{y:.1f} % desde máximos<extra></extra>"))
        fd.update_layout(yaxis_title="Caída desde el máximo (%)", xaxis_title="")
        st.plotly_chart(estilo(fd, 360, "no"), width="stretch")
        # episodios: tramos consecutivos por debajo del máximo
        en_caida = dd < -0.0001
        grupo = (en_caida != en_caida.shift()).cumsum()
        filas_d = []
        for _, tr in dd[en_caida].groupby(grupo[en_caida]):
            ini = tr.index[0]
            fondo_f = tr.idxmin()
            fin_f = nivel.index[nivel.index.get_loc(tr.index[-1]) + 1] if tr.index[-1] != nivel.index[-1] else None
            filas_d.append({"Empieza": ini.strftime("%m/%Y"), "Mínimo": fondo_f.strftime("%m/%Y"),
                            "Caída máxima": float(tr.min()) / 100,
                            "Meses hasta el mínimo": int(round((fondo_f - ini).days / 30.4)),
                            "Recuperado": fin_f.strftime("%m/%Y") if fin_f is not None else "Aún no",
                            "Meses en total": int(round(((fin_f or nivel.index[-1]) - ini).days / 30.4))})
        if filas_d:
            st.markdown("**Las peores caídas**")
            peores = pd.DataFrame(filas_d).sort_values("Caída máxima").head(8)
            st.dataframe(peores, hide_index=True, width="stretch", column_config={
                "Caída máxima": st.column_config.NumberColumn(format="percent")})

    # ------------------------------------------------------------ décadas y ventanas de 10 años
    with t_dec:
        st.markdown("**Rentabilidad media anual por década**")
        explica("Rentabilidad anual compuesta de cada década. Verás que hay décadas «perdidas» y otras muy buenas.")
        dfy = pd.DataFrame({"r": ret.values}, index=ret.index.astype(int))
        dfy["dec"] = (dfy.index // 10) * 10
        dec = dfy.groupby("dec")["r"].agg(lambda x: (1 + x).prod() ** (1 / len(x)) - 1)
        dec_n = dfy.groupby("dec")["r"].size()
        fdc = go.Figure(go.Bar(x=[f"{d}s" + ("*" if dec_n[d] < 10 else "") for d in dec.index], y=dec.values * 100,
                               marker_color=np.where(dec.values >= 0, C_CAP, C_INT),
                               hovertemplate="%{x}: %{y:.1f} % anual<extra></extra>"))
        fdc.update_layout(yaxis_title="Rentabilidad anual (%)", xaxis_title="")
        st.plotly_chart(estilo(fdc, 320, "no"), width="stretch")
        st.caption("* Década incompleta.")
        st.markdown("**Rentabilidad anualizada según el plazo en que mantienes**")
        explica("Cada línea es una ventana móvil de N años: su rentabilidad anualizada según cuándo empiezas. Con más "
                "años la línea se aplana y se vuelve más estable.")
        ventanas_a = st.multiselect("Plazos (años)", [3, 5, 10, 15, 20, 30], default=[5, 10, 20], key="mk_vent")
        fv = go.Figure()
        for h_ in ventanas_a:
            m_ = h_ * 12
            if len(nivel) <= m_:
                continue
            tir_v = (nivel.shift(-m_) / nivel) ** (1 / h_) - 1
            tir_v = tir_v.dropna()
            fv.add_scatter(x=tir_v.index, y=tir_v.values * 100, mode="lines", name=f"{h_} años")
        fv.add_hline(y=0, line_dash="dash", line_color="#8B93A7")
        fv.update_layout(yaxis_title="Rentabilidad anualizada (%)", xaxis_title="Fecha de inicio de la ventana")
        st.plotly_chart(estilo(fv, 380), width="stretch")

    # ------------------------------------------------------------ comparar índices
    with t_cmp:
        explica("Valor de 100 € invertidos a la vez en varios índices (en dólares, con dividendos) desde el primer mes "
                "en que todos tienen datos. Escala logarítmica.")
        elegidos = st.multiselect("Índices", list(fin.INDICES), default=[indice, list(fin.INDICES)[1]]
                                  if len(fin.INDICES) > 1 else [indice], key="mk_cmp")
        series = {}
        for nm in elegidos:
            try:
                series[nm.split(":")[0]] = fin.indice_mensual(nm)
            except Exception as e:
                st.warning(f"{nm}: {str(e)[:120]}")
        if series:
            comun = pd.concat(series, axis=1).dropna()
            if comun.empty:
                st.info("Los índices elegidos no comparten fechas.")
            else:
                comun = comun / comun.iloc[0] * 100
                fc2 = go.Figure()
                for c_ in comun.columns:
                    fc2.add_scatter(x=comun.index, y=comun[c_], mode="lines", name=c_)
                fc2.update_layout(yaxis_type="log", yaxis_title="Valor de 100 €", xaxis_title="")
                st.plotly_chart(estilo(fc2, 400), width="stretch")
                anos_c = (comun.index[-1] - comun.index[0]).days / 365.25
                resumen_c = pd.DataFrame({
                    "Índice": comun.columns,
                    "Rentab. anual": [(comun[c_].iloc[-1] / 100) ** (1 / anos_c) - 1 for c_ in comun.columns],
                    "Mayor caída": [float((comun[c_] / comun[c_].cummax() - 1).min()) for c_ in comun.columns],
                    "Desde": comun.index[0].strftime("%m/%Y")})
                st.dataframe(resumen_c, hide_index=True, width="stretch", column_config={
                    "Rentab. anual": st.column_config.NumberColumn(format="percent"),
                    "Mayor caída": st.column_config.NumberColumn(format="percent")})

    # ------------------------------------------------------------ tipos de interés
    with t_tipos:
        explica("La parte de renta fija de las simulaciones usa estos tipos del BCE. Aquí ves cuánto rinden hoy y cómo "
                "han cambiado.")
        tp, e_tp = tipos_actuales()
        kt = st.columns(2)
        kt[0].metric("Euribor 12 meses", pct(tp["euribor12m"], 2) if tp.get("euribor12m") is not None else "—")
        kt[1].metric("Bono euro a 10 años", pct(tp["bono10"], 2) if tp.get("bono10") is not None else "—")
        cv, e_cv = datos_curva()
        if cv is None:
            st.info(f"No se ha podido descargar la curva histórica del BCE: {e_cv}")
        else:
            fy = go.Figure()
            for venc in (1, 5, 10, 20):
                if venc in cv.columns:
                    fy.add_scatter(x=cv.index, y=cv[venc] * 100, mode="lines", name=f"{venc} año{'s' if venc > 1 else ''}")
            fy.update_layout(yaxis_title="Rendimiento (%)", xaxis_title="")
            st.markdown("**Rendimiento de la deuda por vencimiento**")
            st.plotly_chart(estilo(fy, 340), width="stretch")
            ult = cv.dropna(how="all").iloc[-1]
            hace1 = cv.dropna(how="all").iloc[max(len(cv) - 13, 0)]
            fcv = go.Figure()
            fcv.add_scatter(x=ult.index, y=ult.values * 100, mode="lines+markers", name=f"{cv.index[-1]:%m/%Y}",
                            line=dict(color=C_INT, width=3))
            fcv.add_scatter(x=hace1.index, y=hace1.values * 100, mode="lines", name="Hace un año",
                            line=dict(color="#8B93A7", dash="dash"))
            fcv.update_layout(xaxis_title="Vencimiento (años)", yaxis_title="Rendimiento (%)")
            st.markdown("**Curva de tipos: hoy frente a hace un año**")
            st.plotly_chart(estilo(fcv, 340), width="stretch")
