"""Planificador financiero: toda la lógica de cálculo, sin Streamlit.

- Hipoteca: cuota francesa, tipo fijo / variable / mixto, amortización anticipada, TAE, gastos de compra.
- Datos de mercado: índices de bolsa (Yahoo Finance vía yfinance), tipos del euro (Banco Central Europeo) e
  inflación (IPC de EE.UU. de FRED para la bolsa en dólares; HICP de la zona euro del BCE para la renta fija).
- Modo real: la bolsa se deflacta con la inflación de EE.UU. y la renta fija con la de la zona euro.
- Simulación de cartera: Monte Carlo (block bootstrap de rentabilidades anuales) y ventanas históricas, con tres
  formas de modelar la renta fija (tipo constante, «carry» histórico y vencimiento objetivo).
- Test de tolerancia al riesgo de Grable y Lytton (13 preguntas) y perfiles guardados por usuario.
"""
import io
import json
import math
import os
import re
import time
import urllib.request
from datetime import datetime

import numpy as np
import pandas as pd

CARPETA = os.path.dirname(os.path.abspath(__file__))   # .../Planificador Financiero/py
BASE = os.path.dirname(CARPETA)                          # .../Planificador Financiero
CSV_DIR = os.path.join(BASE, "csv")
PERFILES = os.path.join(BASE, "perfiles_riesgo.json")
CONFIG = os.path.join(BASE, "config_planificador.json")


# =====================================================================  HIPOTECA
def cuota(capital, tin, meses):
    """Cuota mensual constante (sistema francés). tin en tanto por uno anual."""
    if meses <= 0 or capital <= 0:
        return 0.0
    i = tin / 12
    if abs(i) < 1e-12:
        return capital / meses
    return capital * i / (1 - (1 + i) ** -meses)


def n_pagos(capital, tin, pago):
    """Meses que hacen falta para liquidar `capital` pagando `pago` al mes."""
    i = tin / 12
    if pago <= 0:
        return math.inf
    if abs(i) < 1e-12:
        return capital / pago
    x = 1 - capital * i / pago
    return math.inf if x <= 0 else -math.log(x) / math.log(1 + i)


def tin_del_mes(mes, tipo, tin_fijo, diferencial, euribor, paso_euribor, anios_fijos):
    """TIN anual aplicable en el mes `mes` (0 = primer mes). Los tipos solo cambian al empezar un año."""
    anio = mes // 12
    variable = max(euribor + paso_euribor * anio, -diferencial) + diferencial   # nunca por debajo de 0 %
    if tipo == "Fijo":
        return tin_fijo
    if tipo == "Mixto":
        return tin_fijo if anio < anios_fijos else variable
    return variable


def cuadro(capital, anios, tipo="Fijo", tin_fijo=0.03, diferencial=0.01, euribor=0.025, paso_euribor=0.0,
           anios_fijos=5, extra_mensual=0.0, extra_anual=0.0, modo_extra="plazo"):
    """Cuadro de amortización mensual. modo_extra: 'plazo' (mantiene cuota, acorta plazo) o 'cuota'."""
    n = int(round(anios * 12))
    args = (tipo, tin_fijo, diferencial, euribor, paso_euribor, anios_fijos)
    saldo = float(capital)
    tin = tin_del_mes(0, *args)
    pago = cuota(saldo, tin, n)
    filas = []
    mes = 0
    while saldo > 0.005 and mes < n:
        nuevo = tin_del_mes(mes, *args)
        if mes > 0 and abs(nuevo - tin) > 1e-12:           # revisión de tipo: se recalcula la cuota
            if modo_extra == "plazo":
                resto = math.ceil(n_pagos(saldo, tin, pago) - 1e-9)
                resto = min(max(resto, 1), n - mes)
            else:
                resto = n - mes
            pago = cuota(saldo, nuevo, resto)
        tin = nuevo
        interes = saldo * tin / 12
        amort = min(max(pago - interes, 0.0), saldo)
        extra = extra_mensual + (extra_anual if mes % 12 == 11 else 0.0)
        extra = min(extra, saldo - amort)
        saldo = saldo - amort - extra
        if saldo < 0.005:
            saldo = 0.0
        filas.append((mes + 1, tin, interes + amort, interes, amort, extra, saldo))
        mes += 1
        if extra > 0 and modo_extra == "cuota" and saldo > 0 and n - mes > 0:
            pago = cuota(saldo, tin, n - mes)
    df = pd.DataFrame(filas, columns=["mes", "tin", "cuota", "intereses", "amortizacion", "extra", "saldo"])
    df["anio"] = (df["mes"] - 1) // 12 + 1
    return df


