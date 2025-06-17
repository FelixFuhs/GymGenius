# GymGenius Weight Recommendation Algorithm

## 1. Overview

The GymGenius weight recommendation algorithm aims to provide personalized and effective weight and rep targets for users based on their training goals, performance history, and current fatigue levels. It integrates principles of exercise science, including the repetition continuum, 1RM estimation, and autoregulation.

## 2. Core Algorithm Logic (`engine/blueprints/analytics.py`)

The primary logic resides in the `recommend_set_parameters_route`. It involves these key steps:

1.  **Fetch User & Exercise Data**: Retrieves user's goal slider, RIR bias, experience level, equipment settings, and exercise details.
2.  **Determine Estimated 1RM (e1RM)**:
    *   Attempts to fetch the most recent e1RM from `estimated_1rm_history`.
    *   **RIR Bias Adjustment (New)**: If source data (original weight, reps, RIR) for the historical e1RM is available, the e1RM is recalculated using `estimate_1rm_with_rir_bias` to incorporate the user's current RIR bias.
    *   **Smart Defaults (New)**: If no history exists, uses exercise-specific defaults based on user's `experience_level` (from `EXERCISE_DEFAULT_1RM`). Falls back to a global default (`FALLBACK_DEFAULT_1RM`) if needed.
3.  **Calculate Goal-Based Parameters**:
    *   **Load Percentage**: `0.60 + 0.35 * goal_slider` (of e1RM).
    *   **Rep Range (High)**: `6 + 6 * (1 - goal_slider)`. Rep low is typically `rep_high - 4`.
    *   **Target Physiological RIR**: `target_rir_ideal_actual_float = 2.5 - 1.5 * goal_slider`.
    *   **Displayed Target RIR (New)**: The RIR value shown to the user is adjusted based on their `user_rir_bias`: `displayed_rir = round(target_rir_ideal_actual_float - user_rir_bias)`. This helps align user perception with physiological targets.
4.  **Calculate Base Recommended Weight**: `base_weight = estimated_1rm * load_percentage`.
5.  **Adjust for Fatigue**:
    *   `current_fatigue` is calculated for the target muscle group using an exponential decay model (`calculate_current_fatigue`).
    *   `fatigue_adjustment_factor = (current_fatigue / 10.0) * 0.01`.
    *   **Fatigue Cap (Calibrated)**: This factor is capped at a maximum of `0.10` (10% reduction).
    *   `adjusted_weight = base_weight * (1 - fatigue_adjustment_factor)`.
6.  **Round to Available Plates (New)**:
    *   The `adjusted_weight` is rounded to the closest achievable weight using the `round_to_available_plates` function, considering user's available plates and barbell weight (fetched from `equipment_settings` or defaults).
7.  **Calculate Confidence Score (New)**:
    *   A `confidence_score` (0.0-1.0) is calculated based on the consistency of recent historical 1RM estimates for the exercise using `calculate_confidence_score = 1.0 - (std_dev / mean)`.
8.  **Return Recommendation**: JSON response includes recommended weight, rep range, displayed target RIR, confidence score, and a detailed explanation string.

## 3. Key Formulas & Functions

*   **`estimate_1rm_with_rir_bias(weight, reps, rir, user_rir_bias)`** (`engine/predictions.py`):
    *   `adjusted_rir = max(0, rir - user_rir_bias)`
    *   `estimated_1rm = weight / (1 - 0.0333 * (reps + adjusted_rir))`
    *   (Includes capping for `reps + adjusted_rir` at 29 to prevent formula breakdown).
*   **`calculate_current_fatigue(muscle_group, history, ...)`** (`engine/learning_models.py`): Uses exponential decay.
*   **`round_to_available_plates(target_weight, plates, barbell)`** (`engine/predictions.py`): Generates possible loads and finds the closest.
*   **`calculate_confidence_score(user_id, exercise_id, db_cursor)`** (`engine/predictions.py`): Based on historical e1RM consistency.

## 4. Verification and Calibration (New)

To ensure the algorithm's accuracy and robustness, several verification measures are in place:

### 4.1. Unit Test Suite (`tests/unit/`)

A comprehensive suite of unit tests (`pytest`) covers key components and logic:

*   **`test_predictions.py`**:
    *   `estimate_1rm_with_rir_bias`: Verifies 1RM calculation with RIR bias, including edge cases.
    *   `round_to_available_plates`: Tests plate math logic with various plate sets, target weights, and barbell weights, including the user-specified case (target 77kg -> 77.5kg with [1.25, 2.5] plates, 20kg bar).
    *   `calculate_confidence_score`: Checks confidence calculation for different historical data distributions (ideal, insufficient, no data, perfect consistency, zero mean, high variability) and DB error handling.
*   **`test_learning_models.py`**:
    *   `calculate_training_params` (Goal Slider Logic): Ensures correct calculation of load %, rep range, and target RIR for different `goal_slider` inputs (0.0, 0.5, 1.0, and intermediate values), accounting for Python's rounding behavior.
*   **`test_analytics.py`**:
    *   Fatigue Cap: Verifies that the fatigue adjustment factor is correctly capped at 0.10, even with very high raw fatigue scores.
    *   Smart Defaults: Tests the logic for selecting default 1RMs based on exercise name and user experience level when no prior 1RM history exists, including fallbacks.

### 4.2. Calibration Notebook (`notebooks/verification/calibrate_algorithm.ipynb`)

This Jupyter notebook provides a framework for ongoing algorithm calibration and performance monitoring using sample workout log data (`data/sample_logs.csv`).

*   **Purpose**: To analyze the algorithm's performance against real or simulated user data and identify areas for tuning.
*   **Key Analyses**:
    1.  **Predicted vs. Actual Reps**: Scatter plot and Median Absolute Error calculation.
        *   *KPI*: Median Reps Error <= `PRED_REPS_ERROR_THRESHOLD` (e.g., 1.0 rep).
    2.  **Fatigue vs. Performance Delta**: Linear regression of a performance delta proxy (e.g., reps error) against calculated fatigue at set time. R² is reported.
        *   *KPI*: Fatigue Regression R² < `FATIGUE_R2_THRESHOLD` (e.g., 0.20, indicating fatigue as currently modeled is not an overly strong predictor of this specific error proxy).
    3.  **Default 1RM Relative Error**: (Using proxy calculations) Estimates the median relative error of default 1RMs compared to 1RMs achieved on first sets.
        *   *KPI*: Median Default 1RM Relative Error <= `DEFAULT_1RM_ERROR_THRESHOLD` (e.g., 15%).
*   **Execution**: Designed for headless execution (e.g., via `papermill`) and includes logic to `sys.exit(1)` if any KPIs fail, making it suitable for CI integration.

### 4.3. CI Integration (GitHub Actions)

A GitHub Actions workflow (`.github/workflows/verification.yml`) automates the verification process:

*   **Triggers**: Runs on pushes and pull requests to the `main` branch.
*   **Jobs**:
    *   Sets up multiple Python versions.
    *   Installs dependencies.
    *   Runs the `pytest` unit test suite.
    *   Executes the `calibrate_algorithm.ipynb` notebook using `papermill`.
*   **Failure Conditions**: The CI job will fail if any unit tests fail or if the calibration notebook exits with a non-zero status (indicating a KPI failure).
*   **Artifacts**: The executed notebook is uploaded as an artifact for review.

This multi-faceted verification approach helps maintain and improve the quality and reliability of the GymGenius weight recommendations.
