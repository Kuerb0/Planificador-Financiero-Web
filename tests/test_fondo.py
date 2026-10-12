"""Fondo animado (fondo.py), sin Streamlit. Ejecutar: python tests/test_fondo.py"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "py"))
import fondo

ys = fondo.serie(11)
assert len(ys) == fondo.PUNTOS and 6 <= min(ys) and max(ys) <= 94, "los puntos caben en el cuadro"
cerrada = fondo.serie(11, 44)
assert abs(cerrada[0] - cerrada[-1]) < 8, "el final enlaza con el principio (si no, la curva da un salto al repetirse)"
for tema in ("dark", "light", "otro"):
    h = fondo.html(tema)
    assert h.count("<svg") == len(fondo.CAPAS) and not re.search(r"@\w+@", h), f"marcadores sin sustituir en {tema}"
print("TEST OK")
