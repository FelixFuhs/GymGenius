"""Utility functions for performance trend analysis and deload logic."""

from __future__ import annotations

from statistics import mean, stdev
from typing import Iterable, Sequence


def calculate_trend_slope(values: Sequence[float]) -> float:
    """Return slope of a simple linear regression y = ax + b."""
    n = len(values)
    if n < 2:
        return 0.0
    x_vals = range(n)
    x_mean = mean(x_vals)
    y_mean = mean(values)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
    den = sum((x - x_mean) ** 2 for x in x_vals)
    return num / den if den else 0.0


def detect_plateau(values: Sequence[float], threshold: float = 0.005) -> bool:
    """Return True if progression has slowed below threshold."""
    if len(values) < 3:
        return False
    slope = calculate_trend_slope(values)
    avg = mean(values)
    return abs(slope) < threshold * avg


def generate_deload_protocol() -> dict:
    """Return a simple two-week deload protocol."""
    return {
        "week1": {"volume_multiplier": 1.1, "intensity_multiplier": 1.0},
        "week2": {"volume_multiplier": 0.6, "intensity_multiplier": 0.85},
    }


def confidence_score(predictions: Iterable[float], actuals: Iterable[float]) -> float:
    """Calculate confidence as 1 - normalized std deviation of errors."""
    preds = list(predictions)
    acts = list(actuals)
    if not preds or len(preds) != len(acts):
        return 0.0
    errors = [abs(p - a) for p, a in zip(preds, acts)]
    if len(errors) < 2:
        return 1.0 - (errors[0] / preds[0]) if preds[0] else 0.0
    err_std = stdev(errors)
    avg_pred = mean(preds)
    if avg_pred == 0:
        return 0.0
    confidence = 1.0 - err_std / avg_pred
    return max(0.0, min(confidence, 1.0))


__all__ = [
    "calculate_trend_slope",
    "detect_plateau",
    "generate_deload_protocol",
    "confidence_score",
]

