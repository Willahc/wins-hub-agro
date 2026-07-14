#!/usr/bin/env python3
"""
Testes de performance — Fase 5 Clima e Janelas Operacionais.
Valida normalização, scoring, classificação e cache freshness.
"""

import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app'))

from domain.weather_operations import (
    normalize_temperature_celsius,
    normalize_precipitation_mm,
    normalize_wind_kmh,
    normalize_humidity_pct,
    compute_window_score,
    classify_temperature,
    check_freshness,
    WINDOW_DEFAULTS,
)
from datetime import datetime, timedelta


def test_normalization_throughput():
    start = time.time()
    for _ in range(10000):
        normalize_temperature_celsius(25.0)
        normalize_precipitation_mm(5.0)
        normalize_wind_kmh(10.0)
        normalize_humidity_pct(60.0)
    elapsed = time.time() - start
    assert elapsed < 1.0, f"Normalização muito lenta: {elapsed:.3f}s para 10k iterações"
    print(f"OK: Normalização 10k iterações em {elapsed:.3f}s")


def test_scoring_throughput():
    start = time.time()
    for _ in range(10000):
        compute_window_score(
            window_type="cutting",
            temperature_c=25.0,
            precipitation_mm=5.0,
            wind_kmh=10.0,
            is_daytime=True,
            required_fields_present=True,
        )
    elapsed = time.time() - start
    assert elapsed < 2.0, f"Scoring muito lento: {elapsed:.3f}s para 10k iterações"
    print(f"OK: Scoring 10k iterações em {elapsed:.3f}s")


def test_classify_temperature_throughput():
    start = time.time()
    for _ in range(10000):
        classify_temperature(25.0, 25.0)
        classify_temperature(5.0, 3.0)
        classify_temperature(35.0, 40.0)
    elapsed = time.time() - start
    assert elapsed < 0.5, f"Classificação muito lenta: {elapsed:.3f}s para 10k iterações"
    print(f"OK: Classificação 10k iterações em {elapsed:.3f}s")


def test_cache_freshness_logic():
    now = datetime.now(tz=__import__('datetime').timezone.utc)
    fresh = now - timedelta(minutes=10)
    stale = now - timedelta(minutes=60)
    fallback = now - timedelta(hours=5)
    status1, _ = check_freshness(fresh, now)
    status2, _ = check_freshness(stale, now)
    status3, _ = check_freshness(fallback, now)
    assert status1 == "fresh", f"Esperado fresh, obtido {status1}"
    assert status2 == "stale", f"Esperado stale, obtido {status2}"
    assert status3 == "fallback", f"Esperado fallback, obtido {status3}"
    print("OK: Cache freshness logic validado")


if __name__ == "__main__":
    test_normalization_throughput()
    test_scoring_throughput()
    test_classify_temperature_throughput()
    test_cache_freshness_logic()
    print("\nTodos os testes de performance passaram!")
