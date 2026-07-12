<!--
=============================================================================
Authors
=============================================================================
Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
https://github.com/jaychowcl
https://saezlab.org
https://www.gsk.com/
=============================================================================
-->

You are assigning a harmonization target field to the best known field.

Use the harmonization target, publication context, compact metadata context, and
fields dictionary to choose one existing field key or create one new normalized
field key.

Return JSON only with:
- decision: the selected or newly created normalized field key.
- confidence: high, medium, low, or none.
- reason: a short explanation grounded in the target, context, and fields.
- new_field: true if decision creates a new fields entry, otherwise false.
