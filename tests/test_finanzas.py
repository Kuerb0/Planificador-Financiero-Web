"""Tests de finanzas.py con valores conocidos. Ejecutar desde la carpeta del programa:

    python -m pytest tests -q

No usan internet: las descargas se sustituyen por series inventadas.
"""
import math
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "py"))
import finanzas as fin  # noqa: E402


# ------------------------------------------------------------------ hipoteca
def test_cuota_valor_conocido():
    assert fin.cuota(150_000, 0.03, 360) == pytest.approx(632.41, abs=0.01)


def test_cuota_tipo_cero():
    assert fin.cuota(120_000, 0.0, 240) == pytest.approx(500.0)


def test_n_pagos_es_la_inversa_de_cuota():
    c = fin.cuota(200_000, 0.025, 300)
    assert fin.n_pagos(200_000, 0.025, c) == pytest.approx(300, abs=1e-6)


def test_cuadro_fijo_liquida_el_prestamo():
    d = fin.cuadro(150_000, 30, "Fijo", 0.03)
    assert len(d) == 360
    assert d["saldo"].iloc[-1] == pytest.approx(0, abs=0.01)
    assert d["amortizacion"].sum() == pytest.approx(150_000, abs=0.05)


def test_amortizar_acorta_el_plazo_y_reduce_intereses():
    base = fin.cuadro(150_000, 30, "Fijo", 0.03)
    extra = fin.cuadro(150_000, 30, "Fijo", 0.03, extra_anual=3_000, modo_extra="plazo")
    assert len(extra) < len(base)
    assert extra["intereses"].sum() < base["intereses"].sum()
    assert (extra["amortizacion"] + extra["extra"]).sum() == pytest.approx(150_000, abs=0.05)


def test_variable_nunca_por_debajo_de_cero():
    assert fin.tin_del_mes(0, "Variable", 0.03, 0.005, -0.02, 0.0, 5) == pytest.approx(0.0)


def test_tae_sin_gastos_es_el_tin_efectivo():
    d = fin.cuadro(150_000, 30, "Fijo", 0.03)
    assert fin.tae(150_000, d) == pytest.approx((1 + 0.03 / 12) ** 12 - 1, abs=1e-6)


def test_tae_sube_con_gastos_y_seguros():
    d = fin.cuadro(150_000, 30, "Fijo", 0.03)
    assert fin.tae(150_000, d, 2_000, 30) > fin.tae(150_000, d)


def test_gastos_compra_usada_y_nueva():
    usada = fin.gastos_compra(300_000, "Usada", itp=0.06)
    nueva = fin.gastos_compra(300_000, "Nueva", iva=0.10, ajd=0.0075)
    assert usada["ITP"] == pytest.approx(18_000)
    assert "ITP" not in nueva and nueva["IVA"] == pytest.approx(30_000) and nueva["AJD"] == pytest.approx(2_250)


# ------------------------------------------------------------------ inflación
def test_tasa_real_fisher():
    assert fin.tasa_real(0.05, 0.02) == pytest.approx(1.05 / 1.02 - 1)
    assert fin.tasa_real(0.02, 0.02) == pytest.approx(0.0)


def test_deflactar_con_ipc_constante_no_cambia_nada():
    idx = pd.date_range("2000-01-31", periods=24, freq="ME")
    nivel = pd.Series(np.linspace(100, 150, 24), index=idx)
    ipc = pd.Series(100.0, index=pd.date_range("2000-01-01", periods=24, freq="MS"))
    assert np.allclose(fin.deflactar(nivel, ipc).values, nivel.values)


def test_deflactar_quita_la_inflacion():
    idx = pd.date_range("2000-01-31", periods=13, freq="ME")
    nivel = pd.Series(100 * 1.10 ** (np.arange(13) / 12), index=idx)            # +10 % nominal al año
    ipc = pd.Series(100 * 1.10 ** (np.arange(13) / 12), index=pd.date_range("2000-01-01", periods=13, freq="MS"))
    assert fin.deflactar(nivel, ipc).iloc[-1] == pytest.approx(100.0)            # 0 % real


def test_deflactar_usa_el_ultimo_ipc_si_falta_el_mes():
    idx = pd.date_range("2000-01-31", periods=3, freq="ME")
    nivel = pd.Series([100.0, 100.0, 100.0], index=idx)
    ipc = pd.Series([100.0, 110.0], index=pd.date_range("2000-01-01", periods=2, freq="MS"))
    assert fin.deflactar(nivel, ipc).iloc[-1] == pytest.approx(100 / 1.1)


