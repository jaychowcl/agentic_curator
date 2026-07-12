You are assigning a harmonization target to the most appropriate ontology
framework.

Use the harmonization target, publication context, compact metadata context, and
ontology framework config to choose one configured ontology framework ID.

Return JSON only with:
- decision: one configured ontology framework ID, "false" if no framework fits,
  or "unsure" if the evidence is insufficient.
- confidence: high, medium, low, or none.
- reason: a short explanation grounded in the target, context, and framework
  metadata.
