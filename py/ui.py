"""Piezas compartidas por todas las páginas: constantes visuales, formato, ajustes globales y datos con caché.
Las páginas hacen `from ui import *`."""
import os
import sys

import numpy as np
import pandas as pd  # noqa: F401  (lo usan las páginas)
import plotly.graph_objects as go  # noqa: F401
import streamlit as st

CARPETA = os.path.dirname(os.path.abspath(__file__))   # .../Planificador Financiero/py
BASE = os.path.dirname(CARPETA)
ASSETS_DIR = os.path.join(BASE, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)
os.chdir(BASE)
sys.path.insert(0, CARPETA)
import finanzas as fin
import fondo

with open(os.path.join(CARPETA, "VERSION.txt"), encoding="utf-8-sig") as _f:
    VERSION = _f.read().strip()          # única fuente de la versión (la usa también generar_instaladores.py)
ICONO = os.path.join(ASSETS_DIR, "planificador.png")
COLORES = ["#4C9AFF", "#F5A524", "#2EC4A6", "#A78BFA", "#F472B6", "#EAB308", "#38BDF8", "#FB923C"]
C_CAP, C_INT, C_EXTRA, C_SALDO, C_MEDIA = "#4C9AFF", "#F5A524", "#2EC4A6", "#A78BFA", "#F5A524"
# colores semi-neón de la fórmula: un color por variable, el mismo en los parámetros y en la fórmula
NEON = {"cap": "#22F0FF", "tin": "#FF4FD8", "n": "#A6FF3D", "cuota": "#FFB02E", "tae": "#8C9EFF",
        "gris": "#8B93A7"}


CSS = """<style>
.block-container{padding-top:2.2rem;max-width:1500px}
.cab{display:flex;align-items:center;gap:14px;margin:0 0 10px}
.cab-ico{font-family:"Material Symbols Rounded";font-weight:400;font-style:normal;font-size:1.65rem;line-height:1;
 font-feature-settings:"liga";-webkit-font-feature-settings:"liga";display:grid;place-items:center;width:46px;height:46px;
 border-radius:12px;background:rgba(76,154,255,.14);border:1px solid rgba(76,154,255,.35);color:#4C9AFF;flex:none}
.cab h1{font-size:1.9rem;font-weight:700;margin:0;padding:0;letter-spacing:-.02em}
.bloque{display:flex;align-items:center;gap:.55rem;font-weight:650;font-size:1.02rem;margin:0 0 .5rem}
.bloque span{font-family:"Material Symbols Rounded";font-weight:400;font-size:1.25rem;line-height:1;font-feature-settings:"liga";
 -webkit-font-feature-settings:"liga";display:inline-grid;place-items:center;width:1.9rem;height:1.9rem;border-radius:8px;
 background:rgba(76,154,255,.14);color:#4C9AFF}
.cab-sub{margin:2px 0 0;font-size:.95rem;opacity:.8}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:2px 0 20px}
.chip{display:inline-flex;align-items:center;gap:7px;padding:5px 13px;border-radius:999px;
 background:rgba(128,128,128,.10);border:1px solid rgba(128,128,128,.20);font-size:.84rem;
 line-height:1.45;white-space:nowrap}
.chip b{font-weight:400;font-size:.95em}
[data-testid="stMetric"]{background:rgba(128,128,128,.07);border:1px solid rgba(128,128,128,.16);
 border-radius:14px;padding:14px 16px}
[data-testid="stMetric"]:first-child{border-color:rgba(46,158,91,.45)}
[data-testid="stMetricValue"]{font-size:1.6rem;font-weight:700;letter-spacing:-.02em}
[data-testid="stMetricValue"]>div,[data-testid="stMetricLabel"]>div,[data-testid="stMetricDelta"]>div{
 overflow:visible!important;text-overflow:clip!important;white-space:normal!important;line-height:1.25}
[data-testid="stMetricLabel"] p{font-size:.82rem;opacity:.82;text-transform:uppercase;letter-spacing:.04em}
h2,h3{letter-spacing:-.01em}
[data-testid="stHeadingWithActionElements"] h2{font-size:1.25rem;margin-top:1.6rem;
 padding-bottom:.4rem;border-bottom:1px solid rgba(128,128,128,.18)}
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden;border:1px solid rgba(128,128,128,.18)}
[data-testid="stElementContainer"] .stButton>button{border-radius:10px}
[data-testid="stSidebar"] [data-testid="stExpander"]{border:none;background:rgba(128,128,128,.06);
 border-radius:12px;margin-bottom:8px}
[data-testid="stCaptionContainer"] p{opacity:.82}
[data-testid="stStatusWidget"]{visibility:hidden}
[data-testid="stMarkdownContainer"] p,[data-testid="stMarkdownContainer"] li{font-size:1.02rem;line-height:1.55}
button:focus-visible,input:focus-visible,a:focus-visible,[role="tab"]:focus-visible{outline:3px solid #4C9AFF!important;outline-offset:2px}
a{text-underline-offset:2px}
[data-testid="stSidebarNav"] a,[data-testid="stPageLink-NavLink"]{border-radius:8px}
[data-baseweb="tab-list"] button{font-size:1.02rem;padding:.65rem 1rem;min-height:44px}
@media (max-width:640px){h1{font-size:1.6rem!important}.cab h1{font-size:1.5rem}.chip{white-space:normal}}
.resumen{background:rgba(76,154,255,.10);border:1px solid rgba(76,154,255,.35);border-radius:14px;
 padding:14px 18px;margin:6px 0 16px;font-size:1.08rem;line-height:1.6}

/* ---- panel de fórmula, colores semi-neón (fondo propio: se ve igual en tema claro y oscuro) ---- */
.neon{background:linear-gradient(160deg,#0c0f1a,#10121f);border:1px solid rgba(34,240,255,.30);
 border-radius:18px;padding:20px 22px;color:#C9D1E6;
 box-shadow:0 0 0 1px rgba(255,79,216,.10) inset,0 0 26px rgba(34,240,255,.10),0 0 40px rgba(255,79,216,.06)}
.neon h4{margin:0 0 12px;font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;color:#8B93A7;font-weight:600}
.neon .f{font-family:'Cambria Math','STIX Two Math','Times New Roman',serif;font-size:1.32rem;line-height:2.1;
 margin:2px 0 14px;overflow-wrap:anywhere}
.neon .f.s{font-size:1.04rem;line-height:1.9;color:#AEB7CF}
.neon .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:6px 34px}
.neon .grid>div{min-width:0}
.neon .sep{height:1px;background:linear-gradient(90deg,rgba(34,240,255,.35),rgba(255,79,216,.35),transparent);
 margin:12px 0}
.neon .nota{font-size:.78rem;color:#7C849A;line-height:1.5}
.nc{color:#22F0FF;text-shadow:0 0 9px rgba(34,240,255,.65)}
.nt{color:#FF4FD8;text-shadow:0 0 9px rgba(255,79,216,.65)}
.nn{color:#A6FF3D;text-shadow:0 0 9px rgba(166,255,61,.55)}
.nq{color:#FFB02E;text-shadow:0 0 9px rgba(255,176,46,.60)}
.na{color:#8C9EFF;text-shadow:0 0 9px rgba(140,158,255,.60)}
.neon .tag{display:inline-block;font-size:.72rem;padding:1px 9px;margin:0 6px 4px 0;border-radius:999px;
 border:1px solid currentColor;opacity:.9}
/* barra del test */
.medidor{position:relative;height:12px;border-radius:99px;margin:10px 0 26px;
 background:linear-gradient(90deg,#2EC4A6,#EAB308 50%,#E5484D)}
.medidor i{position:absolute;top:-6px;width:4px;height:24px;border-radius:3px;background:#fff;
 box-shadow:0 0 0 2px rgba(0,0,0,.45)}
</style>"""


