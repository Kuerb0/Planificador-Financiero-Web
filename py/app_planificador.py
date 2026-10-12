"""Planificador financiero — app Streamlit (se abre desde planificador_app.pyw).

Páginas (cada una en py/paginas/): Hipoteca · Cartera · Comparador · Mercado · Plazos y riesgo ·
Ahorrador · Asignador · Test de riesgo. Lo común (estilos, formato, ajustes y datos con caché) está en ui.py
y todos los cálculos en finanzas.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import streamlit as st  # noqa: E402

from ui import ICONO, VERSION, aplicar_estilos, fin, refrescar_mercado, modo_real  # noqa: E402

st.set_page_config(page_title="Planificador financiero", layout="wide",
                   page_icon=ICONO if os.path.exists(ICONO) else ":material/euro:")
aplicar_estilos()

from paginas.hipoteca import pag_hipoteca  # noqa: E402
from paginas.cartera import pag_cartera  # noqa: E402
from paginas.comparador import pag_comparador  # noqa: E402
from paginas.mercado import pag_mercado  # noqa: E402
from paginas.plazos import pag_plazos  # noqa: E402
from paginas.ahorrador import pag_ahorrador  # noqa: E402
from paginas.asignador import pag_asignador  # noqa: E402
from paginas.test_riesgo import pag_test  # noqa: E402


# =====================================================================  NAVEGACIÓN
PAGINAS = [
    st.Page(pag_hipoteca, title="Hipoteca", icon=":material/home:", default=True),
    st.Page(pag_cartera, title="Cartera", icon=":material/show_chart:", url_path="cartera"),
    st.Page(pag_comparador, title="Comparador", icon=":material/balance:", url_path="comparador"),
    st.Page(pag_mercado, title="Mercado", icon=":material/public:", url_path="mercado"),
    st.Page(pag_plazos, title="Plazos y riesgo", icon=":material/hourglass_top:", url_path="plazos"),
    st.Page(pag_ahorrador, title="Ahorrador", icon=":material/savings:", url_path="ahorrador"),
    st.Page(pag_asignador, title="Asignador", icon=":material/pie_chart:", url_path="asignador"),
    st.Page(pag_test, title="Test de riesgo", icon=":material/explore:", url_path="test"),
]
pg = st.navigation(PAGINAS, position="hidden")
sb = st.sidebar
for _p in PAGINAS:
    sb.page_link(_p)

_perf = fin.leer_perfiles()
if _perf["usuarios"]:
    lista = list(_perf["usuarios"])
    ya = _perf.get("activo") if _perf.get("activo") in lista else lista[0]
    nuevo = sb.selectbox("Usuario", lista, index=lista.index(ya), key="usuario_sel")
    if nuevo != _perf.get("activo"):
        fin.usuario_activo(nuevo)
    pf = _perf["usuarios"][nuevo]
    sb.caption(f"Perfil {pf['nivel']} · {pf['rv_sugerida']} % renta variable sugerido")
else:
    sb.caption("Sin perfil de riesgo: haz el test.")
_cfg = fin.leer_config()
st.session_state.setdefault("g_real", bool(_cfg.get("modo_real", False)))
st.session_state.setdefault("g_infl_eur", float(_cfg.get("inflacion_euro", fin.INFLACION_EURO_DEFECTO * 100)))
st.session_state.setdefault("g_bloque", int(_cfg.get("bloque_mc", fin.BLOQUE_DEFECTO)))


def _guardar_ajustes():
    fin.guardar_config(modo_real=bool(st.session_state["g_real"]), inflacion_euro=float(st.session_state["g_infl_eur"]),
                       bloque_mc=int(st.session_state["g_bloque"]))


with sb.expander(":material/settings: Ajustes de simulación", expanded=False):
    st.toggle("Ver en términos reales (descontar inflación)", key="g_real", on_change=_guardar_ajustes,
              help="Bolsa (en dólares) deflactada con el IPC de EE.UU. (FRED); renta fija (en euros) con la inflación "
                   "de la zona euro (HICP del BCE) en los modos históricos y con la inflación esperada en el modo "
                   "de tipo constante. «Perder» pasa a significar perder poder adquisitivo.")
    st.number_input("Inflación esperada del euro (% anual)", 0.0, 10.0, step=0.25, key="g_infl_eur",
                    on_change=_guardar_ajustes, disabled=not modo_real(),
                    help="Se usa para pasar a real la renta fija a tipo constante. 2 % = objetivo del BCE.")
    st.slider("Monte Carlo: años seguidos por bloque", 1, 10, key="g_bloque", on_change=_guardar_ajustes,
              help="Block bootstrap: se sortean tramos de años consecutivos del pasado para conservar las rachas "
                   "(crisis de varios años, rebotes). 1 = años sueltos e independientes (método clásico).")
sb.caption("Modo **real** · dinero de hoy" if modo_real() else "Modo **nominal**")
if sb.button("Actualizar datos de mercado", help="Vuelve a descargar los índices (Yahoo Finance) y los tipos del BCE"):
    refrescar_mercado()
    st.rerun()
with sb.expander(":material/menu_book: Glosario sencillo"):
    st.markdown(
        "- **TIN**: interés anual que cobra el banco, sin contar comisiones.\n"
        "- **TAE**: coste anual real del préstamo, con comisiones y seguros. Sirve para comparar ofertas.\n"
        "- **Euribor**: tipo de referencia al que se ligan las hipotecas variables.\n"
        "- **Amortizar**: devolver parte del dinero prestado antes de tiempo.\n"
        "- **Renta variable**: bolsa. Rinde más de media pero sube y baja mucho.\n"
        "- **Renta fija**: bonos y depósitos. Más estable y menos rentable.\n"
        "- **Buy and hold**: inviertes todo el primer día y lo dejas sin tocar.\n"
        "- **Promediar (DCA)**: inviertes poco a poco, con aportaciones periódicas.\n"
        "- **Euros de hoy**: cifras sin inflación, para entender cuánto valdría el dinero con los precios actuales.\n"
        "- **Modo real**: todo descontando la inflación (EE.UU. para la bolsa en dólares, zona euro para la renta "
        "fija).\n"
        "- **Block bootstrap**: Monte Carlo que sortea tramos de varios años seguidos en vez de años sueltos.\n"
        "- **Monte Carlo**: miles de simulaciones con años sorteados del pasado.\n"
        "- **Mal / buen escenario**: solo 1 de cada 20 casos sale peor / mejor que eso (percentiles 5 y 95).\n"
        "- **Volatilidad**: cuánto sube y baja una inversión de un año a otro.\n"
        "- **TIR anualizada**: rentabilidad anual constante equivalente a lo que realmente ganaste.\n"
        "- **Nota T**: escala de media 50 y desviación 10; en el Asignador se lee como % de bolsa ideal.\n"
        "- **Mal escenario anualizado**: rentabilidad anual del 1 de cada 20 peor de los casos históricos.\n"
        "- **Caída desde máximos (drawdown)**: cuánto está el índice por debajo de su mejor valor anterior.\n"
        "- **TER / comisión**: coste anual del fondo, que se resta a la rentabilidad.\n"
        "- **Tasa de retirada segura**: % del capital que puedes gastar cada año sin agotarlo (regla del 4 %).")
sb.caption("Herramienta educativa con datos históricos. No constituye asesoramiento financiero.")
sb.caption(f"v{VERSION}")
if os.path.exists(ICONO):
    try:
        st.logo(ICONO, size="large")
    except Exception as e:                      # versiones de Streamlit sin st.logo(size=…)
        fin.registrar_error("st.logo", e)
pg.run()
