Review the complete publication directly against the supplied theme and return one publication-level judgement.

Judge only from the supplied publication, metadata, and accession identifiers. Apply every inclusion and exclusion requirement in the theme. Use relevant when the publication establishes at least one qualifying dataset, not_relevant when it establishes none, and unsure when the available information cannot establish eligibility.

Also assess each supplied accession independently. Add an accession to accessions_to_remove only when the publication or metadata clearly establishes that the accession does not adhere to the theme, for example because it is animal-only, uses an excluded assay, or is unrelated to the qualifying samples. Do not remove an accession merely because its status is uncertain. Never invent or return an accession that was not supplied.

Return only JSON with:
- judgement: relevant, not_relevant, or unsure
- reasoning: why the publication-level judgement was given
- confidence: confidence in the publication-level judgement
- accessions_to_remove: a list of objects containing accession, reason, and confidence
