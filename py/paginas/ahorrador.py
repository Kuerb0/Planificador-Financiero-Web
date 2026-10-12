"""Página Ahorrador."""
from ui import *  # noqa: F401,F403  (st, np, pd, go, fin y utilidades comunes)


def _anios_meses(m):
    return f"{m // 12} años y {m % 12} meses" if m % 12 else f"{m // 12} años"


@st.cache_data(show_spinner="Cargando tablas de mortalidad del INE…", ttl=86400 * 30)
def datos_mortalidad():
    return fin.tabla_mortalidad()


def pag_ahorrador():
    titulo_pagina("💰", "Ahorrador", "Cuánto necesitas para jubilarte con tu nivel de vida y cuánto tardas en llegar a una meta")
    with st.expander("ℹ️ Cómo funciona el Ahorrador"):
        st.markdown("- Todo se calcula en **euros de hoy**: se descuenta la inflación para que las cifras se entiendan.\n"
                    "- **Capital necesario** = valor, el día que te jubilas, de los gastos mensuales que tu pensión no cubre.\n"
                    "- **Edad fija**: aseguras el gasto hasta una edad concreta. **Probabilidad de seguir vivo**: cada "
                    "mes de gasto se multiplica por la probabilidad de estar vivo (tablas de mortalidad del INE, "
                    "sabiendo que llegas vivo a la jubilación), sin fijar un tope duro.\n"
                    "- La pestaña **Meta de ahorro** calcula cuántos meses o cuánto al mes para llegar a una cantidad.")
    t_jub, t_meta, t_fire, t_fondo = st.tabs(["🎯 Jubilación", "⏱️ Meta de ahorro", "🔥 Independencia financiera",
                                                "🛟 Fondo de emergencia"])

    # ================================================================ jubilación
    with t_jub:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            edad = c1.number_input("Tu edad actual", 16, 80, 30, 1, key="a_edad")
            edad_ret = c2.number_input("Edad a la que te jubilas", 40, 80, 67, 1, key="a_ret",
                                       help="Cambia la edad para ver cuánto tendrías que ahorrar.")
            edad_fin = c3.number_input("Hasta qué edad quieres cobrar", 60, 110, 90, 1, key="a_fin",
                                       help="Solo se usa en el modo «Edad fija». Cuanto más años vivas, más capital "
                                            "necesitas.",
                                       disabled=st.session_state.get("a_modo_vida", "").startswith(("Según", "Prudente")))
            sueldo = c4.number_input("Salario neto mensual (€)", 300, 50_000, 2_000, 50, key="a_sueldo",
                                     help="Lo que cobras al mes después de impuestos.")
            d1, d2, d3, d4 = st.columns(4)
            pct_vida = d1.slider("Nivel de vida: % de tu salario neto", 30, 150, 80, 5, key="a_pct",
                                 help="El 70-80 % suele ser suficiente porque en la jubilación ya no ahorras ni "
                                      "pagas ciertos gastos.")
            pension = d2.number_input("Pensión pública estimada (€/mes, de hoy)", 0, 10_000, 0, 50, key="a_pen",
                                      help="Lo que esperas cobrar de la Seguridad Social. Se resta de lo que necesitas. "
                                           "Pon 0 si no la conoces.")
            ahorro0 = d3.number_input("Lo que ya tienes ahorrado (€)", 0, 10_000_000, 5_000, 500, key="a_ahorro0")
            aporte_actual = d4.number_input("Lo que ahorras ahora (€/mes)", 0, 50_000, 200, 25, key="a_aporte")
            with st.expander("Modo de cálculo: hasta cuándo necesitas cobrar (edad fija o mortalidad)"):
                e1, e2, e3 = st.columns([2, 1, 1])
                modo_vida = e1.radio("¿Hasta cuándo necesitas cobrar?",
                                     ["Edad fija (seguro que vives hasta esa edad)",
                                      "Según probabilidad de seguir vivo (tablas de mortalidad del INE)",
                                      "Prudente: hasta la edad a la que solo llega 1 de cada 10 (INE)"],
                                     key="a_modo_vida",
                                     help="El modo probabilístico pondera cada mes de gasto por la probabilidad de seguir "
                                          "vivo: es el valor actuarial «de media», así que en la mitad de los casos te "
                                          "quedarías corto si vives más. El prudente garantiza la renta hasta la edad "
                                          "que solo alcanza el 10 % de quienes llegan vivos a la jubilación.")
                usa_mort = modo_vida.startswith("Según")
                prudente = modo_vida.startswith("Prudente")
                sexo_lbl = e2.selectbox("Tabla de mortalidad", ["Total", "Hombres", "Mujeres"], key="a_sexo",
                                        disabled=not (usa_mort or prudente))
                edad_max = e3.number_input("Edad máxima de la tabla", 95, 110, 105, 1, key="a_emax", disabled=not usa_mort,
                                           help="A partir de esta edad se deja de contar el gasto (probabilidad ~0).")
            with st.expander("Opciones avanzadas: rentabilidad, inflación y gasto manual"):
                v1, v2, v3, v4 = st.columns(4)
                rent_pre = v1.number_input("Rentabilidad antes de jubilarte (% anual)", -2.0, 15.0, 5.0, 0.5,
                                           key="a_rpre", help="Nominal, es decir, antes de descontar la inflación.") / 100
                rent_post = v2.number_input("Rentabilidad ya jubilado (% anual)", -2.0, 15.0, 3.0, 0.5,
                                            key="a_rpost", help="Suele ser más baja porque se invierte con más "
                                                                "prudencia.") / 100
                infl = v3.number_input("Inflación (% anual)", 0.0, 10.0, 2.0, 0.25, key="a_inf") / 100
                g_ap = v4.number_input("Subida real anual de tu ahorro (%)", 0.0, 10.0, 0.0, 0.5, key="a_g",
                                       help="Si esperas ahorrar más cada año por encima de la inflación.") / 100
                gasto_man = st.number_input("Gasto mensual deseado (€ de hoy). 0 = usar el % de tu salario", 0, 50_000,
                                            0, 100, key="a_gasto")
                st.caption("Todas las cifras están en euros de hoy: se descuenta la inflación para que se entiendan "
                           "mejor. Referencia: el índice mundial rindió de media un 8-9 % anual nominal en el pasado, "
                           "y la renta fija suele moverse cerca del Euribor.")

        if edad_ret <= edad:
            st.warning("La edad de jubilación debe ser mayor que tu edad actual.")
        elif not (usa_mort or prudente) and edad_fin <= edad_ret:
            st.warning("La edad hasta la que quieres cobrar debe ser mayor que la de jubilación.")
        elif usa_mort and edad_max <= edad_ret:
            st.warning("La edad máxima de la tabla debe ser mayor que la de jubilación.")
        else:
            q_tabla = None
            if usa_mort or prudente:
                try:
                    q_tabla = fin.qx_por_edad(datos_mortalidad(), {"Total": "T", "Hombres": "H", "Mujeres": "M"}[sexo_lbl])
                except Exception as e:
                    st.error(f"No se pudo leer la tabla de mortalidad del INE ({e}). Uso la edad fija mientras tanto.")
                    usa_mort = prudente = False

            def pesos_para(er):
                return fin.pesos_supervivencia(er, q_tabla, edad_max) if usa_mort else None

            def fin_para(er):
                """Edad hasta la que se cobra según el modo elegido."""
                if prudente:
                    return int(np.ceil(fin.edad_prudente(er, q_tabla)))
                return edad_max if usa_mort else edad_fin

            def plan_para(er):
                w = pesos_para(er)
                return fin.plan_jubilacion(edad, er, fin_para(er), gasto, pension, ahorro0,
                                           aporte_actual, rent_pre, rent_post, infl, g_ap, pesos=w), w

            gasto = gasto_man if gasto_man > 0 else sueldo * pct_vida / 100
            p, pesos = plan_para(edad_ret)
            if usa_mort:
                edad_fin_txt = (f"los <b>{edad_max}</b> ponderando por la probabilidad de seguir vivo "
                                f"(esperanza de vida a esa edad: {fin.esperanza_vida(edad_ret, q_tabla):.1f} años más)")
            elif prudente:
                edad_fin_txt = (f"los <b>{fin_para(edad_ret)}</b>, la edad que solo alcanza 1 de cada 10 personas que "
                                f"llegan a los {edad_ret} (esperanza de vida: {fin.esperanza_vida(edad_ret, q_tabla):.1f} "
                                "años más)")
            else:
                edad_fin_txt = f"los <b>{edad_fin}</b>"
            anio_ret = pd.Timestamp.today().year + (edad_ret - edad)
            cap_nom = p["capital"] * (1 + infl) ** (p["N"] / 12)
            llegas = p["capital_actual"] / p["capital"] if p["capital"] else 1.0
            if p["aporte"] <= 0:
                frase_ahorro = "Con lo que ya tienes ahorrado y su rentabilidad <b>ya llegarías</b> sin ahorrar más."
            else:
                frase_ahorro = (f'Tendrías que ahorrar <b>{eur(p["aporte"])} al mes</b> '
                                f'({pct(p["aporte"] / sueldo, 0)} de tu salario neto)')
                frase_ahorro += (f', frente a los {eur(aporte_actual)} que ahorras ahora.' if aporte_actual else '.')
            st.markdown(
                f'<div class="resumen">Para vivir con <b>{eur(gasto)} al mes</b> (en euros de hoy) desde los '
                f'<b>{edad_ret} años</b> (en {anio_ret}) hasta {edad_fin_txt}'
                + (f', y contando con una pensión pública de <b>{eur(pension)}</b>' if pension else '')
                + f', necesitas <b>{eur(p["capital"])}</b> el día que te jubiles. {frase_ahorro}</div>',
                unsafe_allow_html=True)

            m = st.columns(4)
            m[0].metric("Capital necesario", eur(p["capital"]),
                        help=f"En euros de hoy. En euros de {anio_ret}, con inflación, serían unos {eur(cap_nom)}.")
            m[1].metric("Ahorro mensual necesario", eur(p["aporte"]), delta=f"{pct(p['aporte'] / sueldo, 0)} de tu sueldo",
                        delta_color="off")
            m[2].metric("Con tu ahorro actual llegas a", pct(llegas, 0),
                        help="Qué parte del capital necesario tendrás con lo que ahorras ahora.")
            m[3].metric("Renta que te darías", eur(p["renta_actual"] + pension),
                        delta=f"{pct((p['renta_actual'] + pension) / gasto, 0)} de tu objetivo", delta_color="off",
                        help="Lo que podrías gastar al mes (incluida la pensión pública) con tu ahorro actual.")

            g1, g2 = st.columns([3, 2], gap="large")
            with g1:
                st.markdown("**Tu dinero a lo largo de la vida**")
                explica("Sube mientras ahorras y baja cuando empiezas a retirar. Con el ahorro necesario llegas a "
                        "cero justo a la edad final." if not usa_mort else
                        "Saldo esperado: en la jubilación se retira cada mes la renta multiplicada por la probabilidad "
                        "de seguir vivo, por eso la curva baja despacio al final y llega a cero en la edad máxima.")
                retira = p["necesidad"] * pesos if usa_mort else p["necesidad"]
                tr_plan = fin.trayectoria(ahorro0, p["aporte"], p["N"], p["n_ret"], retira, p["r_pre"],
                                          p["r_post"], g_ap)
                tr_act = fin.trayectoria(ahorro0, aporte_actual, p["N"], p["n_ret"], retira, p["r_pre"],
                                         p["r_post"], g_ap)
                edades = edad + np.arange(len(tr_plan)) / 12
                fa = go.Figure()
                fa.add_scatter(x=edades, y=tr_plan, mode="lines", name="Con el ahorro necesario",
                               line=dict(color=C_CAP, width=3.5))
                fa.add_scatter(x=edades, y=tr_act, mode="lines", name="Con lo que ahorras ahora",
                               line=dict(color=C_INT, width=2.5, dash="dash"))
                fa.add_vline(x=edad_ret, line_dash="dot", line_color="#8B93A7", annotation_text="Jubilación",
                             annotation_position="top")
                fa.update_layout(xaxis_title="Edad", yaxis_title="€ de hoy")
                st.plotly_chart(estilo(fa, 420), width="stretch")
            with g2:
                st.markdown("**¿Y si me jubilo antes o después?**")
                explica("Ahorro mensual necesario según la edad de jubilación. La barra naranja es la que has elegido.")
                tope_r = fin_para(edad_ret) - 1
                edades_r = [x for x in range(max(edad + 1, 50), min(tope_r, 75) + 1)]
                aportes_r = [plan_para(x)[0]["aporte"] for x in edades_r]
                fb = go.Figure(go.Bar(x=edades_r, y=aportes_r,
                                      marker_color=[C_INT if x == edad_ret else C_CAP for x in edades_r],
                                      hovertemplate="Jubilación a los %{x}: %{y:,.0f} €/mes<extra></extra>"))
                fb.update_layout(xaxis_title="Edad de jubilación", yaxis_title="€ al mes")
                st.plotly_chart(estilo(fb, 420, "no"), width="stretch")

            with st.expander("Detalle de los cálculos"):
                st.markdown(
                    f"- Años ahorrando: **{p['N'] // 12}**; años de tabla/cobro: **{p['n_ret'] // 12}**"
                    + (f" (gasto ponderado por probabilidad de seguir vivo, tabla INE {sexo_lbl.lower()})" if usa_mort else "")
                    + ".\n"
                    f"- Lo que necesitas cada mes de tu propio dinero: **{eur(p['necesidad'])}** "
                    f"({eur(gasto)} de nivel de vida − {eur(pension)} de pensión).\n"
                    f"- Rentabilidad real (sin inflación): **{pct(p['r_pre'] * 12, 2)}** al año antes de jubilarte y "
                    f"**{pct(p['r_post'] * 12, 2)}** después (aprox.).\n"
                    f"- Tu ahorro actual ({eur(ahorro0)}) crece hasta **{eur(p['crece_ahorro'])}** (euros de hoy).\n"
                    "- Resultado orientativo: no incluye impuestos sobre la rentabilidad ni comisiones.")

            with st.expander("Sensibilidad: ¿y si la rentabilidad es distinta?"):
                explica("Ahorro mensual necesario según la rentabilidad antes (filas) y después de jubilarte (columnas). "
                        "Sirve para ver cuánto depende el plan de un supuesto.")
                var = [-0.02, -0.01, 0.0, 0.01, 0.02]
                filas_s = {}
                for dpre in var:
                    fila_s = {}
                    for dpost in var:
                        pl_s = fin.plan_jubilacion(edad, edad_ret, fin_para(edad_ret), gasto, pension,
                                                   ahorro0, aporte_actual, rent_pre + dpre, rent_post + dpost, infl,
                                                   g_ap, pesos=pesos)
                        fila_s[f"Después {(rent_post + dpost) * 100:.1f} %"] = pl_s["aporte"]
                    filas_s[f"Antes {(rent_pre + dpre) * 100:.1f} %"] = fila_s
                st.dataframe(pd.DataFrame(filas_s).T, width="stretch",
                             column_config={c: st.column_config.NumberColumn(format="%.0f €") for c in
                                            next(iter(filas_s.values()))})

    # ================================================================ independencia financiera
    with t_fire:
        explica("Independencia financiera: tener un capital que, retirando cada año un porcentaje pequeño, cubra tus "
                "gastos sin tener que trabajar. La regla clásica es el 4 % (capital = 25 veces el gasto anual). "
                "Cifras en euros de hoy.")
        with st.container(border=True):
            f1, f2, f3, f4 = st.columns(4)
            gasto_f = f1.number_input("Gasto mensual que quieres cubrir (€)", 300, 50_000, 1_800, 50, key="f_gasto")
            tasa_f = f2.number_input("Tasa de retirada segura (%)", 2.0, 8.0, 4.0, 0.25, key="f_tasa",
                                     help="4 % es la regla clásica. En plazos muy largos suele recomendarse 3-3,5 %.") / 100
            ahorro_f = f3.number_input("Lo que ya tienes (€)", 0, 50_000_000, 10_000, 500, key="f_ini")
            aporte_f = f4.number_input("Lo que ahorras al mes (€)", 0, 100_000, 600, 25, key="f_apo")
            g1, g2, g3 = st.columns(3)
            rent_f = g1.number_input("Rentabilidad anual (%)", -2.0, 15.0, 5.0, 0.5, key="f_rent") / 100
            infl_f = g2.number_input("Inflación (% anual)", 0.0, 10.0, 2.0, 0.25, key="f_infl") / 100
            edad_f = g3.number_input("Tu edad", 16, 80, 30, 1, key="f_edad")
        objetivo_f = gasto_f * 12 / tasa_f
        i_f = fin.r_mensual(rent_f, infl_f, real=True)
        n_f = fin.meses_para_meta(objetivo_f, ahorro_f, aporte_f, i_f)
        mf = st.columns(4)
        mf[0].metric("Capital para ser independiente", eur(objetivo_f), help=f"{gasto_f * 12:,.0f} € al año ÷ {tasa_f * 100:.2f} %".replace(",", "."))
        mf[1].metric("Ya tienes", pct(min(ahorro_f / objetivo_f, 1.0), 0))
        if n_f is None:
            mf[2].metric("Tiempo necesario", "No se llega")
            st.warning("Con ese ahorro y esa rentabilidad no se alcanza nunca. Sube el ahorro mensual.")
        else:
            mf[2].metric("Tiempo necesario", _anios_meses(n_f))
            mf[3].metric("Edad de independencia", f"{edad_f + n_f / 12:.1f} años")
            st.markdown(f'<div class="resumen">Ahorrando <b>{eur(aporte_f)} al mes</b> llegarás a <b>{eur(objetivo_f)}</b> '
                        f'en <b>{_anios_meses(n_f)}</b>, a los <b>{edad_f + n_f / 12:.0f} años</b>. Desde ahí podrías '
                        f'retirar {eur(gasto_f)} al mes de forma sostenible.</div>', unsafe_allow_html=True)
            sf = fin.serie_ahorro(ahorro_f, aporte_f, max(n_f, 1), i_f)
            ff = go.Figure()
            ff.add_scatter(x=edad_f + sf.mes / 12, y=sf.total, mode="lines", name="Tu ahorro", line=dict(color=C_CAP, width=3.5))
            ff.add_hline(y=objetivo_f, line_dash="dash", line_color=C_INT, annotation_text="Independencia")
            ff.update_layout(xaxis_title="Edad", yaxis_title="€ de hoy")
            st.plotly_chart(estilo(ff, 360), width="stretch")
        st.markdown("**¿Y si ahorro más o con otra tasa de retirada?**")
        filas_fi = []
        for ap_ in sorted(set([aporte_f // 2, aporte_f, int(aporte_f * 1.5), aporte_f * 2, aporte_f * 3])):
            fila_fi = {"Ahorro mensual": float(ap_)}
            for t_ in (0.03, 0.035, 0.04, 0.05):
                nn = fin.meses_para_meta(gasto_f * 12 / t_, ahorro_f, ap_, i_f)
                fila_fi[f"Retirada {t_ * 100:.1f} %"] = (nn / 12) if nn is not None else np.nan
            filas_fi.append(fila_fi)
        st.dataframe(pd.DataFrame(filas_fi), hide_index=True, width="stretch", column_config={
            "Ahorro mensual": st.column_config.NumberColumn(format="%.0f €"),
            **{f"Retirada {t_ * 100:.1f} %": st.column_config.NumberColumn(format="%.1f años")
               for t_ in (0.03, 0.035, 0.04, 0.05)}})

    # ================================================================ fondo de emergencia
    with t_fondo:
        explica("Colchón de dinero fácil de sacar para imprevistos (perder el empleo, una avería…). Lo habitual son "
                "3-6 meses de gastos esenciales; más si tu ingreso es variable.")
        with st.container(border=True):
            h1, h2, h3, h4 = st.columns(4)
            gasto_e = h1.number_input("Gastos esenciales al mes (€)", 200, 20_000, 1_400, 50, key="e_gasto")
            meses_e = h2.slider("Meses de colchón", 1, 24, 6, 1, key="e_meses")
            ahorro_e = h3.number_input("Lo que ya tienes en el colchón (€)", 0, 1_000_000, 1_000, 100, key="e_ini")
            aporte_e = h4.number_input("Lo que le dedicas al mes (€)", 0, 20_000, 200, 25, key="e_apo")
            rent_e = st.number_input("Rentabilidad de la cuenta (% anual)", 0.0, 6.0, 2.0, 0.25, key="e_rent") / 100
        objetivo_e = gasto_e * meses_e
        n_e = fin.meses_para_meta(objetivo_e, ahorro_e, aporte_e, fin.r_mensual(rent_e, 0.0, real=False))
        me = st.columns(4)
        me[0].metric("Colchón objetivo", eur(objetivo_e))
        me[1].metric("Cubres ahora", f"{ahorro_e / gasto_e:.1f} meses")
        me[2].metric("Te falta", eur(max(objetivo_e - ahorro_e, 0)))
        me[3].metric("Tiempo para completarlo", "Ya lo tienes" if ahorro_e >= objetivo_e else
                     (_anios_meses(n_e) if n_e else "No se llega"))
        niveles_e = pd.DataFrame({"Meses": [3, 6, 9, 12], "Colchón": [gasto_e * m_ for m_ in (3, 6, 9, 12)]})
        niveles_e["Tiempo"] = [("Ya" if ahorro_e >= c_ else (_anios_meses(fin.meses_para_meta(c_, ahorro_e, aporte_e,
                               fin.r_mensual(rent_e, 0.0, real=False))) if fin.meses_para_meta(c_, ahorro_e, aporte_e,
                               fin.r_mensual(rent_e, 0.0, real=False)) else "No se llega")) for c_ in niveles_e["Colchón"]]
        st.dataframe(niveles_e, hide_index=True, width="stretch",
                     column_config={"Colchón": st.column_config.NumberColumn(format="%.0f €")})

    # ================================================================ meta de ahorro
    with t_meta:
        modo = st.radio("¿Qué quieres calcular?", ["¿Cuántos meses necesito ahorrar?", "¿Cuánto debo ahorrar al mes?"],
                        horizontal=True, key="m_modo")
        with st.container(border=True):
            q1, q2, q3, q4 = st.columns(4)
            objetivo = q1.number_input("Cantidad que quieres conseguir (€)", 100, 50_000_000, 20_000, 500, key="m_obj")
            ahorro_ini = q2.number_input("Lo que ya tienes (€)", 0, 50_000_000, 0, 500, key="m_ini")
            if modo.startswith("¿Cuántos"):
                aporte_m = q3.number_input("Puedes ahorrar al mes (€)", 0, 100_000, 400, 25, key="m_aporte")
                plazo_m = 0
            else:
                plazo_m = q3.number_input("En cuántos meses lo quieres", 1, 1200, 36, 1, key="m_plazo")
                aporte_m = 0
            rent_m = q4.number_input("Rentabilidad anual (%)", -2.0, 15.0, 3.0, 0.5, key="m_rent",
                                     help="0 % si lo guardas sin invertir. Una cuenta remunerada suele dar un 2-3 %.") / 100
            ajusta = st.checkbox("La cantidad está en euros de hoy: tener en cuenta la inflación", key="m_infl",
                                 help="Si lo marcas, la rentabilidad se calcula sin inflación (real) y se supone que "
                                      "ahorras algo más cada año para seguir el ritmo de los precios.")
            infl_m = st.number_input("Inflación (% anual)", 0.0, 10.0, 2.0, 0.25, key="m_infv",
                                     disabled=not ajusta) / 100 if ajusta else 0.0
        i_m = fin.r_mensual(rent_m, infl_m, real=ajusta)

        if modo.startswith("¿Cuántos"):
            n = fin.meses_para_meta(objetivo, ahorro_ini, aporte_m, i_m)
            if n is None:
                st.warning("Con ese ahorro y esa rentabilidad no se llega nunca a la cantidad. Sube el ahorro mensual.")
                return
            aportado_total = ahorro_ini + aporte_m * n
        else:
            n = int(plazo_m)
            aporte_m = fin.aporte_para_meta(objetivo, ahorro_ini, n, i_m)
            aportado_total = ahorro_ini + aporte_m * n
        sa = fin.serie_ahorro(ahorro_ini, aporte_m, max(n, 1), i_m)
        intereses = float(sa.intereses.iloc[-1])
        fecha = pd.Timestamp.today() + pd.DateOffset(months=n)
        if n == 0:
            st.success("¡Ya tienes esa cantidad!")
        else:
            st.markdown(
                f'<div class="resumen">Para llegar a <b>{eur(objetivo)}</b> ahorrando <b>{eur(aporte_m, 2) if not modo.startswith("¿Cuántos") else eur(aporte_m)} '
                f'al mes</b> necesitas <b>{n} meses</b> ({_anios_meses(n)}), es decir, hasta aproximadamente '
                f'<b>{fecha:%m/%Y}</b>. De ese dinero, <b>{eur(aportado_total)}</b> lo pones tú y '
                f'<b>{eur(max(intereses, 0))}</b> lo genera la rentabilidad.</div>', unsafe_allow_html=True)
        k = st.columns(4)
        k[0].metric("Meses necesarios" if modo.startswith("¿Cuántos") else "Plazo", f"{n} meses",
                    delta=_anios_meses(n), delta_color="off")
        k[1].metric("Ahorro mensual", eur(aporte_m, 0 if modo.startswith("¿Cuántos") else 2))
        k[2].metric("Lo pones tú", eur(aportado_total))
        k[3].metric("Lo genera la rentabilidad", eur(max(intereses, 0)))
        sueldo_ref = st.session_state.get("a_sueldo")
        if sueldo_ref and aporte_m:
            st.caption(f"Eso es el {pct(aporte_m / sueldo_ref, 0)} del salario neto que has puesto en «Jubilación» "
                       f"({eur(sueldo_ref)}).")

        h1, h2 = st.columns(2, gap="large")
        with h1:
            st.markdown("**¿Cómo crece tu ahorro?**")
            explica("Azul: lo que pones tú. Naranja: lo que añade la rentabilidad. La línea gris es tu meta.")
            fm = go.Figure()
            fm.add_scatter(x=sa.mes, y=sa.aportado, mode="lines", stackgroup="a", name="Lo que pones tú",
                           line=dict(color=C_CAP, width=0.5), fillcolor="rgba(76,154,255,.55)")
            fm.add_scatter(x=sa.mes, y=sa.intereses.clip(lower=0), mode="lines", stackgroup="a",
                           name="Rentabilidad", line=dict(color=C_INT, width=0.5), fillcolor="rgba(245,165,36,.65)")
            fm.add_hline(y=objetivo, line_dash="dash", line_color="#8B93A7", annotation_text="Meta")
            fm.update_layout(xaxis_title="Meses", yaxis_title="€")
            st.plotly_chart(estilo(fm, 380), width="stretch")
        with h2:
            st.markdown("**¿Y si ahorro más o menos?**")
            explica("Meses necesarios según lo que ahorras al mes.")
            base_ap = aporte_m if aporte_m > 0 else max(objetivo / 60, 50)
            opciones = sorted({max(int(round(base_ap * f / 10) * 10), 10) for f in (.5, .75, 1, 1.5, 2, 3, 4)})
            meses_op = [fin.meses_para_meta(objetivo, ahorro_ini, ap, i_m) for ap in opciones]
            pts = [(ap, mm) for ap, mm in zip(opciones, meses_op) if mm is not None]
            if pts:
                fs = go.Figure(go.Scatter(x=[x for x, _ in pts], y=[y for _, y in pts], mode="lines+markers",
                                          line=dict(color=C_CAP, width=3),
                                          hovertemplate="%{x:,.0f} €/mes: %{y} meses<extra></extra>"))
                fs.update_layout(xaxis_title="Ahorro al mes (€)", yaxis_title="Meses para llegar")
                st.plotly_chart(estilo(fs, 380, "no"), width="stretch")
                st.dataframe(pd.DataFrame({"Ahorro al mes": [x for x, _ in pts], "Meses": [y for _, y in pts],
                                           "Tiempo": [_anios_meses(y) for _, y in pts]}), hide_index=True,
                             width="stretch", column_config={
                                 "Ahorro al mes": st.column_config.NumberColumn(format="%.0f €")})
        st.caption("Orientativo: no incluye impuestos ni comisiones. Se asume que aportas a principio de cada mes.")
