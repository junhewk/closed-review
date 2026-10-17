---
id: systematic-review
applies_to: systematic reviews and meta-analyses; qualitative evidence syntheses; systematic reviews of reasons, arguments, or normative literature
not_for: mapping questions without appraisal or synthesis of findings (scoping-review); unsystematic narrative reviews
reporting_guidance: PRISMA 2020 (Page et al., 2021); PRISMA-S for searches (Rethlefsen et al., 2021); ENTREQ (Tong et al., 2012) and eMERGe (France et al., 2019) for qualitative synthesis; AMSTAR 2 and ROBIS for appraising reviews
version: 2
---

# Systematic review

## Recognize

Cues: a focused question, protocol or registration, a reproducible search, explicit eligibility,
appraisal of included studies, a synthesis of their findings. Identify the variant first; the notes
at the end change what counts as a problem.

## Where it usually breaks

### Question, protocol, and review type
- Look in: introduction, methods, registration record.
- Signals: no protocol, or a protocol registered after the search; unexplained changes from the
  protocol (outcomes, eligibility, synthesis); a question that a scoping review would answer better.
- Would settle it: registration details, a list of deviations with reasons.

### Search
- Look in: methods, supplementary search strategies, flow diagram.
- Signals: no full strategy for any database; a set of sources that misses part of the field's
  literature (bioethics spreads across biomedical, philosophy, law, and social-science indexes, and no
  single one covers it; for Korean contexts add KCI, RISS, or KoreaMed); language limits that matter
  for the question; a search date long before submission; no grey literature where it matters.
- Would settle it: full strategies, search dates, a justification of sources and limits, or an
  updated search.

### Selection
- Look in: eligibility criteria, flow diagram, exclusion list.
- Signals: criteria that cannot be applied consistently; single screening without justification;
  flow numbers that do not add up; full-text exclusions without reasons.

### Extraction and appraisal
- Look in: methods, appraisal tables, supplements.
- Signals: single extraction; an appraisal tool that does not match the included designs; appraisal
  reported but not used in synthesis or interpretation; multiple reports of one study counted twice.
- Would settle it: the tool per design, and how appraisal shaped synthesis or certainty.

### Synthesis
- Look in: methods, forest plots, synthesis tables.
- Signals: pooling across clearly different populations, interventions, or outcomes; fixed-effect
  models despite heterogeneity, or random effects with very few studies and no caution; I² read as an
  amount of heterogeneity in absolute terms; no prediction interval where it would change the reading;
  unit-of-analysis errors (shared control arms, cluster trials); "narrative synthesis" with no stated
  method, or vote counting by significance.
- Would settle it: a pre-specified rationale for pooling, sensitivity analyses, or a structured
  narrative synthesis method (such as SWiM).

### Certainty and conclusions
- Look in: results, discussion, abstract.
- Signals: no certainty assessment (GRADE for effects, GRADE-CERQual for qualitative findings) where
  one applies; conclusions stronger than the certainty; abstract spin.

## Variant notes

### Qualitative evidence synthesis
- Check the synthesis approach (thematic synthesis, meta-ethnography, framework synthesis) and that it
  was followed; whether findings separate participants' words, primary authors' interpretations, and
  the reviewers' own interpretations; how context was kept when combining studies.

### Review of reasons, arguments, or normative literature
A review of reasons answers a factual question about the literature: which reasons have been given
for or against the view that X is permissible. It does not weigh reasons or answer the ethical
question itself.
- Question and eligibility: the question names the action or policy and, where it matters, whether
  the requirement is moral or legal; eligibility captures all and only publications that give
  reasons on it; language and date limits are justified.
- Search: sources span medicine, law, ethics, and theses where relevant; hand-searching and
  reference checking, since argument-based literature is poorly indexed.
- Extraction: the unit is clear (in the Strech and Sofaer model, a reason mention is a passage that
  expresses a reason, grouped into narrow reason types within broad ones); each mention is coded for
  the implication it is said to have (for, against, unclear) and the author's attitude to it;
  coding is independent and duplicated; a publication's all-things-considered conclusion is recorded
  separately from its individual reasons.
- Presentation: a list of reason types with their direction; publication characteristics; counts,
  if any, after removing repeats within a publication and with a sensitivity check across narrow and
  broad types.
- Signals: frequency of a reason presented or read as its strength; reasons weighed or ranked without
  the separate analysis that would require (load `normative-argument` if the review goes on to
  recommend); reason types so coarse or arbitrary that counts mean little; the reviewers' own stance
  shaping coding without acknowledgment.
- Appraisal: the Strech and Sofaer model deliberately does not appraise reasons; McCullough,
  Coverdale and Chervenak (2004) propose quality weighting instead. Ask which approach was taken
  and why. Checking whether factual premises in the reasons are evidence-based is a legitimate way
  to identify gaps.
- Sources the reviewer may wish to consult: Strech and Sofaer (2012, J Med Ethics 38:121-126);
  Sofaer and Strech (2012, Bioethics) on the need for such reviews; Mertz, Kahrass and Strech (2016)
  on ethics literature synthesis.

## Major flaws

Major when the quoted evidence shows them (see the index).

- **frequency-as-weight**: in a review of reasons, how often a reason is cited is presented or read
  as its strength, or reasons are weighed or ranked without the separate analysis that would
  require.
- **single-review**: single screening or single extraction without justification, or described
  elsewhere in the paper as independent duplicate review.
- **undisclosed-deviation**: unexplained changes from the protocol in outcomes, eligibility, or
  synthesis.
- **inappropriate-pooling**: pooling across clearly different populations, interventions, or
  outcomes, or vote counting by significance.
- **conclusions-beyond-certainty**: conclusions or abstract claims stronger than the certainty of
  the included evidence.

## Common false alarms

- Asking for a meta-analysis when heterogeneity makes pooling inappropriate.
- Asking for funnel plots or small-study tests with fewer than about ten studies.
- Asking for PROSPERO registration of a review type it does not accept; OSF or another registry is fine.
- Asking for risk-of-bias tools for normative or argument-based literature. How to appraise it is
  contested; ask instead how quality was judged, if at all, and how that was used.
- Asking for GRADE for questions that are not about effects.
- Treating an English-only limit as fatal without saying why it matters for this question.

## Monitoring areas

Question and protocol; search; selection; extraction and appraisal; synthesis; certainty and
conclusions; variant-specific checks.
