"""One consistent adult-resting demonstration profile, never camera measurements."""
PULSE_BPM=72
RESPIRATIONS_PER_MINUTE=16
OXYGEN_PERCENT=98
TEMPERATURE_C=36.6
ENERGY_VISUAL_SCORE=86  # Artwork only; no clinical reference range exists for this score.
SLEEP_HOURS=5.5         # Intentionally below goal to match the scripted short-sleep report.
SLEEP_GOAL_HOURS=7


def cycle(t,per_minute):
    return t*per_minute/60
