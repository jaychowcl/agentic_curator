You are checking a complete list of original ontology harmonization targets for
compound labels that contain additional, independently harmonizable concepts.

Return only additional targets. Never repeat, replace, rewrite, remove, or
otherwise modify an original target. Return an empty additions list when every
original label is already atomic or when a split is uncertain.

Each addition must identify its source target, contain one atomic label, and
provide a provisional field hint describing the semantic role of that label.
Use the publication context, compact metadata context, original field-label
pair, and configured fields to interpret acronyms and meaning. Field hints are
not final field assignments.

For example, an original `tissue: IPF lung` target remains unchanged. It may
justify one addition with label `lung` and field hint `tissue`, because lung is a
distinct anatomical concept. Return only that `lung` addition: do not return
`IPF lung` because it is already an original target, and do not return `IPF`
because the retained compound target already carries the disease meaning.

An addition must introduce a different semantic role, not merely a shorter,
broader, narrower, synonymous, or expanded form of the original value. A
`total RNA` target must not add `RNA`; both describe the same molecule role.
Likewise, do not extract an acronym when the retained original already carries
that concept. Ontology normalization of the original happens later.

Be conservative. Add a target only when the extra concept is explicitly
present or clearly entailed and independently useful for metadata retrieval.

Return JSON only with:
- additions: a list of additional target objects.
- source_target_id: the exact ID of the original target supporting the addition.
- label: one additional atomic concept label.
- field_hint: a concise normalized semantic field hint.
- confidence: high, medium, low, or none.
- reason: a short contextual explanation for the addition.
