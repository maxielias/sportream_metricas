"""Herramientas para cálculos de métricas deportivas.

Contiene funciones para conversión de ritmos/velocidades, cálculo de pendiente
e integración con `specialsauce` (trainingpeaks/minetti) cuando está disponible.

Ubicación: `metrics.py` (raíz del repo)

Funciones principales:
- pace_str_to_minutes / minutes_to_pace_str
- pace_min_per_km_to_kph / kph_to_pace_min_per_km
- elevation_grade
- compute_ngp_speed_factor (usa trainingpeaks.ngp_speed_factor)
- get_threshold_speed (por deporte)
- compute_speed_flat_tp
- compute_intensity_factor
- compute_rtss
- compute_energy (minetti cost + kcal)
- calculate_clean_quartiles
- compute_time_in_zones

Notas: algunas funciones dependen de `specialsauce`. Si no está instalada,
las funciones que la usan lanzarán ImportError con mensaje claro.
"""

from typing import List, Tuple, Optional
import pandas as pd
import numpy as np


def pace_str_to_minutes(pace: str) -> float:
    """Convierte un string de ritmo 'M:SS' o 'MM:SS' a minutos decimales por km.

    Ejemplo: '4:20' -> 4.3333333333
    """
    if isinstance(pace, (int, float)):
        return float(pace)
    s = pace.strip()
    if ':' in s:
        parts = s.split(':')
        try:
            minutes = float(parts[0])
            seconds = float(parts[1]) if len(parts) > 1 else 0.0
            return minutes + seconds / 60.0
        except Exception as e:
            raise ValueError(f"Formato de ritmo no válido: {pace}") from e
    # try float
    try:
        return float(s)
    except Exception:
        raise ValueError(f"Formato de ritmo no válido: {pace}")


def minutes_to_pace_str(minutes: float) -> str:
    """Convierte minutos decimales por km a formato 'M:SS'."""
    if minutes is None or (isinstance(minutes, float) and np.isnan(minutes)):
        return ''
    total_seconds = int(round(minutes * 60))
    m = total_seconds // 60
    s = total_seconds % 60
    return f"{m}:{s:02d}"


def pace_min_per_km_to_kph(pace_min_per_km: float) -> float:
    """Convierte minutos por km a km/h.

    velocidad(km/h) = 60 / (minutos por km)
    """
    if pace_min_per_km <= 0:
        return 0.0
    return 60.0 / float(pace_min_per_km)


def kph_to_pace_min_per_km(kph: float) -> float:
    """Convierte km/h a minutos por km.

    minutos por km = 60 / km/h
    """
    if kph <= 0:
        return float('inf')
    return 60.0 / float(kph)


def elevation_grade(elevation_gain_m: float, elevation_loss_m: float, distance_m: float) -> float:
    """Calcula la pendiente (grade) como (gain - loss) / distance (ambos en metros).

    Devuelve un valor en unidades de "rise/run" (por ejemplo 0.01 = 1%).
    """
    if distance_m == 0 or distance_m is None:
        return 0.0
    try:
        return float((elevation_gain_m - elevation_loss_m) / distance_m)
    except Exception:
        return 0.0


def _import_trainingpeaks_and_minetti():
    try:
        from specialsauce.specialsauce.sources import trainingpeaks, minetti
        return trainingpeaks, minetti
    except Exception as e:
        raise ImportError("La librería 'specialsauce' no está disponible. Instala 'specialsauce' para usar estas funciones.") from e


def compute_ngp_speed_factor(elevation_grade_value: float) -> float:
    """Wrapper que devuelve ngp_speed_factor usando specialsauce.trainingpeaks.

    Lanza ImportError si specialsauce no está instalada.
    """
    trainingpeaks, _ = _import_trainingpeaks_and_minetti()
    return trainingpeaks.ngp_speed_factor(elevation_grade_value)


def get_threshold_speed(sport: str) -> float:
    """Devuelve el umbral (en unidades apropiadas) para el deporte.

    - running: 3.75 min/km -> convertido a km/h
    - cycling: 200 (watts)
    - swimming: 2 min/100m -> convertido a km/h
    """
    s = sport.lower()
    if s == 'running' or s == 'run':
        pace = 3.75  # min/km
        return pace_min_per_km_to_kph(pace)
    if s == 'cycling' or s == 'bike':
        return 200.0
    if s == 'swimming' or s == 'swim':
        # 2 min per 100m -> 20 min per km -> kph = 60/20 = 3.0
        pace_100m_min = 2.0
        pace_per_km = pace_100m_min * 10.0
        return pace_min_per_km_to_kph(pace_per_km)
    # default: assume running-like
    return pace_min_per_km_to_kph(3.75)


