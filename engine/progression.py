"""Utility functions for performance trend analysis and deload logic."""

from __future__ import annotations

from enum import Enum
from statistics import mean, stdev
from typing import Any, Dict, Iterable, List, Sequence


class PlateauStatus(Enum):
    """Represents the status of performance progression."""
    NO_PLATEAU = "No plateau detected."
    STAGNATION = "Performance has stagnated."
    REGRESSION = "Performance has regressed."
    STAGNATION_WARNING = "Performance is showing signs of stagnation." # For early warning
    REGRESSION_WARNING = "Performance is showing signs of regression." # For early warning


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

def detect_plateau(
    values: Sequence[float],
    threshold: float = 0.005,  # Threshold for slope to be considered near zero
    min_duration: int = 3,    # Min consecutive data points for plateau
    check_frequency: str = "session" # For details string, not used in core logic yet
) -> Dict[str, Any]:
    """
    Detects plateaus in performance metrics.

    Args:
        values: Sequence of performance metrics over time.
        threshold: Slope magnitude below which (or if negative, beyond which)
                   is considered a plateau or regression signal.
        min_duration: Minimum number of consecutive data points (after an initial
                      period) showing plateau characteristics to confirm a plateau.
        check_frequency: String descriptor for the data point frequency (e.g., "session", "week").

    Returns:
        A dictionary containing:
            'plateauing': bool - True if a plateau (stagnation or regression) is detected.
            'status': PlateauStatus - Enum indicating the type of plateau.
            'duration': int - Number of consecutive data points the plateau condition has been met.
            'slope': float - Calculated slope of the values.
            'details': str - Human-readable summary.
    """
    n = len(values)
    slope = calculate_trend_slope(values)

    # Normalize threshold against the average value if avg_value is significant
    # This makes threshold relative to the magnitude of values
    # However, for metrics like e1RM, absolute changes might be more relevant.
    # For now, let's keep threshold as an absolute slope value for simplicity,
    # assuming values are somewhat normalized or their typical range is known.
    # Consider if threshold * avg_value (as in old func) is better for some metrics.

    plateau_info = {
        'plateauing': False,
        'status': PlateauStatus.NO_PLATEAU,
        'duration': 0,
        'slope': slope,
        'details': "Not enough data to determine plateau."
    }

    if n < min_duration: # Need at least min_duration points to potentially form a plateau
        plateau_info['details'] = f"Not enough data (need at least {min_duration} points)."
        return plateau_info

    # Check the last `min_duration` points for plateau characteristics
    # This is a simplified check; a more robust check might look for sustained periods.
    # For this version, we'll check the overall trend of the *entire series*
    # and if it meets criteria, the 'duration' will reflect `min_duration`
    # if the condition is met over that period.
    # A more advanced version would slide a window or check segments.

    # Iterate backwards from the end of the series for `min_duration` points
    # to see if the plateau condition holds for these recent points.
    # This is a bit tricky as slope is for the whole series.
    # A simpler approach: if overall slope indicates plateau, assume it's for min_duration.
    # This is what the original prompt leans towards by checking the overall slope.

    # Stagnation check
    if abs(slope) <= threshold:
        # Check if this near-zero slope is representative of the last `min_duration` points
        # For simplicity, if the overall slope is flat, and we have enough data,
        # we assume this has been the case for at least `min_duration`.
        # A more precise 'duration' would require segmental analysis.
        if n >= min_duration : # If the overall trend is flat
            plateau_info['plateauing'] = True
            plateau_info['status'] = PlateauStatus.STAGNATION
            plateau_info['duration'] = min_duration # Simplified duration
            plateau_info['details'] = (
                f"Performance has stagnated (slope: {slope:.4f}) "
                f"over the checked period ({check_frequency}s)."
            )
            # We could check the slope of ONLY the last `min_duration` points too
            # slope_last_segment = calculate_trend_slope(values[-min_duration:])
            # if abs(slope_last_segment) <= threshold: ...

    # Regression check (overrides stagnation if true)
    # Using a more negative threshold for regression
    regression_threshold = -1.5 * threshold # Example: if slope is more negative than this
    if slope < regression_threshold:
        if n >= min_duration: # If the overall trend is negative
            plateau_info['plateauing'] = True
            plateau_info['status'] = PlateauStatus.REGRESSION
            plateau_info['duration'] = min_duration # Simplified duration
            plateau_info['details'] = (
                f"Performance has regressed (slope: {slope:.4f}) "
                f"over the checked period ({check_frequency}s)."
            )
            # slope_last_segment = calculate_trend_slope(values[-min_duration:])
            # if slope_last_segment < regression_threshold: ...

    if not plateau_info['plateauing'] and n >= min_duration:
        plateau_info['details'] = f"No plateau detected (slope: {slope:.4f})."
    elif not plateau_info['plateauing'] and n < min_duration:
        plateau_info['details'] = f"Not enough data (need {min_duration} points, have {n}). Slope: {slope:.4f}."


    # Refine duration: A more accurate duration would count consecutive points
    # at the end of the series that individually contribute to the plateau.
    # This is complex with a single slope. The current 'duration' is a placeholder
    # indicating the minimum observation period if a plateau is detected based on overall slope.

    return plateau_info