def tae(capital, cuadro_df, neto_inicial_resta=0.0, coste_mensual=0.0):
    """TAE (tasa anual equivalente). Flujo inicial = capital - gastos ligados al préstamo; después, cada
    cuota + coste mensual (seguros vinculados). Resuelta por bisección sobre la TIR mensual."""
    flujos = [capital - neto_inicial_resta] + [-(c + coste_mensual) for c in cuadro_df["cuota"]]
    f = np.array(flujos, dtype=float)

    def vp(r):
        return float(np.sum(f / (1 + r) ** np.arange(len(f))))
    lo, hi = -0.02, 0.2
    if vp(lo) * vp(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        if vp(lo) * vp(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (1 + (lo + hi) / 2) ** 12 - 1


def gastos_compra(precio, tipo_vivienda="Usada", itp=0.06, iva=0.10, ajd=0.0075, notaria_registro=2500.0,
                  tasacion=400.0, comision_apertura=0.0, capital=0.0):
    """Desglose de gastos de la compra. 'Usada' paga ITP; 'Nueva' paga IVA + AJD."""
    d = {}
    if tipo_vivienda == "Usada":
        d["ITP"] = precio * itp
    else:
        d["IVA"] = precio * iva
        d["AJD"] = precio * ajd
    d["Notaría, registro y gestoría"] = notaria_registro
    d["Tasación"] = tasacion
    d["Comisión de apertura"] = capital * comision_apertura
    return d


# =====================================================================  DATOS DE MERCADO
LOG_ERRORES = os.path.join(BASE, "errores.log")


LOG_MAX_BYTES = 1_000_000


def registrar_error(contexto, exc):
    """Guarda el error completo en errores.log (para saber por qué falla una descarga).
    Cuando el log pasa de 1 MB se renombra a errores.old.log y se empieza uno nuevo."""
    try:
        import traceback
        if os.path.exists(LOG_ERRORES) and os.path.getsize(LOG_ERRORES) > LOG_MAX_BYTES:
            os.replace(LOG_ERRORES, LOG_ERRORES.replace(".log", ".old.log"))
        with open(LOG_ERRORES, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {contexto}: {exc!r}\n")
            f.write("".join(traceback.format_exception(exc))[-1500:] + "\n")
    except Exception:
        pass


AGENTE = "Mozilla/5.0 (Planificador)"


def _leer_url(url, timeout=60, agente=AGENTE):
    """Descarga texto probando varias vías: requests (con certifi), urllib normal y urllib con certifi.
    Así funciona aunque el almacén de certificados de Windows o el proxy den problemas."""
    errores = []
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": agente} if agente else {}, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        errores.append(f"requests: {e!r}")
    req = urllib.request.Request(url, headers={"User-Agent": agente} if agente else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        errores.append(f"urllib: {e!r}")
    try:
        import ssl
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        errores.append(f"urllib+certifi: {e!r}")
    raise RuntimeError(" | ".join(errores))


def _cache_valida(ruta, horas):
    return os.path.exists(ruta) and (time.time() - os.path.getmtime(ruta)) < horas * 3600


def _fin_mes(serie_o_df):
    try:
        return serie_o_df.resample("ME")
    except ValueError:                      # pandas antiguo
        return serie_o_df.resample("M")


def ecb_ultimo(flow, clave):
    """Último dato publicado de una serie del BCE (petición diminuta). Devuelve (valor en tanto por uno, fecha)."""
    url = (f"https://data-api.ecb.europa.eu/service/data/{flow}/{clave}"
           "?format=csvdata&lastNObservations=1&detail=dataonly")
    df = pd.read_csv(io.StringIO(_leer_url(url, 30)))
    return float(df["OBS_VALUE"].iloc[-1]) / 100, pd.to_datetime(str(df["TIME_PERIOD"].iloc[-1]))


def tipos_actuales(forzar=False):
    """Euribor 12m y bono euro a 10 años (AAA, BCE) más recientes. Cada uno falla por separado.
    Devuelve (dict, dict de errores)."""
    ruta = os.path.join(CSV_DIR, "tipos_actuales.json")
    cache = _leer_json(ruta, {})
    out, errs = {"euribor12m": None, "bono10": None}, {}
    fuentes = {"euribor12m": ("FM", "M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA"),
               "bono10": ("YC", "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y")}
    hoy = datetime.now().strftime("%Y-%m-%d")
    for k, (flow, clave) in fuentes.items():
        c = cache.get(k)
        if c and c.get("dia") == hoy and not forzar:
            out[k], out[f"fecha_{k}"] = c["valor"], c["fecha"]
            continue
        try:
            v, f = ecb_ultimo(flow, clave)
            out[k], out[f"fecha_{k}"] = v, f.strftime("%Y-%m-%d")
            cache[k] = {"dia": hoy, "valor": v, "fecha": out[f"fecha_{k}"]}
        except Exception as e:
            registrar_error(f"BCE {k}", e)
            errs[k] = str(e)[:400]
            if c:                               # último valor conocido, aunque sea de otro día
                out[k], out[f"fecha_{k}"] = c["valor"], c["fecha"]
    try:
        os.makedirs(CSV_DIR, exist_ok=True)
        _escribir_json(ruta, cache)
    except Exception as e:
        registrar_error("Guardar tipos_actuales.json", e)
    return out, errs


def curva_bce(forzar=False):
    """Curva de tipos al contado del euro (bonos AAA de la zona euro, BCE). DataFrame mensual:
    índice = fin de mes, columnas = vencimiento en años (1..25), valores en tanto por uno.
    Solo se descarga cuando un modo de renta fija la necesita (son ~6 MB la primera vez)."""
    os.makedirs(CSV_DIR, exist_ok=True)
    ruta = os.path.join(CSV_DIR, "bce_curva_euro.csv")
    if not forzar and _cache_valida(ruta, 24 * 7):
        return pd.read_csv(ruta, index_col=0, parse_dates=True).rename(columns=int)
    try:
        venc = "+".join(f"SR_{m}Y" for m in range(1, 26))
        url = ("https://data-api.ecb.europa.eu/service/data/YC/"
               f"B.U2.EUR.4F.G_N_A.SV_C_YM.{venc}?format=csvdata&startPeriod=2004-09-06&detail=dataonly")
        df = pd.read_csv(io.StringIO(_leer_url(url, 300)))
        df["venc"] = df["KEY"].str.extract(r"SR_(\d+)Y")[0].astype(int)
        df["fecha"] = pd.to_datetime(df["TIME_PERIOD"])
        piv = df.pivot_table(index="fecha", columns="venc", values="OBS_VALUE") / 100
        mensual = _fin_mes(piv).last().dropna(how="all")
        mensual.to_csv(ruta)
        return mensual
    except Exception as e:
        registrar_error("BCE curva", e)
        if os.path.exists(ruta):
            return pd.read_csv(ruta, index_col=0, parse_dates=True).rename(columns=int)
        raise


# Índices de renta variable. Todos en dólares y con dividendos reinvertidos, SIN convertir a euros.
# Cada índice es una lista de tramos (símbolo de Yahoo, primer año que se usa de ese símbolo, dividendo a sumar).
# El MSCI World de Yahoo (^990100-USD-STRD) es de PRECIO, sin dividendos: Yahoo no publica la versión «net return».
# Se le suma una rentabilidad por dividendo neta media aproximada (MSCI World 1972-2008: ~3,5-4 % en los 70,
# ~3 % en los 80 y ~2 % de 1995 a 2008 → ~2,75 % neta de retenciones de media). VT, VTSMX y ^SP500TR ya
# incluyen los dividendos (precio ajustado / índice total return).
DIV_MSCI_WORLD = 0.0275
INDICES = {
    "Mundo largo: MSCI World hasta 2008 + Vanguard Total World (VT)":
        {"tramos": [("^990100-USD-STRD", 1972, DIV_MSCI_WORLD), ("VT", 2009, 0.0)], "desde": 1973},
    "Vanguard Total World (VT)": {"tramos": [("VT", 2009, 0.0)], "desde": 2009},
    "Vanguard Total Stock Market EE.UU. (VTSMX)": {"tramos": [("VTSMX", 1993, 0.0)], "desde": 1993},
    "S&P 500 con dividendos": {"tramos": [("^SP500TR", 1988, 0.0)], "desde": 1989},
}
INDICE_DEFECTO = next(iter(INDICES))


def _descargar_yahoo(simbolo):
    import yfinance as yf
    for intento in range(3):
        try:
            px = yf.download(simbolo, period="max", interval="1d", auto_adjust=True, progress=False)["Close"]
            if isinstance(px, pd.DataFrame):
                px = px.iloc[:, 0]
            px = px.dropna()
            if len(px):
                return px
        except Exception:
            if intento == 2:
                raise
        time.sleep(2 * (intento + 1))
    raise RuntimeError(f"Yahoo Finance no devuelve datos de {simbolo}")


CACHE_VERSION = "v2"     # súbelo si cambia cómo se construyen los índices (invalida las cachés viejas)


def indice_nivel(nombre, freq="M", forzar=False, real=False):
    """Nivel (base 100) del índice elegido, encadenando tramos si hace falta.
    freq: 'M' = fin de mes, 'W' = viernes de cada semana. real=True: deflactado con el IPC de EE.UU.
    (la caché en disco siempre guarda la serie nominal)."""
    nivel = _indice_nominal(nombre, freq, forzar)
    return deflactar(nivel, ipc_eeuu()) if real else nivel


def _indice_nominal(nombre, freq="M", forzar=False):
    os.makedirs(CSV_DIR, exist_ok=True)
    clave = re.sub(r"[^a-z0-9]+", "_", nombre.lower())[:40]
    ruta = os.path.join(CSV_DIR, f"indice_{'sem_' if freq == 'W' else ''}{clave}_{CACHE_VERSION}.csv")
    if not forzar and _cache_valida(ruta, 24):
        return pd.read_csv(ruta, index_col=0, parse_dates=True)["nivel"]
    try:
        tramos = INDICES[nombre]["tramos"]
        pasos = 52 if freq == "W" else 12
        rets = []
        for i, (simbolo, desde, div) in enumerate(tramos):
            px = _descargar_yahoo(simbolo)
            px.index = pd.to_datetime(px.index).tz_localize(None)
            serie = (px.resample("W-FRI").last() if freq == "W" else _fin_mes(px).last()).dropna()
            r = serie.pct_change()
            if div:                                   # índice de precio: se suman los dividendos
                r = (1 + r) * (1 + div) ** (1 / pasos) - 1
            hasta = tramos[i + 1][1] if i + 1 < len(tramos) else 9999
            rets.append(r[(r.index.year >= desde - (1 if i == 0 else 0)) & (r.index.year < hasta)])
        r = pd.concat(rets).dropna()
        nivel = (1 + r).cumprod() * 100
        nivel.name = "nivel"
        nivel.to_frame().to_csv(ruta)
        return nivel
    except Exception as e:
        registrar_error(f"Yahoo {nombre} ({freq})", e)
        if os.path.exists(ruta):
            return pd.read_csv(ruta, index_col=0, parse_dates=True)["nivel"]
        raise


def indice_mensual(nombre, forzar=False, real=False):
    return indice_nivel(nombre, "M", forzar, real)


def indice_semanal(nombre, forzar=False, real=False):
    return indice_nivel(nombre, "W", forzar, real)


def indice_anual(nombre, forzar=False, real=False):
    """Rentabilidades anuales (diciembre a diciembre) del índice. Descarta el año en curso."""
    nivel = indice_mensual(nombre, forzar, real)
    fin_anio = nivel.groupby(nivel.index.year).last()
    ret = fin_anio.pct_change().dropna()
    hoy = datetime.now()
    if ret.index.max() >= hoy.year and hoy.month < 12:
        ret = ret[ret.index < hoy.year]
    desde = INDICES[nombre]["desde"]
    ret = ret[ret.index >= desde]
    ret.name = "ret"
    ret.index.name = "anio"
    return ret


# =====================================================================  INFLACIÓN
INFLACION_EURO_DEFECTO = 0.02      # objetivo del BCE: inflación esperada para la renta fija a tipo constante


def _serie_mensual_cache(nombre_csv, descargar, forzar=False, dias=7):
    """Serie mensual (índice = primer día del mes) con caché en csv/ y respaldo a la última copia."""
    ruta = os.path.join(CSV_DIR, nombre_csv)
    if not forzar and _cache_valida(ruta, 24 * dias):
        return pd.read_csv(ruta, index_col=0, parse_dates=True).iloc[:, 0]
    try:
        s = descargar().dropna().sort_index()
        if s.empty:
            raise RuntimeError(f"{nombre_csv}: serie vacía")
        os.makedirs(CSV_DIR, exist_ok=True)
        s.rename("valor").to_frame().to_csv(ruta)
        return s
    except Exception as e:
        registrar_error(f"Inflación {nombre_csv}", e)
        if os.path.exists(ruta):
            return pd.read_csv(ruta, index_col=0, parse_dates=True).iloc[:, 0]
        raise


def ipc_eeuu(forzar=False):
    """IPC de EE.UU. (CPI-U, todos los artículos, sin desestacionalizar; FRED CPIAUCNS), mensual desde 1913."""
    def bajar():
        # FRED corta las peticiones con agentes inventados: se usa el de la librería (agente=None)
        txt = _leer_url("https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS", 60, agente=None)
        df = pd.read_csv(io.StringIO(txt))
        return pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
                         index=pd.to_datetime(df.iloc[:, 0]), name="valor")
    return _serie_mensual_cache("ipc_eeuu.csv", bajar, forzar)


def hicp_euro(forzar=False):
    """Índice de precios armonizado de la zona euro (HICP, BCE ICP.M.U2.N.000000.4.INX), mensual desde 1996."""
    def bajar():
        url = ("https://data-api.ecb.europa.eu/service/data/ICP/M.U2.N.000000.4.INX"
               "?format=csvdata&detail=dataonly")
        df = pd.read_csv(io.StringIO(_leer_url(url, 60)))
        return pd.Series(df["OBS_VALUE"].astype(float).values, index=pd.to_datetime(df["TIME_PERIOD"]),
                         name="valor")
    return _serie_mensual_cache("hicp_euro.csv", bajar, forzar)


def deflactar(nivel, ipc):
    """Pasa una serie de niveles a términos reales: divide por el IPC del mes de cada fecha (los meses que aún no
    se han publicado usan el último dato) y vuelve a base 100."""
    ipc_m = pd.Series(np.asarray(ipc, dtype=float), index=pd.DatetimeIndex(ipc.index).to_period("M"))
    ipc_m = ipc_m[~ipc_m.index.duplicated(keep="last")]
    periodos = pd.DatetimeIndex(nivel.index).to_period("M")
    rango = pd.period_range(min(ipc_m.index.min(), periodos.min()), max(ipc_m.index.max(), periodos.max()), freq="M")
    p = ipc_m.reindex(rango).ffill().bfill().reindex(periodos).values
    real = np.asarray(nivel, dtype=float) / p
    return pd.Series(real / real[0] * 100, index=nivel.index, name=nivel.name)


def inflacion_anual(ipc):
    """Inflación diciembre a diciembre por año (Series índice = año). El año en curso no se incluye."""
    s = pd.Series(np.asarray(ipc, dtype=float), index=pd.DatetimeIndex(ipc.index))
    dic = s[s.index.month == 12]
    inf = dic.pct_change().dropna()
    inf.index = inf.index.year
    inf.index.name = "anio"
    return inf


def tasa_real(nominal, inflacion):
    """Rentabilidad real (Fisher exacta): (1 + nominal) / (1 + inflación) − 1."""
    return (1 + nominal) / (1 + inflacion) - 1


# =====================================================================  SIMULACIÓN DE CARTERA
MODOS_RF = ["Tipo constante", "Histórico (carry 10 años)", "Vencimiento objetivo"]


def _frac(m):
    """Fracción del año que cada aportación pasa invertida. Anual (m=1): 1. Mensual (m=12): 1, 11/12, ..., 1/12."""
    return np.array([(m - j) / m for j in range(m)])


def trayectoria_mc(R, r_rf, w_rv, inicial, aporte, m=1):
    """R: (N, H) rentabilidades anuales de renta variable; r_rf: escalar, (H,) o (N, H).
    Capital inicial el día 1 y `aporte` al año repartido en m aportaciones iguales (m=1 anual, m=12 mensual).
    Sin rebalanceo: cada aportación se reparte según w_rv y después crece por su cuenta.
    Devuelve (N, H) con el valor de la cartera al final de cada año."""
    N, H = R.shape
    r_rf = np.broadcast_to(np.asarray(r_rf, dtype=float), (N, H)) if np.ndim(r_rf) else np.full((N, H), r_rf)
    fr = _frac(m)
    rv = np.zeros(N)
    rf = np.zeros(N)
    out = np.zeros((N, H))
    for k in range(H):
        gr, gf = 1 + R[:, k], 1 + r_rf[:, k]
        ini = inicial if k == 0 else 0.0
        rv = rv * gr + w_rv * (ini * gr + (aporte / m) * (gr[:, None] ** fr).sum(1))
        rf = rf * gf + (1 - w_rv) * (ini * gf + (aporte / m) * (gf[:, None] ** fr).sum(1))
        out[:, k] = rv + rf
    return out


BLOQUE_DEFECTO = 5     # años seguidos por bloque en el Monte Carlo


def muestras_bloques(ret_hist, n, H, bloque=BLOQUE_DEFECTO, semilla=7):
    """Block bootstrap circular: en vez de sortear años sueltos se sortean tramos de `bloque` años SEGUIDOS del
    histórico (dando la vuelta al final), así se conserva que a un año malo le suele seguir otro malo o un rebote.
    bloque=1 es el bootstrap clásico de años independientes. Devuelve (n, H)."""
    r = np.asarray(ret_hist, dtype=float)
    L = len(r)
    b = int(max(1, min(bloque, L)))
    nb = -(-H // b)                                   # bloques necesarios (redondeo hacia arriba)
    rng = np.random.default_rng(semilla)
    inicios = rng.integers(0, L, size=(n, nb))
    idx = (inicios[:, :, None] + np.arange(b)) % L
    return r[idx.reshape(n, nb * b)[:, :H]]


def montecarlo(ret_hist, H, w_rv, r_rf, inicial, aporte, n=5000, semilla=7, m=1, bloque=BLOQUE_DEFECTO):
    """Monte Carlo con block bootstrap del histórico de rentabilidades anuales. Renta fija a tipo constante."""
    R = muestras_bloques(ret_hist, n, H, bloque, semilla)
    return trayectoria_mc(R, r_rf, w_rv, inicial, aporte, m)


def ventanas_historicas(ret_rv, curva, H, w_rv, modo, inicial, aporte, r_const=0.03, m=1, infl_rf=None):
    """Una simulación por cada año de inicio posible usando los años reales.
    modo: 'Tipo constante' | 'Histórico (carry 10 años)' | 'Vencimiento objetivo'.
    infl_rf: inflación anual de la zona euro por año (Series). Si se pasa, la renta fija de los modos históricos
    se pasa a términos reales con la inflación de cada año (y se descartan los años sin dato).
    Devuelve (DataFrame trayectorias [ventana x año], lista de años de inicio)."""
    fr = _frac(m)
    # rendimiento del bono: tipo vigente a 31-dic del año anterior (el que se pudo comprar el 1 de enero)
    y_ini = curva.groupby(curva.index.year).last() if curva is not None else None
    inicios, trays = [], []
    for s in sorted(ret_rv.index):
        anios = range(s, s + H)
        if any(a not in ret_rv.index for a in anios):
            continue
        if modo != "Tipo constante" and any((a - 1) not in y_ini.index for a in anios):
            continue
        if modo != "Tipo constante" and infl_rf is not None and any(a not in infl_rf.index for a in anios):
            continue
        pi = [float(infl_rf[s + k]) if (infl_rf is not None and modo != "Tipo constante") else 0.0
              for k in range(H)]

        def recursion(tasas, peso):
            v, out = 0.0, np.zeros(H)
            for k in range(H):
                g = 1 + tasas[k]
                ini = inicial if k == 0 else 0.0
                v = v * g + peso * (ini * g + (aporte / m) * np.sum(g ** fr))
                out[k] = v
            return out

        rv_val = recursion([ret_rv[s + k] for k in range(H)], w_rv)      # parte de renta variable
        if modo == "Tipo constante":
            rf_val = recursion([r_const] * H, 1 - w_rv)
        elif modo == "Histórico (carry 10 años)":
            rf_val = recursion([tasa_real(y_ini.loc[s + k - 1, 10], pi[k]) for k in range(H)], 1 - w_rv)
        else:                                  # vencimiento objetivo: compra a (H-k) años y mantiene hasta el final
            rf_val = np.zeros(H)
            for k in range(H):
                y = y_ini.loc[s + k - 1, int(min(H - k, 25))]
                g = np.array([(1 + y) / (1 + pi[j]) for j in range(H)])     # crecimiento real de cada año
                ini = inicial if k == 0 else 0.0
                for t in range(k, H):
                    resto = float(np.prod(g[k + 1:t + 1]))
                    rf_val[t] += (1 - w_rv) * (ini * g[k] * resto + (aporte / m) * np.sum(g[k] ** fr) * resto)
        total = rv_val + rf_val
        if not np.all(np.isfinite(total)):          # faltan tipos de ese vencimiento en esos años
            continue
        trays.append(total)
        inicios.append(s)
    if not trays:
        return pd.DataFrame(), []
    return pd.DataFrame(trays, index=inicios, columns=range(1, H + 1)), inicios


def resumen_trayectorias(tray, aportado, inicial, aporte, H, m=1):
    """Estadísticas del valor final de una tabla [simulación x año]."""
    final = np.asarray(tray)[:, -1]
    p = np.percentile(final, [5, 25, 50, 75, 95])
    return {
        "p5": p[0], "p25": p[1], "mediana": p[2], "p75": p[3], "p95": p[4],
        "minimo": float(final.min()), "maximo": float(final.max()),
        "prob_perdida": float(np.mean(final < aportado)),
        "multiplo_mediana": float(p[2] / aportado) if aportado else float("nan"),
        "tir_mediana": tir_anual(inicial, aporte, H, p[2], m),
    }


def tir_anual(inicial, aporte, H, final, m=1):
    """Rentabilidad anual equivalente (TIR) de un resultado final dado."""
    tiempos = [0.0] + [k + j / m for k in range(H) for j in range(m)]
    importes = [inicial] + [aporte / m] * (H * m)
    if final <= 0 or sum(importes) <= 0:
        return float("nan")

    def vf(r):
        return sum(a * (1 + r) ** (H - t) for t, a in zip(tiempos, importes))
    lo, hi = -0.9, 1.0
    if vf(lo) > final or vf(hi) < final:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        if vf(mid) < final:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def ventanas_moviles(nivel, horizontes, w_rv, r_rf, pasos_por_anio=12, min_ventanas=None):
    """Ventanas móviles que se solapan. `nivel` es una serie de niveles del índice con `pasos_por_anio` puntos al año
    (1 = niveles de fin de año, con el nivel inicial incluido: N años dan N+1 puntos y N−h+1 ventanas de h años;
    12 = niveles de fin de mes). Para cada horizonte h (años) mira TODAS las ventanas de h años y calcula, para una cartera invertida de golpe el primer
    día (sin rebalanceo) con w_rv en bolsa y el resto en renta fija a r_rf constante:
    probabilidad de perder dinero (acabar por debajo de lo invertido) y rentabilidad anual de las ventanas."""
    v = np.asarray(nivel, dtype=float)
    min_ventanas = min_ventanas or (12 if pasos_por_anio > 1 else 3)
    filas = []
    for h in horizontes:
        k = pasos_por_anio * h
        if len(v) - k < min_ventanas:       # muy pocas ventanas para decir nada
            continue
        rv = v[k:] / v[:-k]                  # múltiplo del índice en cada ventana
        port = w_rv * rv + (1 - w_rv) * (1 + r_rf) ** h
        anual = port ** (1 / h) - 1
        q = np.percentile(anual, [5, 25, 50, 75, 95])
        filas.append({"anios": h, "ventanas": len(port), "independientes": ventanas_independientes(len(v), k),
                      "prob_perder": float(np.mean(port < 1)),
                      "prob_perder_bolsa": float(np.mean(rv < 1)), "peor": float(anual.min()),
                      "p5": q[0], "p25": q[1], "mediana": q[2], "p75": q[3], "p95": q[4],
                      "mejor": float(anual.max())})
    return pd.DataFrame(filas)


def ventanas_independientes(n_puntos, pasos):
    """Ventanas que NO se solapan entre sí: (puntos − 1) // pasos. Las ventanas solapadas comparten casi todos sus
    datos, así que esta cifra es la que dice cuánta información independiente hay detrás de una probabilidad."""
    return max(int((n_puntos - 1) // max(pasos, 1)), 0)


def prob_perder_semanal(v, pesos, r_rf, max_semanas=1560, ma=52, min_ventanas=52, estrategia="hold"):
    """Probabilidad de perder dinero según el plazo en SEMANAS (1, 2, 3 … max_semanas), con ventanas que empiezan
    cada semana y se solapan, para cada reparto de `pesos` (fracción en bolsa; el resto, renta fija a r_rf).
    Inversión de golpe el primer día, sin rebalanceo. Devuelve (sin_suavizar, suavizada): DataFrames con índice =
    plazo en semanas y una columna por reparto. La suavizada es la media móvil centrada de `ma` plazos consecutivos
    y solo contiene los puntos con `ma` plazos completos (se descartan los extremos).
    estrategia='hold': todo el dinero el primer día (buy and hold).
    estrategia='dca': el mismo dinero repartido en aportaciones iguales al inicio de cada semana del plazo."""
    v = np.asarray(v, dtype=float)
    n = len(v)
    horizontes = [h for h in range(1, max_semanas + 1) if n - h >= min_ventanas]
    g = (1 + r_rf) ** (1 / 52)                  # crecimiento semanal de la renta fija
    suma_inv = np.concatenate([[0.0], np.cumsum(1.0 / v)])
    datos = {w: np.empty(len(horizontes)) for w in pesos}
    for i, h in enumerate(horizontes):
        if estrategia == "dca":
            # cada semana j se compra 1/h y se mantiene hasta el final: Σ_j (1/h)·v[fin]/v[j]
            rv = v[h:] * (suma_inv[h:n] - suma_inv[:n - h]) / h
            rf = (h if abs(g - 1) < 1e-12 else g * (g ** h - 1) / (g - 1)) / h
        else:
            rv = v[h:] / v[:-h]
            rf = (1 + r_rf) ** (h / 52)
        for w in pesos:
            datos[w][i] = np.mean(w * rv + (1 - w) * rf < 1)
    raw = pd.DataFrame(datos, index=pd.Index(horizontes, name="semanas"))
    suav = raw.rolling(ma, center=True, min_periods=ma).mean().dropna(how="all")
    return raw, suav


def semanas_para_riesgo(serie, maximo):
    """Menor plazo (semanas) a partir del cual la serie (prob. de perder suavizada) se queda siempre ≤ maximo."""
    s = serie.dropna()
    ok = (s <= maximo).values
    for i in range(len(ok)):
        if ok[i:].all():
            return int(s.index[i])
    return None


def anios_para_riesgo(df, columna, maximo):
    """Menor horizonte a partir del cual la probabilidad de perder se queda siempre ≤ maximo (o None)."""
    ok = (df[columna] <= maximo).values
    for i in range(len(ok)):
        if ok[i:].all():
            return int(df["anios"].iloc[i])
    return None


def riesgo_referencia(ret_rv, w_rv, r_rf):
    """Cartera de referencia con rebalanceo anual: rentabilidad media, volatilidad y peor año históricos."""
    r = w_rv * np.asarray(ret_rv, dtype=float) + (1 - w_rv) * r_rf
    return {"media": float(r.mean()), "vol": float(r.std(ddof=1)), "peor": float(r.min()),
            "mejor": float(r.max())}


def frontera(ret_rv, r_rf, H, inicial, aporte, n=3000, paso=10, m=1, bloque=BLOQUE_DEFECTO):
    """Tabla riesgo/rentabilidad para renta variable 0-100 %: sirve para ver el efecto del reparto."""
    filas = []
    aportado = inicial + aporte * H
    for w in range(0, 101, paso):
        t = montecarlo(ret_rv, H, w / 100, r_rf, inicial, aporte, n=n, m=m, bloque=bloque)
        s = resumen_trayectorias(t, aportado, inicial, aporte, H, m)
        ref = riesgo_referencia(ret_rv, w / 100, r_rf)
        filas.append({"% renta variable": w, "Vol. anual": ref["vol"], "Peor año": ref["peor"],
                      "Mediana final": s["mediana"], "P5 final": s["p5"], "Prob. pérdida": s["prob_perdida"],
                      "TIR mediana": s["tir_mediana"]})
    return pd.DataFrame(filas)


# =====================================================================  AHORRADOR
def r_mensual(nominal, inflacion=0.0, real=True):
    """Rentabilidad mensual equivalente. Con real=True descuenta la inflación (todo en euros de hoy)."""
    anual = (1 + nominal) / (1 + inflacion) - 1 if real else nominal
    return (1 + anual) ** (1 / 12) - 1


def capital_para_renta(d, meses, r_m, pesos=None):
    """Capital que hace falta para retirar `d` al mes durante `meses` (retirada a principio de mes).
    Si se pasa `pesos` (probabilidad de seguir vivo cada mes), cada retirada se pondera por ella."""
    if meses <= 0 or d <= 0:
        return 0.0
    if pesos is not None:
        w = np.asarray(pesos, dtype=float)[:meses]
        return float(d * np.sum(w * (1 + r_m) ** -np.arange(len(w))))
    if abs(r_m) < 1e-12:
        return d * meses
    return d * (1 - (1 + r_m) ** -meses) / r_m * (1 + r_m)


def factor_aportaciones(N, r_m, g=0.0):
    """Valor final de aportar 1 € al mes (a principio de mes) durante N meses, con la aportación subiendo un
    porcentaje `g` cada año. El capital final es: aportación inicial × este factor."""
    t = np.arange(N)
    return float(np.sum((1 + g) ** (t // 12) * (1 + r_m) ** (N - t)))


def trayectoria(ahorro0, aporte, N, n_ret, retirada, r_pre, r_post, g=0.0):
    """Saldo (euros de hoy) al final de cada mes: N meses ahorrando y luego n_ret meses retirando `retirada`."""
    saldo = [float(ahorro0)]
    b = float(ahorro0)
    for t in range(N):
        b = (b + aporte * (1 + g) ** (t // 12)) * (1 + r_pre)
        saldo.append(b)
    ret = np.broadcast_to(np.asarray(retirada, dtype=float), (n_ret,)) if n_ret > 0 else []
    for k in range(n_ret):
        b = max((b - ret[k]) * (1 + r_post), 0.0)
        saldo.append(b)
    return np.array(saldo)


def plan_jubilacion(edad, edad_ret, edad_fin, gasto_mes, pension, ahorro0, aporte_actual,
                    rent_pre, rent_post, inflacion, g=0.0, pesos=None):
    """Todo en euros de hoy. Devuelve capital necesario, aportación mensual necesaria y qué pasa con la actual.
    `pesos`: probabilidad mensual de seguir vivo desde la jubilación (None = vivir hasta `edad_fin` seguro)."""
    N, n_ret = int(round((edad_ret - edad) * 12)), int(round((edad_fin - edad_ret) * 12))
    r_pre, r_post = r_mensual(rent_pre, inflacion), r_mensual(rent_post, inflacion)
    necesidad = max(gasto_mes - pension, 0.0)
    K = capital_para_renta(necesidad, n_ret, r_post, pesos)
    fac = factor_aportaciones(N, r_pre, g)
    crece = ahorro0 * (1 + r_pre) ** N
    P = max((K - crece) / fac, 0.0) if fac > 0 else float("nan")
    cap_actual = crece + aporte_actual * fac
    unidad = capital_para_renta(1.0, n_ret, r_post, pesos)
    return {"N": N, "n_ret": n_ret, "necesidad": necesidad, "capital": K, "aporte": P,
            "crece_ahorro": crece, "capital_actual": cap_actual,
            "renta_actual": cap_actual / unidad if unidad else float("nan"),
            "r_pre": r_pre, "r_post": r_post, "factor": fac}


# --- mortalidad (INE, tablas de mortalidad de España)
EDAD_MAX_TABLA = 110


def _descargar_ine_mortalidad():
    """Riesgo de muerte q(x) por edad (0..100) y sexo, último año disponible. Tabla INE 27153 (por 1.000)."""
    import json
    txt = _leer_url("https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/27153?nult=1", timeout=90)
    filas = []
    for serie in json.loads(txt):
        n = serie["Nombre"]
        if ". Riesgo de muerte." not in n or not serie.get("Data"):
            continue
        partes = n.split(". ")
        sexo = {"Hombres": "H", "Mujeres": "M", "Total": "T"}.get(partes[1])
        m = re.match(r"(\d+)", partes[2])
        if sexo and m:
            d = serie["Data"][-1]
            filas.append({"sexo": sexo, "edad": int(m.group(1)), "qx": float(d["Valor"]) / 1000.0,
                          "anio": d.get("Anyo")})
    df = pd.DataFrame(filas).sort_values(["sexo", "edad"])
    if df.empty:
        raise RuntimeError("El INE no devolvió la tabla de mortalidad")
    return df


def tabla_mortalidad(forzar=False):
    """DataFrame sexo/edad/qx/anio con caché en csv/mortalidad_ine.csv."""
    ruta = os.path.join(CSV_DIR, "mortalidad_ine.csv")
    if not forzar and os.path.exists(ruta):
        try:
            return pd.read_csv(ruta)
        except Exception as e:
            registrar_error("Leer mortalidad_ine.csv", e)
    try:
        df = _descargar_ine_mortalidad()
        os.makedirs(CSV_DIR, exist_ok=True)
        df.to_csv(ruta, index=False)
        return df
    except Exception as e:
        registrar_error("Mortalidad INE", e)
        if os.path.exists(ruta):
            return pd.read_csv(ruta)
        raise


def qx_por_edad(df, sexo="T"):
    """Array q[0..EDAD_MAX_TABLA]: el INE agrupa 100 y más (q=1), así que de 100 a 110 se extrapola con el
    ritmo de crecimiento de las edades previas y se fuerza q=1 a la edad máxima."""
    t = df[df["sexo"] == sexo].set_index("edad")["qx"]
    q = np.ones(EDAD_MAX_TABLA + 1)
    for a in range(0, 100):
        q[a] = float(t.get(a, 1.0))
    ratio = min(max(q[99] / q[98], 1.0), 1.25) if q[98] > 0 else 1.15
    for a in range(100, EDAD_MAX_TABLA):
        q[a] = min(q[a - 1] * ratio, 0.999)
    q[EDAD_MAX_TABLA] = 1.0
    return q


def pesos_supervivencia(edad_ret, q, edad_max=EDAD_MAX_TABLA):
    """Probabilidad de seguir vivo cada mes desde la jubilación (=1 el primer mes, sabiendo que se llega vivo),
    hasta `edad_max`. Dentro de cada año la supervivencia se interpola de forma exponencial."""
    n = int(round((edad_max - edad_ret) * 12))
    if n <= 0:
        return np.array([])
    p = 1.0
    edad0 = int(np.floor(edad_ret))
    frac0 = edad_ret - edad0
    w = np.empty(n)
    for k in range(n):
        if k > 0:   # el mes k-1 ya se ha vivido: se aplica la mortalidad de esa edad
            a = min(edad0 + int((frac0 * 12 + k - 1) // 12), EDAD_MAX_TABLA)
            p *= (1 - min(q[a], 1.0)) ** (1 / 12)
        w[k] = p
    return w


def edad_prudente(edad_ret, q, umbral=0.10):
    """Edad a la que la probabilidad de seguir vivo (sabiendo que se llega a `edad_ret`) baja de `umbral`.
    Planificar hasta esa edad cubre el riesgo de vivir más de lo esperado en 9 de cada 10 casos."""
    w = pesos_supervivencia(edad_ret, q)
    debajo = np.nonzero(w < umbral)[0]
    k = int(debajo[0]) if debajo.size else len(w)
    return edad_ret + k / 12


def esperanza_vida(edad_ret, q):
    """Años esperados de vida restantes a partir de la jubilación."""
    w = pesos_supervivencia(edad_ret, q)
    return float(w.sum() / 12)


# --- meta de ahorro
def meses_para_meta(objetivo, ahorro0, aporte, i_m):
    """Meses (enteros) hasta llegar a `objetivo` ahorrando `aporte` al mes (a principio de mes) con rentabilidad
    mensual i_m. 0 si ya se alcanza; None si no se alcanzará nunca."""
    if ahorro0 >= objetivo:
        return 0
    if abs(i_m) < 1e-12:
        return int(math.ceil((objetivo - ahorro0) / aporte)) if aporte > 0 else None
    k = aporte * (1 + i_m) / i_m
    if i_m < 0 and aporte <= 0:
        return None
    num_, den = objetivo + k, ahorro0 + k
    if den <= 0 or num_ <= 0 or num_ / den <= 1:
        return None
    return int(math.ceil(math.log(num_ / den) / math.log(1 + i_m) - 1e-9))


def aporte_para_meta(objetivo, ahorro0, meses, i_m):
    """Aportación mensual necesaria para llegar a `objetivo` en `meses`."""
    if meses <= 0:
        return float("nan")
    if abs(i_m) < 1e-12:
        return max((objetivo - ahorro0) / meses, 0.0)
    cre = (1 + i_m) ** meses
    return max((objetivo - ahorro0 * cre) * i_m / ((1 + i_m) * (cre - 1)), 0.0)


def serie_ahorro(ahorro0, aporte, meses, i_m):
    """Evolución mensual: total acumulado, lo aportado (incluye el ahorro inicial) y los intereses."""
    saldo, filas = float(ahorro0), [(0, float(ahorro0), float(ahorro0), 0.0)]
    for m in range(1, meses + 1):
        saldo = (saldo + aporte) * (1 + i_m)
        aportado = ahorro0 + aporte * m
        filas.append((m, saldo, aportado, saldo - aportado))
    return pd.DataFrame(filas, columns=["mes", "total", "aportado", "intereses"])


# =====================================================================  TEST DE RIESGO (Grable y Lytton)
# Cada pregunta: (enunciado, [(texto, puntos), ...]). Adaptación al español y a euros.
TEST = [
    ("¿Cómo te describiría tu mejor amigo cuando se trata de asumir riesgos?",
     [("Un verdadero jugador", 4), ("Dispuesto a arriesgar tras informarse bien", 3), ("Prudente", 2),
      ("Alguien que evita el riesgo a toda costa", 1)]),
    ("Estás en un concurso de la tele y puedes elegir una opción. ¿Cuál?",
     [("1.000 € en efectivo seguros", 1), ("50 % de probabilidad de ganar 5.000 €", 2),
      ("25 % de probabilidad de ganar 10.000 €", 3), ("5 % de probabilidad de ganar 100.000 €", 4)]),
    ("Acabas de reunir el dinero para un viaje único en la vida y, tres semanas antes, te quedas sin trabajo. ¿Qué haces?",
     [("Cancelo el viaje", 1), ("Hago un viaje mucho más modesto", 2), ("Voy tal y como estaba previsto", 3),
      ("Lo alargo: puede que sea la única oportunidad", 4)]),
    ("Si recibieras de forma inesperada 20.000 € para invertir, ¿qué harías?",
     [("Depósito, cuenta remunerada o fondo monetario", 1), ("Bonos seguros de alta calidad o fondos de bonos", 2),
      ("Acciones o fondos de acciones", 3)]),
    ("¿Cómo de cómodo te sientes invirtiendo en acciones o fondos de acciones por tu experiencia?",
     [("Nada cómodo", 1), ("Algo cómodo", 2), ("Muy cómodo", 3)]),
    ("Cuando oyes la palabra «riesgo», ¿cuál es la primera palabra que te viene a la cabeza?",
     [("Pérdida", 1), ("Incertidumbre", 2), ("Oportunidad", 3), ("Emoción", 4)]),
    ("Casi todo tu patrimonio invertido está en bonos del Estado con buen interés. Algunos expertos prevén que "
     "oro, joyas, coleccionismo e inmuebles se revalorizarán y que los bonos podrían caer. ¿Qué harías?",
     [("Mantengo los bonos", 1), ("Vendo y paso la mitad a liquidez y la otra mitad a esos activos", 2),
      ("Vendo todo y lo paso a esos activos", 3),
      ("Vendo todo, lo paso a esos activos y pido dinero prestado para comprar más", 4)]),
    ("Según el mejor y el peor resultado posible de estas cuatro inversiones, ¿cuál preferirías?",
     [("Mejor caso +200 €, peor caso 0 €", 1), ("Mejor caso +800 €, peor caso −200 €", 2),
      ("Mejor caso +2.600 €, peor caso −800 €", 3), ("Mejor caso +4.800 €, peor caso −2.400 €", 4)]),
    ("Además de lo que ya tienes, te regalan 1.000 €. Ahora debes elegir:",
     [("Una ganancia segura de 500 €", 1), ("50 % de ganar 1.000 € y 50 % de no ganar nada", 3)]),
    ("Además de lo que ya tienes, te regalan 2.000 €. Ahora debes elegir:",
     [("Una pérdida segura de 500 €", 1), ("50 % de perder 1.000 € y 50 % de no perder nada", 3)]),
    ("Un familiar te deja 100.000 € de herencia con la condición de invertirlos TODOS en una sola de estas opciones:",
     [("Cuenta de ahorro o fondo monetario", 1), ("Un fondo mixto de acciones y bonos", 2),
      ("Una cartera de 15 acciones", 3), ("Materias primas como oro, plata y petróleo", 4)]),
    ("Si tuvieras que invertir 20.000 €, ¿qué reparto te resultaría más atractivo?",
     [("60 % riesgo bajo, 30 % medio, 10 % alto", 1), ("30 % bajo, 40 % medio, 30 % alto", 2),
      ("10 % bajo, 40 % medio, 50 % alto", 3)]),
    ("Un amigo geólogo de confianza organiza un grupo de inversores para una prospección minera. Si sale bien, "
     "devuelve entre 50 y 100 veces lo invertido; si no, se pierde todo. Calcula un 20 % de probabilidad de éxito. "
     "Si tuvieras el dinero, ¿cuánto pondrías?",
     [("Nada", 1), ("Un sueldo mensual", 2), ("Tres sueldos mensuales", 3), ("Seis sueldos mensuales", 4)]),
]

NIVELES = [  # (puntuación máxima inclusive, nivel, descripción, % renta variable orientativo)
    (18, "Bajo", "Muy conservador: prioriza no perder capital.", 15),
    (22, "Medio-bajo", "Prudente: acepta algo de riesgo a cambio de algo más de rentabilidad.", 35),
    (28, "Medio", "Equilibrado: tolera oscilaciones moderadas.", 55),
    (32, "Medio-alto", "Dinámico: acepta caídas relevantes a cambio de más rentabilidad esperada.", 75),
    (99, "Alto", "Agresivo: tolera fuertes caídas buscando la máxima rentabilidad.", 90),
]


def puntuacion_min_max():
    return sum(min(p for _, p in o) for _, o in TEST), sum(max(p for _, p in o) for _, o in TEST)


# --- asignador de cartera: puntuación del test -> % de renta variable ideal -> ajuste por horizonte
# Escala T (psicometría): media 50 y desviación 10. Con ±5 desviaciones cubre justo de 0 a 100.
# No hay normas publicadas (media/desviación) de la escala de Grable-Lytton en la web oficial; se deducen de los
# tramos oficiales: «normal» 23-28 (centro 25,5) y «bajo» ≤18 / «alto» ≥33 (a ±7 puntos del centro).
NORMA_TEST = (25.5, 6.0)


def t_score(puntos, media=NORMA_TEST[0], sd=NORMA_TEST[1]):
    return 50.0 + 10.0 * (puntos - media) / sd


def rv_ideal_desde_puntos(puntos, media=NORMA_TEST[0], sd=NORMA_TEST[1]):
    """Devuelve (fracción de renta variable ideal 0-1, nota T, percentil 0-1)."""
    z = (puntos - media) / sd
    t = 50.0 + 10.0 * z
    return float(np.clip(t, 0, 100)) / 100.0, t, 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _fila_plazo(suav, semanas):
    idx = suav.index.values
    k = int(np.abs(idx - min(max(semanas, idx.min()), idx.max())).argmin())
    return suav.iloc[k]


def prob_objetivo(suav, w_ideal, h_ref_anios, p_min=0.02):
    """Riesgo que se acepta: la probabilidad de perder del reparto ideal al horizonte de referencia (con un suelo)."""
    return max(float(_fila_plazo(suav, h_ref_anios * 52)[min(suav.columns, key=lambda c: abs(c - w_ideal))]), p_min)


def rv_recomendada(suav, w_ideal, anios, p_obj):
    """Mayor % de bolsa (≤ ideal) cuya probabilidad histórica de perder al plazo `anios` no supera `p_obj`."""
    fila = _fila_plazo(suav, anios * 52)
    ok = [c for c in fila.index if c <= w_ideal + 1e-9 and fila[c] <= p_obj + 1e-12]
    return float(max(ok)) if ok else 0.0


def mal_escenario(v, pesos, r_rf, anios, q=5):
    """TIR anualizada del percentil `q` (5 = «1 de cada 20 peor») de las ventanas semanales solapadas, para cada
    plazo de `anios` y cada reparto de `pesos` (fracción en bolsa; resto en renta fija a r_rf). Todo de golpe el
    primer día del tramo y sin rebalanceo. Devuelve un DataFrame (índice = años, columnas = pesos)."""
    v = np.asarray(v, dtype=float)
    datos = {w: [] for w in pesos}
    ok = []
    for y in anios:
        h = int(round(y * 52))
        if len(v) - h < 52:
            continue
        rv = v[h:] / v[:-h]
        rf = (1 + r_rf) ** y
        ok.append(y)
        for w in pesos:
            datos[w].append(float(np.percentile((w * rv + (1 - w) * rf) ** (1 / y) - 1, q)))
    return pd.DataFrame(datos, index=pd.Index(ok, name="anios"))


def prob_caida_mayor(v, w, r_rf, anios, umbral):
    """Probabilidad (ventanas semanales solapadas, todo de golpe) de acabar con menos de (1-umbral) de lo invertido."""
    v = np.asarray(v, dtype=float)
    out = []
    for y in anios:
        h = int(round(y * 52))
        if len(v) - h < 52:
            out.append(np.nan)
            continue
        val = w * (v[h:] / v[:-h]) + (1 - w) * (1 + r_rf) ** y
        out.append(float(np.mean(val < 1 - umbral)))
    return np.array(out)


def senda_mal_escenario(tabla, w_ideal, suelo, suavizado=2):
    """% de bolsa recomendado según los años que quedan: en cada tramo, la mayor bolsa (≤ ideal) cuyo mal escenario
    anualizado no baja de `suelo`. Se suaviza con una media móvil de ±`suavizado` puntos y nunca sube al acercarse
    el final."""
    cols = [c for c in tabla.columns if c <= w_ideal + 1e-9]
    rv = np.array([max([c for c in cols if tabla.loc[y, c] >= suelo], default=0.0) for y in tabla.index])
    k = 2 * suavizado + 1
    if suavizado > 0 and len(rv) > k:
        rv = np.convolve(np.pad(rv, (suavizado, suavizado), mode="edge"), np.ones(k) / k, mode="valid")
    rv = np.minimum(rv, w_ideal)
    rv = np.minimum.accumulate(rv[::-1])[::-1]
    return pd.DataFrame({"anios": tabla.index.values.astype(float), "rv": rv})


def mal_escenario_de(tabla, w, anios):
    """Mal escenario anualizado (de `tabla`) de una cartera con fracción `w` en bolsa a `anios` años vista."""
    y = tabla.index.values.astype(float)
    fila = tabla.iloc[int(np.abs(y - min(max(anios, y.min()), y.max())).argmin())]
    return float(np.interp(w, fila.index.values.astype(float), fila.values))


def matriz_rentabilidades(v, H, paso=1):
    """Rentabilidades brutas (1+r) de la bolsa año a año para cada ventana semanal solapada que empieza en
    cada semana del histórico (filas = ventanas, columnas = años 1..H)."""
    v = np.asarray(v, dtype=float)
    starts = np.arange(0, len(v) - H * 52, paso)
    if len(starts) == 0:
        raise ValueError("Histórico demasiado corto para ese horizonte")
    return np.column_stack([v[starts + (y + 1) * 52] / v[starts + y * 52] for y in range(H)])


def simular_dinamico(R, w_ideal, r_rf, tabla, suelo):
    """Simulación dinámica con la cartera que realmente se tiene. R: (trayectorias × H) de (1+r) anuales de la bolsa.
    Cada año se mira la cartera con la que se entra (el peso en bolsa se mueve con el mercado, sin rebalancear),
    se calcula su mal escenario con los años que quedan y, si está por debajo de `suelo`, se recorta a la mayor
    bolsa que sí lo cumple. Devuelve dict con valores finales (por 1 € invertido), pesos de cada año, nº de recortes."""
    n, H = R.shape
    g = 1.0 + r_rf
    cols = tabla.columns.values.astype(float)
    yrs = tabla.index.values.astype(float)
    S = np.full(n, float(w_ideal))
    B = 1.0 - S
    W = np.empty((n, H))
    ENT = np.empty((n, H))
    recortes = np.zeros(n)
    for y in range(H):
        rest = H - y
        fila = tabla.iloc[int(np.abs(yrs - min(max(rest, yrs.min()), yrs.max())).argmin())].values
        tot = S + B
        w = S / tot
        ENT[:, y] = w
        me = np.interp(w, cols, fila)
        ok = cols[(cols <= w_ideal + 1e-9) & (fila >= suelo)]
        wmax = float(ok.max()) if ok.size else 0.0
        corte = me < suelo
        w_new = np.where(corte, np.minimum(w, wmax), w)
        recortes += (corte & (w_new < w - 1e-9))
        W[:, y] = w_new
        S = tot * w_new * R[:, y]
        B = tot * (1.0 - w_new) * g
    return {"final": S + B, "pesos": W, "entrada": ENT, "recortes": recortes}


def simular_fijo(R, w, r_rf):
    """Buy and hold con un reparto fijo (sin rebalancear)."""
    H = R.shape[1]
    return w * np.prod(R, axis=1) + (1 - w) * (1.0 + r_rf) ** H


def simular_senda(R, pesos_anuales, r_rf):
    """Plan fijo: cada año se rebalancea a `pesos_anuales[y]` en bolsa."""
    g = 1.0 + r_rf
    v = np.ones(R.shape[0])
    for y, w in enumerate(pesos_anuales):
        v = v * (w * R[:, y] + (1 - w) * g)
    return v


def rv_en(senda, anios):
    return float(np.interp(anios, senda["anios"].values, senda["rv"].values))


def evaluar_test(puntos_por_pregunta):
    total = int(sum(puntos_por_pregunta))
    for tope, nivel, desc, rv in NIVELES:
        if total <= tope:
            return {"puntuacion": total, "nivel": nivel, "descripcion": desc, "rv_sugerida": rv}
    raise ValueError(total)


# ------------------------------------------------------------ perfiles guardados
def _leer_json(ruta, defecto):
    if not os.path.exists(ruta):
        return defecto
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:                      # fichero corrupto (p. ej. conflicto de OneDrive)
        registrar_error(f"Leer {os.path.basename(ruta)}", e)
        return defecto


def _escribir_json(ruta, obj):
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def leer_perfiles():
    d = _leer_json(PERFILES, {})
    d.setdefault("usuarios", {})
    return d


def guardar_perfil(usuario, resultado, respuestas):
    d = leer_perfiles()
    previo = d["usuarios"].get(usuario, {})
    hoy = datetime.now().strftime("%Y-%m-%d")
    historial = list(previo.get("historial") or ([{"fecha": previo["fecha"], "puntuacion": previo["puntuacion"]}]
                                                  if previo.get("fecha") else []))
    historial.append({"fecha": hoy, "puntuacion": resultado["puntuacion"]})
    d["usuarios"][usuario] = {**resultado, "respuestas": list(respuestas), "fecha": hoy, "historial": historial}
    d["activo"] = usuario
    _escribir_json(PERFILES, d)


def borrar_perfil(usuario):
    d = leer_perfiles()
    d["usuarios"].pop(usuario, None)
    if d.get("activo") == usuario:
        d["activo"] = next(iter(d["usuarios"]), None)
    _escribir_json(PERFILES, d)


def usuario_activo(nuevo=None):
    d = leer_perfiles()
    if nuevo is not None:
        d["activo"] = nuevo
        _escribir_json(PERFILES, d)
    return d.get("activo")


def leer_config():
    return _leer_json(CONFIG, {})


def guardar_config(**kw):
    c = leer_config()
    c.update(kw)
    _escribir_json(CONFIG, c)
