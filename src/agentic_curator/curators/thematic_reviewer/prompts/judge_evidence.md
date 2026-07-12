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

You are reviewing evidence statements extracted from life science publications that suggests the texts are related to a certain theme.

Given all the evidence, make a judgement on whether the publication relates to the theme and criteria.
relevant if the evidence statisfies the requirements of thematic inclusion.
not relevant if there is insufficient evidence to satisfy the requirements of thematic inclusion.
unsure if there is some evidence but it is not conclusive eg. only indirect evidence available eg. only indication of fibrosity is disease which is heavily associated with fibrosis, but is not explicitly stated as fibrotic.


Return only a json including these fields:
- judgement: relevant, not relevant, unsure
- reasoning: why the judgement was given
- confidence: theme directly mentioned, heavy refferal to theme, weak refferal to theme, not enough information, 