def generate_deload_protocol(
    plateau_severity: float = 0.5,
    deload_duration_weeks: int = 1,
    recent_fatigue_score: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Generates a dynamic deload protocol based on plateau severity and fatigue.

    Args:
        plateau_severity: Float from 0.0 (mild) to 1.0 (severe).
        deload_duration_weeks: How many weeks the deload should last (e.g., 1 or 2).
        recent_fatigue_score: Score representing recent accumulated fatigue (0-100).

    Returns:
        A list of dictionaries, each representing a week of the deload protocol.
    """
    protocol_weeks = []

    # Define base and max reductions
    base_vol_reduction = 0.40  # 40% reduction for mildest case
    max_additional_vol_reduction_severity = 0.20 # Max 20% more from severity
    max_additional_vol_reduction_fatigue = 0.10 # Max 10% more from fatigue

    base_int_reduction = 0.10 # 10% reduction for mildest case
    max_additional_int_reduction_severity = 0.15 # Max 15% more from severity

    min_volume_multiplier = 0.4 # Absolute minimum volume multiplier
    min_intensity_multiplier = 0.7 # Absolute minimum intensity multiplier

    for week_num in range(1, deload_duration_weeks + 1):
        # Adjust reduction for multi-week deloads (e.g., slightly less reduction in week 2 if it's a 2-week plan)
        # This is a simple approach; could be more nuanced.
        multi_week_factor = 1.0 if deload_duration_weeks == 1 else (0.9 + 0.1 * week_num) # less severe further into deload

        # Calculate volume reduction
        vol_reduction_from_severity = max_additional_vol_reduction_severity * plateau_severity
        vol_reduction_from_fatigue = max_additional_vol_reduction_fatigue * (min(recent_fatigue_score, 100.0) / 100.0)
        total_vol_reduction = base_vol_reduction + vol_reduction_from_severity + vol_reduction_from_fatigue

        volume_multiplier = max(min_volume_multiplier, (1.0 - total_vol_reduction) * multi_week_factor)

        # Calculate intensity reduction
        int_reduction_from_severity = max_additional_int_reduction_severity * plateau_severity
        total_int_reduction = base_int_reduction + int_reduction_from_severity

        intensity_multiplier = max(min_intensity_multiplier, (1.0 - total_int_reduction) * multi_week_factor)

        # RIR target adjustment (example: increase RIR for deload)
        rir_target_adjust = 0
        if plateau_severity > 0.3:
            rir_target_adjust +=1
        if recent_fatigue_score > 50:
             rir_target_adjust +=1
        rir_target_adjust = min(rir_target_adjust, 3) # Cap RIR adjustment

        notes = "Focus on recovery, technique, and maintaining movement patterns."
        if plateau_severity > 0.7 or recent_fatigue_score > 70:
            notes += " Prioritize sleep and nutrition."

        week_protocol = {
            "week_number": week_num,
            "volume_multiplier": round(volume_multiplier, 2),
            "intensity_multiplier": round(intensity_multiplier, 2),
            "frequency_multiplier": 1.0,  # Kept at 1.0 for now
            "rir_target_adjust": rir_target_adjust,
            "notes": notes,
        }
        protocol_weeks.append(week_protocol)

    return protocol_weeks


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
    "PlateauStatus",
]


if __name__ == '__main__':
    # --- Test detect_plateau ---
    print("--- Testing detect_plateau ---")

    # Example 1: Clear Progression
    values_progress = [100.0, 102.0, 104.0, 106.0, 108.0]
    plateau_info = detect_plateau(values_progress, min_duration=3)
    print(f"Progressing: {values_progress} -> {plateau_info}")
    assert not plateau_info['plateauing']
    assert plateau_info['status'] == PlateauStatus.NO_PLATEAU

    # Example 2: Stagnation
    values_stagnation = [100.0, 100.5, 100.2, 100.3, 100.1]
    plateau_info = detect_plateau(values_stagnation, threshold=0.1, min_duration=3) # Higher threshold for test
    print(f"Stagnation: {values_stagnation} -> {plateau_info}")
    assert plateau_info['plateauing']
    assert plateau_info['status'] == PlateauStatus.STAGNATION
    assert plateau_info['duration'] == 3

    # Example 3: Regression
    values_regression = [100.0, 98.0, 96.0, 95.0, 93.0]
    plateau_info = detect_plateau(values_regression, threshold=0.1, min_duration=3)
    print(f"Regression: {values_regression} -> {plateau_info}")
    assert plateau_info['plateauing']
    assert plateau_info['status'] == PlateauStatus.REGRESSION

    # Example 4: Short data series
    values_short = [100.0, 101.0]
    plateau_info = detect_plateau(values_short, min_duration=3)
    print(f"Short Series: {values_short} -> {plateau_info}")
    assert not plateau_info['plateauing']
    assert "Not enough data" in plateau_info['details']

    # Example 5: Stagnation with default threshold (requires smaller changes)
    values_stagnation_tight = [100.0, 100.01, 100.02, 100.01, 100.00]
    plateau_info = detect_plateau(values_stagnation_tight, threshold=0.005, min_duration=3)
    print(f"Stagnation (tight): {values_stagnation_tight} -> {plateau_info}")
    assert plateau_info['plateauing']
    assert plateau_info['status'] == PlateauStatus.STAGNATION

    # Example 6: Clear progression with more data
    values_progress_long = [100, 101, 102, 103, 104, 105, 106, 107]
    plateau_info = detect_plateau(values_progress_long, min_duration=4)
    print(f"Progressing Long: {values_progress_long} -> {plateau_info}")
    assert not plateau_info['plateauing']

    # Example 7: Late Stagnation (overall slope might still be positive)
    # Current detect_plateau checks overall slope, so this might not be caught as stagnation
    # unless the recent data significantly flattens the overall slope.
    # A segmental analysis would be needed for more nuanced detection here.
    values_late_stagnation = [100, 102, 104, 106, 106.1, 106.2, 106.15]
    plateau_info = detect_plateau(values_late_stagnation, threshold=0.1, min_duration=3)
    print(f"Late Stagnation: {values_late_stagnation} -> {plateau_info}")
    # This assertion might depend on how much the late values affect overall slope.
    # If slope of [100, 102, 104, 106, 106.1, 106.2, 106.15] is still > 0.1, it won't be stagnation.
    # slope is approx 1.08, so not stagnation by current logic. This is a limitation.

    # --- Test generate_deload_protocol ---
    print("\n--- Testing generate_deload_protocol ---")

    # Example 1: Mild plateau, low fatigue, 1 week
    protocol1 = generate_deload_protocol(plateau_severity=0.2, deload_duration_weeks=1, recent_fatigue_score=10.0)
    print(f"Mild Plateau, Low Fatigue (1wk): {protocol1}")
    assert len(protocol1) == 1
    assert protocol1[0]['volume_multiplier'] < 0.6 # Base is 0.6, severity and fatigue increase reduction
    assert protocol1[0]['intensity_multiplier'] < 0.9

    # Example 2: Severe plateau, high fatigue, 2 weeks
    protocol2 = generate_deload_protocol(plateau_severity=0.9, deload_duration_weeks=2, recent_fatigue_score=80.0)
    print(f"Severe Plateau, High Fatigue (2wks): {protocol2}")
    assert len(protocol2) == 2
    assert protocol2[0]['volume_multiplier'] <= 0.4 # Should be close to min_volume_multiplier
    assert protocol2[0]['intensity_multiplier'] <= 0.75
    assert protocol2[1]['volume_multiplier'] > protocol2[0]['volume_multiplier'] # Week 2 might be slightly less severe
    assert protocol2[0]['rir_target_adjust'] >= 2

    # Example 3: Moderate plateau, moderate fatigue, 1 week
    protocol3 = generate_deload_protocol(plateau_severity=0.5, deload_duration_weeks=1, recent_fatigue_score=50.0)
    print(f"Moderate Plateau, Moderate Fatigue (1wk): {protocol3}")
    assert len(protocol3) == 1
    assert protocol3[0]['volume_multiplier'] < (1.0 - (0.4 + 0.2*0.5 + 0.1*0.5)) + 0.01 # approx
    assert protocol3[0]['intensity_multiplier'] < (1.0 - (0.1 + 0.15*0.5)) + 0.01 # approx
    assert protocol3[0]['rir_target_adjust'] >= 1

    # Example 4: Zero severity, zero fatigue (edge case)
    protocol4 = generate_deload_protocol(plateau_severity=0.0, deload_duration_weeks=1, recent_fatigue_score=0.0)
    print(f"Zero Severity, Zero Fatigue (1wk): {protocol4}")
    assert protocol4[0]['volume_multiplier'] == round(1.0 - 0.40, 2) # Base reduction only
    assert protocol4[0]['intensity_multiplier'] == round(1.0 - 0.10, 2)
    assert protocol4[0]['rir_target_adjust'] == 0

    print("\nAll tests seem to pass based on implemented logic.")
