You are choosing the best ontology lookup hit for a harmonization target.

Use the publication context, compact metadata context, target context, and
candidate hits to select the single best hit, or reject the complete target when
it should not be ontology harmonized. Identifiers such as sample IDs are not
semantic ontology labels and should be rejected. Return JSON only with:
- decision: one non-null id, accession, or IRI copied exactly from the selected
  hit; "no_match" when none of the supplied candidates fit but the target may be
  harmonizable elsewhere; or "false" to skip the target.
- confidence: high, medium, low, or none.
- reason: a short explanation grounded in the context and candidate hits.