def aplicar_estilos():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(fondo.html("dark" if es_oscuro() else "light"), unsafe_allow_html=True)


# ------------------------------------------------------------------ utilidades
def es_oscuro():
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return True


def estilo(fig, alto=380, leyenda="abajo"):
    """Estilo común. La leyenda va debajo del gráfico para no tapar los datos."""
    oscuro = es_oscuro()
    tinta = "#E8EAED" if oscuro else "#202124"
    rejilla = "rgba(255,255,255,.10)" if oscuro else "rgba(0,0,0,.10)"
    fig.update_layout(
        template="plotly_dark" if oscuro else "plotly_white", colorway=COLORES, height=alto,
        margin=dict(l=8, r=8, t=16, b=8),
        font=dict(family="Inter, Segoe UI, system-ui, sans-serif", size=14, color=tinta),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(font_size=14, bordercolor="rgba(0,0,0,0)"),
        legend=dict(orientation="h", yanchor="top", y=-0.2, x=0, title_text="", font_size=13),
        showlegend=leyenda != "no")
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=rejilla, ticks="outside", tickcolor=rejilla)
    fig.update_yaxes(gridcolor=rejilla, zeroline=False, linecolor="rgba(0,0,0,0)")
    return fig


def explica(texto):
    """Frase corta bajo el título de un gráfico: cómo leerlo."""
    st.caption(texto)


def titulo_pagina(icono, texto, subtitulo=None):
    st.markdown(f'<div class="cab"><span class="cab-ico" aria-hidden="true">{icono}</span><div><h1>{texto}</h1>'
                + (f'<p class="cab-sub">{subtitulo}</p>' if subtitulo else "") + "</div></div>",
                unsafe_allow_html=True)


def bloque(titulo, icono="tune"):
    """Encabezado de un bloque de datos de entrada (icono y título), para que todas las páginas arranquen igual."""
    st.markdown(f'<div class="bloque"><span aria-hidden="true">{icono}</span>{titulo}</div>', unsafe_allow_html=True)


def chips(lista):
    st.markdown('<div class="chips">' + "".join(f'<span class="chip"><b>{i}</b> {t}</span>' for i, t in lista)
                + "</div>", unsafe_allow_html=True)


def eur(x, dec=0):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    s = f"{x:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".") + " €"


