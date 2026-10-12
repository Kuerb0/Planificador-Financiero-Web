"""Página Hipoteca."""
from ui import *  # noqa: F401,F403  (st, np, pd, go, fin y utilidades comunes)


def formula_neon(cap, tin, n_meses, c, tipo, df, tin2=None, c2=None, anios_fijos=5, tae_v=None, extra=False):
    i = tin / 12
    span = lambda cls, t: f'<span class="{cls}">{t}</span>'
    P, I, N, C = (span("nc", num(cap, 0)), span("nt", f"{i:.6f}".replace(".", ",")),
                  span("nn", str(n_meses)), span("nq", num(c, 2)))
    bruta = (f'{span("nq", "C")} = {span("nc", "P")} · {span("nt", "i")} / '
             f'(1 − (1 + {span("nt", "i")})<sup>−{span("nn", "n")}</sup>)')
    bloques = [
        ('Cuota mensual · sistema francés',
         f'<div class="f">{bruta}</div>'
         f'<div class="f s">{span("nq", "C")} = {P} · {I} / (1 − (1 + {I})<sup>−{N}</sup>) = <b>{C} €</b></div>'
         f'<span class="tag nc">P capital {num(cap, 0)} €</span>'
         f'<span class="tag nt">i = TIN/12 = {pct(tin)} / 12</span>'
         f'<span class="tag nn">n = {n_meses} meses</span>')]
    if len(df):
        r0 = df.iloc[0]
        bloques.append((
            'Primer recibo',
            f'<div class="f s">Interés = {span("nc", "P")} · {span("nt", "i")} = {P} · {I} = '
            f'<b>{span("nq", num(r0.intereses, 2))} €</b></div>'
            f'<div class="f s">Amortización = {span("nq", "C")} − Interés = {C} − {num(r0.intereses, 2)} = '
            f'<b>{span("nq", num(r0.amortizacion, 2))} €</b></div>'))
    if tipo == "Variable":
        bloques.append((
            'Revisión anual',
            f'<div class="f s">Nuevo {span("nt", "TIN")} = Euribor + diferencial'
            + (f' = <b>{span("nt", pct(tin2))}</b>' if tin2 is not None else '')
            + f'. Se recalcula {span("nq", "C")} con el saldo vivo y los meses que quedan'
            + (f' → <b>{span("nq", num(c2, 2))} €</b>' if c2 is not None else '') + '.</div>'))
    if tipo == "Mixto" and c2 is not None:
        bloques.append((
            'Tras el tramo fijo',
            f'<div class="f s">Desde el mes {anios_fijos * 12 + 1}: {span("nt", "TIN")} = Euribor + diferencial = '
            f'{span("nt", pct(tin2))} → nueva cuota <b>{span("nq", num(c2, 2))} €</b></div>'))
    if tae_v is not None:
        bloques.append((
            'TAE',
            f'<div class="f s">Capital neto = Σ (cuota + seguros)<sub>t</sub> / (1 + TIR<sub>mes</sub>)<sup>t</sup><br>'
            f'{span("na", "TAE")} = (1 + TIR<sub>mes</sub>)<sup>12</sup> − 1 = <b>{span("na", pct(tae_v))}</b></div>'))
    html = ['<div class="neon"><div class="grid">']
    for titulo, cuerpo in bloques:
        html.append(f'<div><h4>{titulo}</h4>{cuerpo}</div>')
    html.append('</div>')
    if extra:
        html.append('<div class="sep"></div><div class="nota">Con amortizaciones anticipadas la cuota se '
                    'recalcula sobre el saldo restante; la TAE se calcula siempre sin ellas, como exige la '
                    'normativa.</div>')
    html.append('</div>')
    st.markdown("".join(html), unsafe_allow_html=True)


