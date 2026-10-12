"""Fondo animado del planificador: curvas de mercado que se desplazan sin parar sobre un degradado, con cuadrícula tenue y
paneles translúcidos para que se lea todo. CSS y SVG puros inyectados con st.markdown: sin JavaScript ni imágenes."""
import random

# colores por tema: fondo, panel translúcido, curvas (de la más lenta y lejana a la más rápida y cercana) y brillos
TEMAS = {
    "dark": {"cielo": "linear-gradient(180deg,#060a16 0%,#0b1430 55%,#101c40 100%)", "panel": "rgba(8,12,26,.48)",
             "curvas": ["#4C9AFF", "#FF4FD8", "#22F0FF"], "opa": [.40, .52, .72], "rejilla": "rgba(140,158,255,.07)",
             "brillo": ["rgba(34,240,255,.12)", "rgba(255,79,216,.10)"]},
    "light": {"cielo": "linear-gradient(180deg,#e9f0fb 0%,#f3f6fd 55%,#fbfcff 100%)", "panel": "rgba(255,255,255,.62)",
              "curvas": ["#3b6fd8", "#c2399f", "#13a5b8"], "opa": [.30, .38, .52], "rejilla": "rgba(60,80,140,.07)",
              "brillo": ["rgba(59,111,216,.12)", "rgba(194,57,159,.08)"]},
}
PUNTOS = 44                 # por periodo; la curva se repite dos veces seguidas y se desliza medio ancho: sin salto
CAPAS = [(18, 46, 260, 1.10), (38, 40, 170, 1.00), (58, 34, 105, 0.95)]   # (arriba %, alto vh, segundos por vuelta, grosor)


def serie(semilla, n=PUNTOS):
    """Paseo aleatorio con tendencia que empieza y acaba en el mismo valor (para enlazar sin salto), entre 6 y 94."""
    rnd = random.Random(semilla)
    y = [0.0]
    for _ in range(n - 1):
        y.append(y[-1] + rnd.gauss(0, 1) + .12)
    y = [v - (y[-1] + .12 - y[0]) * i / n for i, v in enumerate(y)]      # el siguiente punto (el primero) cierra el ciclo
    lo, hi = min(y), max(y)
    return [6 + 88 * (v - lo) / ((hi - lo) or 1) for v in y]


def trazo(ys, x0, ancho):
    """Curva suave (Catmull-Rom a Bézier) cíclica de los puntos ys entre x0 y x0 + ancho, con las tangentes enlazadas."""
    n, paso = len(ys), ancho / len(ys)
    p = lambda i: (x0 + i * paso, 100 - ys[i % n])      # noqa: E731  (el SVG crece hacia abajo)
    d = f"M{p(0)[0]:.1f},{p(0)[1]:.1f}"
    for i in range(n):
        a, b, c, e = p(i - 1), p(i), p(i + 1), p(i + 2)
        d += (f"C{b[0] + (c[0] - a[0]) / 6:.1f},{b[1] + (c[1] - a[1]) / 6:.1f} "
              f"{c[0] - (e[0] - b[0]) / 6:.1f},{c[1] - (e[1] - b[1]) / 6:.1f} {c[0]:.1f},{c[1]:.1f}")
    return d


CSS = """<style>
.stApp{background:@cielo@!important;isolation:isolate}
[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:transparent!important}
[data-testid="stHeader"],[data-testid="stSidebar"]{background:@panel@!important;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.block-container{background:@panel@;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-radius:16px;
margin-top:.8rem;margin-bottom:1rem;border:1px solid rgba(128,140,180,.18)}
[data-testid="stElementContainer"]:has(.fx){position:absolute;width:0;height:0}
.fx{position:fixed;inset:0;z-index:-1;overflow:hidden;pointer-events:none}
.fx::before{content:"";position:absolute;inset:0;background-image:linear-gradient(@rejilla@ 1px,transparent 1px),
linear-gradient(90deg,@rejilla@ 1px,transparent 1px);background-size:90px 90px;
-webkit-mask-image:radial-gradient(ellipse at 50% 40%,#000 25%,transparent 80%);mask-image:radial-gradient(ellipse at 50% 40%,#000 25%,transparent 80%)}
.fx::after{content:"";position:absolute;inset:-25%;background:radial-gradient(38% 34% at 22% 28%,@b1@,transparent 70%),
radial-gradient(34% 38% at 78% 72%,@b2@,transparent 70%);animation:fxbrillo 40s ease-in-out infinite alternate}
.fx svg{position:absolute;left:0;width:200%;will-change:transform;animation:fxdesliza linear infinite}
.fx path{fill:none;stroke-linejoin:round;stroke-linecap:round;vector-effect:non-scaling-stroke}
@keyframes fxdesliza{to{transform:translateX(-50%)}}
@keyframes fxbrillo{to{transform:translate3d(7%,5%,0) scale(1.1)}}
@media (prefers-reduced-motion:reduce){.fx svg,.fx::after{animation:none}}
@media (max-width:640px){.block-container{border-radius:0;margin:0}.fx svg:nth-of-type(1){display:none}}
</style>"""


def html(tema="dark"):
    """Estilos del fondo más la capa fija con las curvas. tema: 'dark' o 'light'."""
    t = TEMAS.get(tema, TEMAS["dark"])
    css = CSS
    for k, v in {"cielo": t["cielo"], "panel": t["panel"], "rejilla": t["rejilla"], "b1": t["brillo"][0], "b2": t["brillo"][1]}.items():
        css = css.replace(f"@{k}@", v)
    capas = []
    for i, ((arriba, alto, seg, grosor), color, opa) in enumerate(zip(CAPAS, t["curvas"], t["opa"])):
        ys = serie(11 + i * 7)
        d = trazo(ys, 0, 1000) + " " + trazo(ys, 1000, 1000)
        relleno = (f'<path d="{d} L2000,100 L0,100Z" style="fill:url(#fxg{i});stroke:none"/>' if i == 0 else "")
        capas.append(
            f'<svg viewBox="0 0 2000 100" preserveAspectRatio="none" style="top:{arriba}%;height:{alto}vh;animation-duration:{seg}s;opacity:{opa}">'
            f'<defs><linearGradient id="fxg{i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{color}" stop-opacity=".28"/>'
            f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>{relleno}'
            f'<path d="{d}" style="stroke:{color};stroke-width:{grosor * 1.6:.2f}px;filter:drop-shadow(0 0 5px {color})"/></svg>')
    return f'{css}<div class="fx">{"".join(capas)}</div>'