def pct(x, dec=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x * 100:.{dec}f}".replace(".", ",") + " %"


def num(x, dec=2):
    return f"{x:,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")


# ------------------------------------------------------------------ ajustes globales (barra lateral)
def modo_real():
    """True si el usuario ha elegido ver todo en términos reales (descontando la inflación)."""
    return bool(st.session_state.get("g_real", False))


def infl_euro_esperada():
    return float(st.session_state.get("g_infl_eur", fin.INFLACION_EURO_DEFECTO * 100)) / 100


def bloque_mc():
    return int(st.session_state.get("g_bloque", fin.BLOQUE_DEFECTO))


def rf_efectivo(r):
    """Tipo de la renta fija a usar: el nominal, o el real (con la inflación esperada del euro) en modo real."""
    return fin.tasa_real(r, infl_euro_esperada()) if modo_real() else r


def etiqueta_modo():
    return ("en términos reales (bolsa deflactada con el IPC de EE.UU., renta fija con la inflación del euro)"
            if modo_real() else "en términos nominales (sin descontar la inflación)")


def montecarlo(*args, **kw):
    return fin.montecarlo(*args, bloque=bloque_mc(), **kw)


def frontera(*args, **kw):
    return fin.frontera(*args, bloque=bloque_mc(), **kw)


# ------------------------------------------------------------------ datos de mercado (con caché)
@st.cache_data(ttl=3600, show_spinner="Leyendo tipos del euro (BCE)…")
def datos_tipos_actuales():
    return fin.tipos_actuales()


def tipos_actuales():
    """(dict con euribor12m y bono10, dict de errores por serie)."""
    return datos_tipos_actuales()


@st.cache_data(ttl=3600, show_spinner="Descargando la curva de tipos del euro (BCE), solo la primera vez…")
def datos_curva():
    try:
        return fin.curva_bce(), None
    except Exception as e:
        return None, str(e)[:500]


@st.cache_data(ttl=3600, show_spinner="Descargando el índice (Yahoo Finance)…")
def _datos_indice(nombre, real):
    try:
        return fin.indice_anual(nombre, real=real), fin.indice_mensual(nombre, real=real), None
    except Exception as e:
        fin.registrar_error(f"datos_indice {nombre}", e)
        return None, None, str(e)[:500]


def datos_indice(nombre):
    """(rentabilidades anuales, nivel mensual, error). Respeta el modo nominal / real."""
    return _datos_indice(nombre, modo_real())


@st.cache_data(ttl=3600, show_spinner="Descargando el índice semanal…")
def _serie_semanal(nombre, real):
    return fin.indice_semanal(nombre, real=real).values


def serie_semanal(nombre):
    return _serie_semanal(nombre, modo_real())


@st.cache_data(ttl=3600, show_spinner="Leyendo la inflación de la zona euro (BCE)…")
def _inflacion_euro():
    try:
        return fin.inflacion_anual(fin.hicp_euro())
    except Exception as e:
        fin.registrar_error("HICP zona euro", e)
        return None


def inflacion_rf():
    """Inflación anual del euro por año para la renta fija histórica (solo en modo real)."""
    return _inflacion_euro() if modo_real() else None


@st.cache_data(ttl=3600, show_spinner="Calculando el mal escenario de cada plazo…")
def _tabla_mal_escenario(indice, r_rf, pesos, q, real):
    try:
        v = fin.indice_semanal(indice, real=real).values
        return fin.mal_escenario(v, list(pesos), r_rf, np.arange(1, 30.01, 0.5), q)
    except Exception as e:
        fin.registrar_error(f"mal_escenario {indice}", e)
        return None


def tabla_mal_escenario(indice, r_rf, pesos, q):
    return _tabla_mal_escenario(indice, r_rf, pesos, q, modo_real())


@st.cache_data(ttl=3600, show_spinner="Calculando probabilidades semana a semana…")
def _curvas_plazos(indice, r_rf, pesos, estrategia, real):
    try:
        v = fin.indice_semanal(indice, real=real).values
        raw, suav = fin.prob_perder_semanal(v, list(pesos), r_rf, estrategia=estrategia)
        return raw, suav, None
    except Exception as e:
        fin.registrar_error(f"curvas_plazos {indice}", e)
        return None, None, str(e)[:500]


def curvas_plazos(indice, r_rf, pesos, estrategia):
    return _curvas_plazos(indice, r_rf, pesos, estrategia, modo_real())


def refrescar_mercado():
    for f in (_curvas_plazos, _tabla_mal_escenario, datos_tipos_actuales, datos_curva, _datos_indice,
              _serie_semanal, _inflacion_euro):
        f.clear()
    fin.tipos_actuales(forzar=True)
    for n in fin.INDICES:
        try:
            fin.indice_mensual(n, forzar=True)
            fin.indice_semanal(n, forzar=True)
        except Exception as e:
            fin.registrar_error(f"Actualizar {n}", e)
    for f in (fin.ipc_eeuu, fin.hicp_euro):
        try:
            f(forzar=True)
        except Exception as e:
            fin.registrar_error("Actualizar inflación", e)