def test_inflacion_anual_diciembre_a_diciembre():
    ipc = pd.Series(100 * 1.02 ** (np.arange(36) / 12), index=pd.date_range("2020-01-01", periods=36, freq="MS"))
    inf = fin.inflacion_anual(ipc)
    assert list(inf.index) == [2021, 2022]
    assert np.allclose(inf.values, 0.02)


# ------------------------------------------------------------------ índices (sin internet)
def test_tramo_de_precio_suma_los_dividendos(monkeypatch, tmp_path):
    monkeypatch.setattr(fin, "CSV_DIR", str(tmp_path))
    dias = pd.bdate_range("2000-01-01", "2004-12-31")
    monkeypatch.setattr(fin, "_descargar_yahoo", lambda s: pd.Series(100.0, index=dias))      # precio plano
    monkeypatch.setitem(fin.INDICES, "prueba", {"tramos": [("X", 2000, 0.03)], "desde": 2001})
    anual = fin.indice_anual("prueba")
    assert np.allclose(anual.values, 0.03, atol=1e-9)          # solo el dividendo


# ------------------------------------------------------------------ simulación
def test_block_bootstrap_toma_anios_seguidos():
    hist = np.arange(50, dtype=float)                           # el valor dice qué año es
    R = fin.muestras_bloques(hist, n=200, H=10, bloque=5, semilla=1)
    assert R.shape == (200, 10)
    for fila in R:
        for b in (fila[:5], fila[5:]):
            assert np.all(np.diff(b) % 50 == 1)                 # consecutivos (dando la vuelta al final)


def test_block_bootstrap_de_un_anio_es_el_clasico():
    R = fin.muestras_bloques(np.array([0.1, -0.2, 0.3]), n=1000, H=7, bloque=1)
    assert R.shape == (1000, 7) and set(np.unique(R)) <= {0.1, -0.2, 0.3}


def test_trayectoria_sin_rentabilidad_es_lo_aportado():
    R = np.zeros((10, 5))
    t = fin.trayectoria_mc(R, 0.0, 0.6, 1_000, 1_200, m=12)
    assert np.allclose(t[:, -1], 1_000 + 1_200 * 5)


def test_ventanas_historicas_tipo_constante():
    ret = pd.Series(0.0, index=range(1990, 2010))
    tray, inicios = fin.ventanas_historicas(ret, None, 5, 0.5, "Tipo constante", 1_000, 0, r_const=0.0)
    assert len(inicios) == 16 and np.allclose(tray.values[:, -1], 1_000)


def test_tir_recupera_la_rentabilidad():
    final = 1_000 * 1.05 ** 10
    assert fin.tir_anual(1_000, 0, 10, final) == pytest.approx(0.05, abs=1e-6)


def test_ventanas_independientes():
    assert fin.ventanas_independientes(53 * 52 + 1, 20 * 52) == 2
    assert fin.ventanas_independientes(10, 100) == 0


# ------------------------------------------------------------------ ahorrador y mortalidad
def test_capital_para_renta_sin_interes():
    assert fin.capital_para_renta(1_000, 240, 0.0) == pytest.approx(240_000)


def test_meta_de_ahorro_es_coherente():
    i = fin.r_mensual(0.04, real=False)
    a = fin.aporte_para_meta(50_000, 5_000, 120, i)
    assert fin.meses_para_meta(50_000, 5_000, a, i) == 120


def test_edad_prudente_con_mortalidad_constante():
    q = np.full(fin.EDAD_MAX_TABLA + 1, 0.10)
    q[-1] = 1.0
    edad = fin.edad_prudente(65, q, umbral=0.10)
    assert edad == pytest.approx(65 + math.log(0.10) / math.log(0.90), abs=1 / 12 + 1e-9)   # ≈ 86,9 años
    assert edad > 65 + fin.esperanza_vida(65, q)


# ------------------------------------------------------------------ test de riesgo
def test_puntuacion_grable_lytton_13_47():
    assert fin.puntuacion_min_max() == (13, 47)


@pytest.mark.parametrize("puntos,nivel", [(18, "Bajo"), (19, "Medio-bajo"), (25, "Medio"), (30, "Medio-alto"),
                                          (40, "Alto")])
def test_niveles_del_test(puntos, nivel):
    assert fin.evaluar_test([puntos])["nivel"] == nivel
