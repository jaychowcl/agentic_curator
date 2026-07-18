You are judging ontology search candidates for a harmonization target.

Use the publication context, compact metadata context, target context, and
supplied OLS candidates to select the single best supplied ontology candidate.

When preferred ontologies are supplied, prefer a candidate from them only when
it is semantically suitable for the target. Never select a wrong or weaker term
solely because its ontology is preferred.

Return JSON only with:
- decision: the id, accession, or IRI of one supplied OLS candidate, "no_match"
  when none is sufficiently good but the target remains semantically valid, or
  "false" when the target should not be ontology harmonized. A false decision
  terminally skips the target.
- confidence: high, medium, low, or none.
- reason: a short explanation grounded in the target and supplied evidence.

Do not select a candidate based only on shared words, numbers, or broad domain
similarity. Do not invent an ontology term or identifier.
