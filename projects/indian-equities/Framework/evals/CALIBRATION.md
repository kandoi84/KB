# Probability Calibration

## Purpose
Prevent intuitive probabilities from becoming arbitrary confidence language.

## Procedure
- Store every explicit catalyst/debate probability with date and event definition.
- Resolve outcome as occurred / did not occur / ambiguous by deadline.
- Bucket forecasts: 50-59, 60-69, 70-79, 80-89, 90-100.
- Compare forecast probability to realized frequency.
- Calculate Brier score for binary events.
- Track calibration separately by event type: earnings revision, regulatory, corporate action, cycle inflection, capacity/commissioning.

## Guardrail
Do not tighten probability precision beyond 5-percentage-point increments until the dataset demonstrates calibration skill.
