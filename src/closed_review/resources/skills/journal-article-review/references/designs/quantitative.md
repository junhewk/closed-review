---
id: quantitative
applies_to: surveys and vignette studies, observational studies of records, registries, or practice data, trials of ethics interventions (decision aids, consent materials), and prediction-model studies used in clinical decisions
not_for: reviews of quantitative studies (systematic-review); open-ended responses analyzed qualitatively (qualitative); the normative conclusions drawn from the data (add normative-argument)
reporting_guidance: STROBE (von Elm et al., 2007) for observational studies; CONSORT 2010 (Schulz et al., 2010) for trials; CROSS (Sharma et al., 2021) and CHERRIES (Eysenbach, 2004) for surveys; TRIPOD+AI (Collins et al., 2024) for prediction models
version: 1
---

# Quantitative empirical research

## Recognize

Cues: a sample of people, records, or cases measured on predefined variables; percentages, means,
odds ratios, or model performance as the main result; statistical tests or models. In bioethics this
is most often an attitude or experience survey, a vignette experiment, an analysis of how often a
practice occurs, or an evaluation of an intervention such as a decision aid. When the paper goes on
to say what ought to be done, load `normative-argument` as well.

## Where it usually breaks

### Question and design
- Look in: aims, methods, the first paragraph of the discussion.
- Signals: a causal or effect question answered with a cross-sectional or uncontrolled before-after
  design; no stated estimand, so the reader cannot tell what the main number estimates; a vignette
  study whose vignettes differ in more than the factor being tested.
- Would settle it: the question restated at the level the design supports, or a design (control
  group, adjustment, randomization) that answers it.

### Sampling and response
- Look in: recruitment, sampling frame, response rate, participant table.
- Signals: a convenience, snowball, or online-panel sample described as representative; a response
  rate that is low, unreported, or computed without a stated denominator; no comparison of
  responders with non-responders; a sampling frame that leaves out groups the question concerns.
- Would settle it: the frame and response figures, a non-response analysis or weighting, or claims
  limited to the people sampled.

### Measurement
- Look in: instrument description, supplements, item wording.
- Signals: the main outcome measured with items that are leading, double-barreled, or about a
  different construct than the one claimed; an instrument translated or adapted without testing;
  attitudes to a hypothetical treated as evidence of what people do.
- Would settle it: the full instrument as a supplement, its source and any validation, and wording
  of the key items in the text.

### Analysis
- Look in: statistical methods, tables, supplements.
- Signals: many comparisons or subgroups with no correction or pre-specification, and the
  significant ones reported as findings; groups compared without adjustment for obvious
  confounders when the conclusion depends on the comparison; missing data not reported or handled
  by dropping cases without saying how many; p-values reported in place of effect sizes and
  confidence intervals; for prediction models, performance reported only in the development data.
- Would settle it: pre-specified analyses identified, adjusted estimates with intervals, the
  missing-data approach, and external or at least internal validation.

### Results and reporting
- Look in: abstract, results, tables.
- Signals: sample sizes that differ between text, tables, and abstract without explanation;
  percentages without denominators; the abstract reporting a subgroup or secondary result as the
  main finding.

### Claims
- Look in: discussion, conclusions, abstract.
- Signals: causal language ("led to", "reduces") from associations; population-level statements
  from the sample; a majority view presented as what should be done (then `normative-argument`
  applies); recommendations that need data the study did not collect.
- Proportionate fixes: restate claims at the level the design supports; name the further evidence
  needed.

### Ethics specific to quantitative data
- Signals: identifiable small cells in tables (rare conditions, small units); consent or approval
  unclear for the secondary use of records; survey items that could cause distress without support
  offered.

## Major flaws

Major when the quoted evidence shows them (see the index).

- **causal-from-association**: causal or effect conclusions drawn from observational,
  cross-sectional, or uncontrolled before-after data without a design or analysis that supports
  them.
- **unrepresentative-generalization**: population-level conclusions from a convenience, panel, or
  low-response sample, without a non-response analysis or weighting.
- **invalid-measure**: the main outcome is measured with items that do not measure the construct the
  conclusions are about.
- **unadjusted-comparison**: a conclusion rests on comparing groups that differ in obvious
  confounders, with no adjustment.
- **selective-analysis**: findings selected from many unadjusted comparisons or subgroups, or a
  prediction model's performance reported only in its development data.

## Common false alarms

- Asking for a power calculation in a descriptive survey that tests no hypothesis.
- Asking for probability sampling when the paper makes claims only about its sample.
- Treating parametric analysis of summed Likert scales as an error in itself; the practice is
  debated, so ask instead whether the conclusions depend on it.
- Asking for causal methods when the paper makes no causal claim.
- Asking for multiple-comparison correction for a few pre-specified analyses.
- Treating a reporting checklist (STROBE, CROSS) as a quality score.
- Faulting a vignette study for being hypothetical; ask only whether its claims stay at that level.

## Monitoring areas

Question and design; sampling and response; measurement; analysis; results and reporting; claims;
quantitative ethics.
