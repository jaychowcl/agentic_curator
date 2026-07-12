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

You are choosing the best ontology lookup hit for a harmonization target.

Use the publication context, compact metadata context, target context, and
candidate hits to select the single best hit. Return JSON only with:
- decision: the selected hit id.
- confidence: high, medium, low, or none.
- reason: a short explanation grounded in the context and candidate hits.
