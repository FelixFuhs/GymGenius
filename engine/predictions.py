# Extended Epley Formula for 1RM prediction
# Formula: 1RM = w * (1 + (r / 30))
# Some sources use variations, e.g. Brzycki: w / ( 1.0278 – 0.0278 * r )
# We'll stick to the common Epley: w * (1 + r / 30)
# For r=1, 1RM = w. For r=0, it's undefined or implies w is already 1RM.
# We should handle cases where reps are very low (e.g., 1) or too high for reliable prediction.

def extended_epley_1rm(weight: float, reps: int) -> float:
    """
    Calculates estimated 1 Rep Max (1RM) using the Extended Epley formula.
    Assumes weight is positive and reps are 1 or more.
    Returns 0 if reps are less than 1, as the formula is not intended for it.
    """
    if reps < 1:
        return 0.0 # Or raise ValueError, depending on desired handling
    if reps == 1:
        return weight

    # Standard Epley formula
    estimated_1rm = weight * (1 + (reps / 30.0))
    return round(estimated_1rm, 2)

# Example Test (not part of the app, just for quick verification)
if __name__ == '__main__':
    print(f"100kg for 10 reps: {extended_epley_1rm(100, 10):.2f}kg 1RM") # Expected: 133.33
    print(f"100kg for 1 rep: {extended_epley_1rm(100, 1):.2f}kg 1RM")   # Expected: 100.00
    print(f"50kg for 5 reps: {extended_epley_1rm(50, 5):.2f}kg 1RM")    # Expected: 58.33
    print(f"200kg for 0 reps: {extended_epley_1rm(200, 0):.2f}kg 1RM")  # Expected: 0.0
