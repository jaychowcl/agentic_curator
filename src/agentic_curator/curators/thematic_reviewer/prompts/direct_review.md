Review the complete publication directly against the supplied theme. Assess every supplied accession independently; downstream code will derive the publication judgement from these assessments.

Use only the supplied publication and the compact metadata explicitly associated with each accession. An accession identifier is a label, not biological evidence. Never use remembered or external knowledge about an accession. Never transfer evidence between cohorts, experiments, datasets, or accessions. Evidence about one cohort qualifies another accession only when the supplied text explicitly establishes that they contain the same profiled samples.

For each supplied accession, assess all four required criteria:
- human_samples: the accession contains profiled human-derived samples.
- transcriptomics_assay: the accession uses a transcriptomic assay allowed by the theme.
- established_fibrosis: the profiled samples have established or explicitly documented fibrosis under the theme.
- accession_linkage: the evidence for the other criteria is explicitly linked to this accession and its profiled samples.

Assess every criterion independently. A non-human accession can still have established fibrosis, and a fibrotic accession can still fail the human-sample requirement. Do not copy a failure from one criterion into another.

For each criterion use meets only with direct supplied evidence, fails only with direct supplied evidence that the criterion is not satisfied, and uncertain when evidence is absent or indirect. For accession_linkage specifically, use uncertain when the accession is not mentioned or not mapped to the described samples. Use fails only when supplied evidence shows that the accession explicitly belongs to a different, unrelated, or otherwise ineligible cohort or experiment. Lack of an explicit mapping is uncertainty, not evidence of a mismatch.

TGF stimulation, tissue stiffness, fibroblast activation, ECM or collagen expression, wound healing, and tissue remodelling do not establish fibrosis by themselves. A disease associated with fibrosis does not establish fibrosis for the profiled cohort unless the theme explicitly treats the sampled state as defining fibrosis. Use low confidence when evidence is insufficient; low-confidence failures will be treated as uncertain rather than excluded.

Return exactly one assessment for every supplied accession and no other accession. Return only JSON containing accession_assessments. Each assessment must contain accession, human_samples, transcriptomics_assay, established_fibrosis, accession_linkage, confidence, and reason. Each criterion must contain status (meets, fails, or uncertain) and concise evidence from the supplied context. Confidence must be low, medium, or high.