def compute_speed_flat_tp(average_speed_tp: float, elevation_grade_value: float) -> float:
    """speed_flat_tp = average_speed_tp * ngp_speed_factor(elevation_grade)

    average_speed_tp: km/h
    devuelve km/h
    """
    factor = compute_ngp_speed_factor(elevation_grade_value)
    return average_speed_tp * factor


def compute_intensity_factor(speed_flat_tp: float, threshold_speed: float) -> float:
    """intensity_factor = speed_flat_tp / threshold_speed

    Nota: para cycling threshold_speed es potencia (watts), por lo que la relación puede
    no ser homogénea; se asume que el usuario entiende las unidades por deporte.
    """
    if threshold_speed == 0:
        return 0.0
    return float(speed_flat_tp) / float(threshold_speed)


def compute_rtss(df_summary: pd.DataFrame, speed_flat_tp: float, intensity_factor: float, threshold_speed: float) -> Optional[float]:
    """Calcula RTSS según la fórmula provista:

    rtss = (df_summary.durationInSeconds[0] * speed_flat_tp * intensity_factor) / (threshold_speed * 3600) * 100

    Asume que `df_summary` es un DataFrame y que la fila 0 contiene `durationInSeconds`.
    """
    try:
        duration = float(df_summary.loc[0, 'durationInSeconds'])
    except Exception:
        try:
            duration = float(df_summary['durationInSeconds'].iat[0])
        except Exception:
            return None
    if threshold_speed == 0:
        return None
    rtss = (duration * speed_flat_tp * intensity_factor) / (threshold_speed * 3600.0) * 100.0
    return float(rtss)


def compute_energy(df_summary: pd.DataFrame, elevation_grade_value: float, weight_kg: float = 73.0) -> Tuple[Optional[float], Optional[float]]:
    """Calcula kj_kg y kcal estimadas usando minetti.cost_of_running.

    cost_of_running_minetti = minetti.cost_of_running(elevation_grade)
    kj_kg = cost_of_running_minetti * distance_m / 1000
    kcal = (kj_kg * weight) / 4.184

    Aquí `df_summary.distanceInMeters[0]` se usa como distancia.
    """
    _, minetti = _import_trainingpeaks_and_minetti()
    try:
        distance_m = float(df_summary.loc[0, 'distanceInMeters'])
    except Exception:
        try:
            distance_m = float(df_summary['distanceInMeters'].iat[0])
        except Exception:
            return None, None
    cost = minetti.cost_of_running(elevation_grade_value)
    kj_kg = cost * distance_m / 1000.0
    kcal = (kj_kg * float(weight_kg)) / 4.184
    return float(kj_kg), float(kcal)


def calculate_clean_quartiles(series: pd.Series):
    """Filtra ceros/negativos y devuelve (q1, median, q3, q4).

    Devuelve None si la serie limpia queda vacía.
    """
    clean_series = series[series > 0]
    if clean_series.empty:
        return None
    q1 = clean_series.quantile(0.25)
    median = clean_series.quantile(0.50)
    q3 = clean_series.quantile(0.75)
    q4 = clean_series.quantile(1.00)
    return q1, median, q3, q4


def compute_time_in_zones(values: pd.Series, zones: List[Tuple[Optional[float], Optional[float]]], total_time_seconds: Optional[float] = None):
    """Calcula % de muestras y minutos en cada zona.

    - `values`: serie de valores (por ejemplo velocidades) de donde se evalúan zonas.
    - `zones`: lista de tuplas (min_inclusive, max_exclusive). Usa None para abierto.
    - `total_time_seconds`: si se provee, los minutos en zona se calculan como pct * total_time_seconds / 60.
      Si no, las "minutos" devueltas son proporcionales al número de muestras (no absolutas).

    Devuelve lista de dicts: [{'zone': (min,max), 'pct': 0.xx, 'minutes': y}, ...]
    """
    clean = values.dropna()
    if clean.empty:
        return []
    n = len(clean)
    results = []
    for z in zones:
        lo, hi = z
        if lo is None and hi is None:
            mask = pd.Series([True] * n)
        elif lo is None:
            mask = clean < hi
        elif hi is None:
            mask = clean >= lo
        else:
            mask = (clean >= lo) & (clean < hi)
        count = int(mask.sum())
        pct = float(count) / float(n)
        if total_time_seconds is not None:
            minutes = pct * float(total_time_seconds) / 60.0
        else:
            minutes = pct * float(n)  # relative units
        results.append({'zone': z, 'pct': pct, 'minutes': minutes, 'count': count})
    return results


if __name__ == '__main__':
    # ejemplo rápido
    print('metrics.py cargado. Usa las funciones desde tu código.')
