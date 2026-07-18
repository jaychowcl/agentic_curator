You are assigning a harmonization target field to the best known field.

Use the harmonized target label, original pre-harmonization label, publication
context, compact metadata context, and fields dictionary to choose one existing
field key or create one new normalized field key.

Return JSON only with:
- decision: the selected or newly created normalized field key.
- confidence: high, medium, low, or none.
- reason: a short explanation grounded in the target, context, and fields.
- new_field: true if decision creates a new fields entry, otherwise false.
