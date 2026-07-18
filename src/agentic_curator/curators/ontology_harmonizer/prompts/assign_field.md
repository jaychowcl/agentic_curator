You are assigning a harmonization target field to the best known field.

Choose the field that describes the semantic category or role of the value, not
the value itself. Interpret the original field and label as a pair, then use the
harmonized label, selected ontology term, publication context, compact metadata
context, and fields dictionary to understand the wider purpose of that pair.

For example, `molecule: total RNA` describes an extracted or sequenced molecular
material. Select an existing field such as `molecule` or `extracted_molecule`;
do not turn the value into a field named `total_rna`.

Prefer a suitable existing field. When selecting one, copy its exact field key
and set `new_field` to false. Create a concise normalized field-category key only
when no existing field represents the same role, and set `new_field` to true.

Return JSON only with:
- decision: the selected or newly created normalized field key.
- confidence: high, medium, low, or none.
- reason: a short explanation grounded in the target, context, and fields.
- new_field: true if decision creates a new fields entry, otherwise false.