def pag_hipoteca():
    titulo_pagina("home", "Hipoteca", "Calcula cuánto pagarás al mes y cuánto te costará el préstamo")
    with st.expander(":material/info: Cómo usar esta página"):
        st.markdown("1. Rellena arriba el precio, lo que aportas de entrada, los años y el tipo de interés.\n"
                    "2. Elige **fija, variable o mixta**: en la variable el tipo es Euribor + diferencial y se revisa cada año.\n"
                    "3. En «Opciones avanzadas» añades gastos de compra, seguros y **amortizaciones anticipadas**.\n"
                    "4. Mira la **TAE**: es el coste real anual, porque incluye comisiones y gastos del préstamo.")
    tipos, err = tipos_actuales()
    eur_def = tipos["euribor12m"] if tipos.get("euribor12m") is not None else 0.025

    with st.container(border=True):
        bloque("Datos de la hipoteca")
        c1, c2, c3, c4 = st.columns(4)
        precio = c1.number_input("Precio de la vivienda (€)", 20_000, 5_000_000, 250_000, 5_000, key="h_precio")
        entrada_pct = c2.number_input("Entrada (%)", 0.0, 100.0, 20.0, 1.0, key="h_entrada",
                                      help="Lo que pagas tú de tu bolsillo. Lo habitual es el 20 %.")
        anios = c3.number_input("Plazo (años)", 1, 40, 30, 1, key="h_anios")
        tipo = c4.selectbox("Tipo de hipoteca", ["Fijo", "Variable", "Mixto"], key="h_tipo",
                            help="Fijo: el interés no cambia. Variable: sube o baja con el Euribor. "
                                 "Mixto: fijo unos años y luego variable.")

        d1, d2, d3, d4 = st.columns(4)
        tin_fijo = diferencial = euribor = paso = 0.0
        anios_fijos = 5
        if tipo in ("Fijo", "Mixto"):
            tin_fijo = d1.number_input("TIN fijo (%)", 0.0, 15.0, 2.60, 0.05, key="h_tin",
                                       help="Tipo de interés nominal anual que te ofrece el banco.") / 100
        if tipo == "Mixto":
            anios_fijos = d2.number_input("Años a tipo fijo", 1, 39, 5, 1, key="h_afijos")
        if tipo in ("Variable", "Mixto"):
            diferencial = d3.number_input("Diferencial (%)", -1.0, 5.0, 0.80, 0.05, key="h_dif") / 100
            euribor = d4.number_input("Euribor 12m supuesto (%)", -1.0, 10.0, round(eur_def * 100, 2), 0.05,
                                      key="h_eur", help="Por defecto, el último dato del BCE") / 100
            paso = d1.number_input("Variación anual del Euribor (pp)", -2.0, 2.0, 0.0, 0.1, key="h_paso") / 100

        with st.expander("Opciones avanzadas: gastos de compra, seguros y amortizaciones anticipadas"):
            e1, e2, e3, e4 = st.columns(4)
            vivienda = e1.selectbox("Vivienda", ["Usada", "Nueva"], key="h_viv",
                                    help="Usada: paga ITP. Nueva: paga IVA + AJD.")
            if vivienda == "Usada":
                itp = e2.number_input("ITP (%)", 0.0, 12.0, 6.0, 0.5, key="h_itp",
                                      help="Madrid: 6 %. Cambia según comunidad.") / 100
                iva = ajd = 0.0
            else:
                iva = e2.number_input("IVA (%)", 0.0, 21.0, 10.0, 0.5, key="h_iva") / 100
                ajd = e3.number_input("AJD (%)", 0.0, 3.0, 0.75, 0.05, key="h_ajd") / 100
                itp = 0.0
            notaria = e4.number_input("Notaría + registro + gestoría (€)", 0, 20_000, 2_500, 100, key="h_not")
            f1, f2, f3, f4 = st.columns(4)
            tasacion = f1.number_input("Tasación (€)", 0, 3_000, 400, 50, key="h_tas")
            comision = f2.number_input("Comisión de apertura (%)", 0.0, 3.0, 0.0, 0.1, key="h_com") / 100
            seguros = f3.number_input("Seguros vinculados (€/mes)", 0, 500, 0, 5, key="h_seg",
                                      help="Entran en la TAE")
            f4.write("")
            g1, g2, g3 = st.columns(3)
            extra_m = g1.number_input("Amortización extra mensual (€)", 0, 20_000, 0, 50, key="h_exm")
            extra_a = g2.number_input("Amortización extra anual (€, cada diciembre)", 0, 500_000, 0, 500,
                                      key="h_exa")
            modo_extra = g3.radio("Con las amortizaciones…", ["Reducir plazo", "Reducir cuota"],
                                  horizontal=True, key="h_modo")

    entrada = precio * entrada_pct / 100
    capital = precio - entrada
    if capital <= 0:
        st.warning("La entrada cubre todo el precio: no hay hipoteca que calcular.")
        return
    gastos = fin.gastos_compra(precio, vivienda, itp, iva, ajd, notaria, tasacion, comision, capital)
    gastos_total = sum(gastos.values())
    modo = "plazo" if modo_extra == "Reducir plazo" else "cuota"
    args = dict(tipo=tipo, tin_fijo=tin_fijo, diferencial=diferencial, euribor=euribor, paso_euribor=paso,
                anios_fijos=anios_fijos)
    base = fin.cuadro(capital, anios, **args)
    con_extra = (fin.cuadro(capital, anios, extra_mensual=extra_m, extra_anual=extra_a, modo_extra=modo, **args)
                 if (extra_m or extra_a) else base)
    hay_extra = bool(extra_m or extra_a)
    ligados = gastos["Comisión de apertura"] + tasacion          # gastos ligados al préstamo para la TAE
    tae_v = fin.tae(capital, base, ligados, seguros)
    n = anios * 12
    tin0 = fin.tin_del_mes(0, tipo, tin_fijo, diferencial, euribor, paso, anios_fijos)
    c0 = float(base.cuota.iloc[0])

    total_int = con_extra.intereses.sum()
    total_pagado = con_extra.cuota.sum() + con_extra.extra.sum()
    meses_reales = len(con_extra)

    tin2 = c2 = None
    if tipo in ("Variable", "Mixto"):
        mes_cambio = anios_fijos * 12 if tipo == "Mixto" else 12
        if len(base) > mes_cambio:
            tin2 = float(base.tin.iloc[mes_cambio])
            c2 = float(base.cuota.iloc[mes_cambio])
    with st.expander("Cómo se calcula la cuota (fórmula)", expanded=True):
        formula_neon(capital, tin0, n, c0, tipo, base, tin2=tin2, c2=c2, anios_fijos=anios_fijos,
                     tae_v=tae_v, extra=hay_extra)

    desde = "al mes" if tipo == "Fijo" else "al mes al principio (puede cambiar al revisarse el tipo)"
    st.markdown(
        f'<div class="resumen">Pagarás <b>{eur(c0, 2)} {desde}</b> durante <b>{meses_reales // 12} años'
        + (f' y {meses_reales % 12} meses' if meses_reales % 12 else '') + f'</b>. En total devolverás '
        f'<b>{eur(total_pagado)}</b>, de los que <b>{eur(total_int)}</b> son intereses (lo que te cuesta el '
        f'préstamo). Para comprar necesitas tener ahorrados <b>{eur(entrada + gastos_total)}</b> '
        f'(entrada + impuestos y gastos).</div>', unsafe_allow_html=True)

    m = st.columns(4)
    m[0].metric("Cuota mensual" if tipo == "Fijo" else "Cuota inicial", eur(c0, 2))
    m[1].metric("Intereses totales", eur(total_int), help="Lo que pagas de más sobre el dinero prestado")
    m[2].metric("TAE", pct(tae_v), help="Coste anual real del préstamo, incluyendo comisiones y seguros")
    m[3].metric("Ahorro necesario", eur(entrada + gastos_total),
                help="Entrada + gastos de compra (impuestos, notaría, tasación, comisión)")
    if hay_extra:
        a = st.columns(3)
        a[0].metric("Intereses que te ahorras", eur(base.intereses.sum() - total_int))
        a[1].metric("Duración real", f"{meses_reales // 12} a {meses_reales % 12} m",
                    delta=f"{meses_reales - len(base)} meses" if meses_reales != len(base) else None,
                    delta_color="off")
        a[2].metric("Cuota final", eur(float(con_extra.cuota.iloc[-1]), 2))

    t_graf, t_compra, t_mas, t_cuadro = st.tabs([":material/bar_chart: Gráficos", ":material/receipt_long: Compra y gastos", ":material/search: Más análisis",
                                                 ":material/table_chart: Cuadro de amortización"])

    with t_graf:
        g1, g2 = st.columns(2, gap="large")
        with g1:
            st.markdown("**¿Cuánto debo en cada momento?**")
            explica("Es el dinero que todavía le debes al banco. Baja despacio al principio y más deprisa al final.")
            saldo = pd.concat([pd.DataFrame({"mes": [0], "saldo": [capital]}), con_extra[["mes", "saldo"]]])
            f1 = go.Figure(go.Scatter(x=saldo.mes / 12, y=saldo.saldo, mode="lines", fill="tozeroy",
                                      line=dict(color=C_SALDO, width=3), fillcolor="rgba(167,139,250,.18)",
                                      name="Deuda pendiente",
                                      hovertemplate="Año %{x:.1f}: debes %{y:,.0f} €<extra></extra>"))
            f1.update_layout(xaxis_title="Años desde la firma", yaxis_title="€ que debes")
            st.plotly_chart(estilo(f1, 340, "no"), width="stretch")
        with g2:
            st.markdown("**¿Qué parte del dinero es interés?**")
            explica("Del total que acabarás pagando al banco, cuánto es el préstamo y cuánto el coste.")
            f2 = go.Figure(go.Pie(labels=["Dinero prestado", "Intereses"], values=[capital, total_int], hole=.62,
                                  marker_colors=[C_CAP, C_INT], sort=False, textinfo="percent",
                                  textfont_size=15,
                                  hovertemplate="%{label}: %{value:,.0f} €<extra></extra>"))
            f2.add_annotation(text=f"<b>{eur(capital + total_int)}</b><br>en total", showarrow=False,
                              font_size=15)
            st.plotly_chart(estilo(f2, 340), width="stretch")

        st.markdown("**Cada año: ¿cuánto pago de capital y cuánto de intereses?**")
        explica("Cada barra es un año. La parte azul reduce tu deuda; la naranja es lo que cobra el banco. "
                "Con los años, el naranja se encoge.")
        anual = con_extra.groupby("anio").agg(intereses=("intereses", "sum"), capital=("amortizacion", "sum"),
                                              extra=("extra", "sum")).reset_index()
        f3 = go.Figure()
        f3.add_bar(x=anual.anio, y=anual.capital, name="Capital (reduce la deuda)", marker_color=C_CAP)
        if hay_extra:
            f3.add_bar(x=anual.anio, y=anual.extra, name="Amortización extra", marker_color=C_EXTRA)
        f3.add_bar(x=anual.anio, y=anual.intereses, name="Intereses (coste del banco)", marker_color=C_INT)
        f3.update_layout(barmode="stack", xaxis_title="Año", yaxis_title="€ pagados en el año")
        st.plotly_chart(estilo(f3, 380), width="stretch")

        if tipo != "Fijo" or (hay_extra and modo == "cuota"):
            st.markdown("**¿Cómo cambia la cuota mensual?**")
            explica("La cuota se recalcula cuando se revisa el tipo de interés o cuando amortizas para reducir cuota.")
            f4 = go.Figure(go.Scatter(x=con_extra.mes / 12, y=con_extra.cuota, mode="lines", line_shape="hv",
                                      line=dict(color=C_INT, width=3), name="Cuota",
                                      hovertemplate="Año %{x:.1f}: %{y:,.2f} €/mes<extra></extra>"))
            f4.update_layout(xaxis_title="Años desde la firma", yaxis_title="€ por mes")
            st.plotly_chart(estilo(f4, 300, "no"), width="stretch")

    with t_compra:
        st.markdown("**Cuánto dinero necesitas el día de la compra**")
        des = pd.DataFrame({"Concepto": ["Entrada"] + list(gastos) + ["Total a aportar"],
                            "Importe": [entrada] + list(gastos.values()) + [entrada + gastos_total]})
        st.dataframe(des, hide_index=True, width="stretch",
                     column_config={"Importe": st.column_config.NumberColumn("Importe", format="%.0f €")})
        st.caption(f"Total que pagarás al banco: {eur(total_pagado)} · coste total de la vivienda "
                   f"(entrada + gastos + banco): {eur(entrada + gastos_total + total_pagado)}")

    with t_mas:
        # ---------------------------------------------------------- asequibilidad
        st.markdown("**¿Puedo permitírmela?**")
        explica("Regla habitual: la cuota no debería pasar del 30-35 % de tus ingresos netos mensuales del hogar.")
        q1, q2 = st.columns([1, 2])
        ingresos = q1.number_input("Ingresos netos al mes (€)", 500, 50_000, 3_000, 100, key="h_ingr",
                                   help="Suma de lo que cobráis al mes después de impuestos.")
        ratio = c0 / ingresos
        estado, color = (("Cómoda", "normal") if ratio <= 0.30 else (("Ajustada", "off") if ratio <= 0.35 else ("Demasiado alta", "inverse")))
        with q2:
            mm = st.columns(3)
            mm[0].metric("Cuota / ingresos", pct(ratio, 0), delta=estado, delta_color=color, delta_arrow="off")
            cuota_max = ingresos * 0.35
            cap_max = cuota_max / fin.cuota(1.0, tin0, n)
            mm[1].metric("Cuota máxima (35 %)", eur(cuota_max, 0))
            mm[2].metric("Precio máximo aprox.", eur(cap_max / (1 - entrada_pct / 100), 0),
                         help="Precio de vivienda con el que la cuota inicial llegaría al 35 % de tus ingresos, con "
                              "esta entrada, plazo y tipo (sin contar gastos de compra).")

        # ---------------------------------------------------------- estrés del Euribor
        st.markdown("**¿Y si suben los tipos?**")
        if tipo == "Fijo":
            st.info("Con una hipoteca fija el tipo no cambia, así que esta prueba solo tiene sentido en variable o "
                    "mixta. Cambia el tipo arriba para verla.")
        else:
            explica("Cuota y coste total si el Euribor fuese distinto desde el principio (el resto de datos iguales).")
            filas_e = []
            for d_pp in (-1.0, 0.0, 1.0, 2.0, 3.0):
                a_e = dict(args, euribor=euribor + d_pp / 100)
                cu = fin.cuadro(capital, anios, **a_e)
                mes_c = anios_fijos * 12 if tipo == "Mixto" else 12
                filas_e.append({"Euribor": euribor + d_pp / 100, "Cambio": f"{d_pp:+.0f} pp" if d_pp else "Actual",
                                "Cuota inicial": float(cu.cuota.iloc[0]),
                                "Cuota tras la primera revisión": float(cu.cuota.iloc[min(mes_c, len(cu) - 1)]),
                                "Intereses totales": float(cu.intereses.sum())})
            st.dataframe(pd.DataFrame(filas_e), hide_index=True, width="stretch", column_config={
                "Euribor": st.column_config.NumberColumn(format="percent"),
                **{c: st.column_config.NumberColumn(format="%.0f €") for c in
                   ["Cuota inicial", "Cuota tras la primera revisión", "Intereses totales"]}})

        # ---------------------------------------------------------- comparar plazos
        st.markdown("**¿Y si cambio el plazo?**")
        explica("Más años = cuota más baja pero muchos más intereses. Con la misma entrada y tipo.")
        plazos_c = sorted(set([15, 20, 25, 30, 35, int(anios)]))
        filas_p = []
        for a_ in plazos_c:
            cu = fin.cuadro(capital, a_, **args)
            filas_p.append({"Plazo": f"{a_} años", "Cuota inicial": float(cu.cuota.iloc[0]),
                            "Intereses totales": float(cu.intereses.sum()),
                            "Total a devolver": float(cu.cuota.sum())})
        dfp = pd.DataFrame(filas_p)
        fpz = go.Figure()
        fpz.add_bar(x=dfp["Plazo"], y=dfp["Intereses totales"], name="Intereses totales", marker_color=C_INT)
        fpz.add_scatter(x=dfp["Plazo"], y=dfp["Cuota inicial"], name="Cuota mensual", mode="lines+markers",
                        yaxis="y2", line=dict(color=C_CAP, width=3))
        fpz.update_layout(yaxis=dict(title="Intereses totales (€)"),
                          yaxis2=dict(title="Cuota (€/mes)", overlaying="y", side="right"))
        z1, z2 = st.columns([3, 2], gap="large")
        z1.plotly_chart(estilo(fpz, 340), width="stretch")
        z2.dataframe(dfp, hide_index=True, width="stretch", column_config={
            c: st.column_config.NumberColumn(format="%.0f €") for c in
            ["Cuota inicial", "Intereses totales", "Total a devolver"]})

    with t_cuadro:
        explica("Mes a mes: cuánto pagas, cuánto son intereses, cuánto reduce la deuda y cuánto te queda por pagar.")
        t = con_extra.rename(columns={"mes": "Mes", "tin": "TIN", "cuota": "Cuota", "intereses": "Intereses",
                                      "amortizacion": "Amortización", "extra": "Extra", "saldo": "Saldo",
                                      "anio": "Año"})
        st.dataframe(t, hide_index=True, width="stretch", column_config={
            "TIN": st.column_config.NumberColumn(format="%.3f"),
            **{k: st.column_config.NumberColumn(format="%.2f €") for k in
               ["Cuota", "Intereses", "Amortización", "Extra", "Saldo"]}})
        st.download_button("Descargar CSV", t.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           "cuadro_amortizacion.csv", "text/csv")
