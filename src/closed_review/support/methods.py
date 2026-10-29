"Versioned, applicability-bound criteria, not an automatic major-flaw catalogue."

from __future__ import annotations

from typing import Any


def _module(
    family: str, roles: str, criteria: dict[str, str], guidance: list[str], limits: str
) -> dict[str, Any]:
    return {
        "version": 2,
        "family": family,
        "roles": roles.split(),
        "criteria": criteria,
        "guidance": guidance,
        "limits": limits,
    }


MODULES = {
    "statistics": _module(
        "statistical",
        ("population outcome analysis result table_definition interpretation"),
        {
            "population": (
                "Identify analysis populations, units, denominators, "
                "exclusions, timepoints and missingness before comparing "
                "numbers."
            ),
            "tables": (
                "Trace headers, footnotes, units, text/table/abstract "
                "correspondence. Weighted and multiple-response percentages "
                "need different rules."
            ),
            "calculation": (
                "Recalculate only from sufficient source-bound inputs using "
                "the declared variant. Rounded summaries yield conditional "
                "comparisons."
            ),
            "test_fit": (
                "Assess compatibility of the reported test with outcome, "
                "independent/paired/clustered structure, estimand and stated "
                "assumptions. Unknown diagnostics are not failed assumptions."
            ),
            "analysis": (
                "Assess reported adjustment, missing-data handling and "
                "multiplicity in relation to the actual aim. Do not demand a "
                "preferred redesign or universal correction."
            ),
            "interpretation": (
                "Compare direction, magnitude, uncertainty and stated "
                "conclusions. Distinguish statistical support from "
                "causality, clinical importance and proof of no effect."
            ),
        },
        [
            (
                "SAMPL (Lang & Altman, 2013): "
                "https://www.equator-network.org/2013/02/11/sampl-guidelines-"
                "for-statistical-reporting/"
            ),
            (
                "CONSORT 2025 / STROBE, when applicable: "
                "https://www.equator-network.org/reporting-guidelines/"
            ),
        ],
        (
            "No raw data, diagnostics, adjusted-model reconstruction or "
            "unsupported meta-analysis replay. No automatic test choice "
            "based only on sample size."
        ),
    ),
    "qualitative-study": _module(
        "qualitative",
        (
            "approach sampling participant relationship generation "
            "coding theme quotation interpretation"
        ),
        {
            "approach": (
                "Reconstruct question, epistemological/methodological "
                "approach and congruity of the reported procedures. "
                "Qualitative description is legitimate."
            ),
            "participants": (
                "Reconstruct participant selection, composition, recruitment "
                "and sample-adequacy rationale for this question; do not "
                "demand representativeness or statistical power."
            ),
            "reflexivity": (
                "Identify researcher position, relationships and handling of "
                "influence; subjectivity itself is not an error."
            ),
            "generation": (
                "Examine reported interview/observation procedures, "
                "instruments, recording/transcription and "
                "language/translation."
            ),
            "coding": (
                "Trace the reported path from material to "
                "codes/categories/themes and who did what. No unavailable "
                "transcript or coding-record validation."
            ),
            "themes": (
                "Assess displayed quotations, theme meanings, interpretive "
                "explanation and represented variation. Do not impose "
                "counting or a single uniquely correct reading."
            ),
            "validation": (
                "Judge quality practices in the declared tradition. Kappa, "
                "consensus coding, saturation and member checking are not "
                "universal requirements, especially in reflexive thematic "
                "analysis."
            ),
            "claims": (
                "Assess conclusions and transferability against the "
                "participants, context and evidence actually presented."
            ),
        },
        [
            (
                "SRQR (2014), COREQ (2007), reporting: "
                "https://www.equator-network.org/reporting-guidelines/"
            ),
            ("JBI qualitative critical appraisal: https://jbi.global/critical-appraisal-tools"),
            (
                "Braun & Clarke, approach-specific thematic analysis: "
                "https://www.thematicanalysis.net/editor-checklist/"
            ),
        ],
        (
            "Manuscript-only appraisal of reporting and displayed "
            "evidence; cannot re-code or certify original interviews."
        ),
    ),
    "systematic-review": _module(
        "qualitative",
        (
            "question eligibility protocol search selection extraction "
            "appraisal synthesis finding interpretation"
        ),
        {
            "question": (
                "Identify the review subtype and congruity of question, "
                "eligibility, included designs and synthesis; PICO is not "
                "mandatory for every subtype."
            ),
            "protocol": (
                "Identify reported protocol, registration and explained "
                "deviations; an unavailable protocol cannot be compared or "
                "silently assumed absent."
            ),
            "search": (
                "Examine reported search sources, dates, strategies and "
                "limits in relation to the question, without claiming "
                "independent search completeness."
            ),
            "selection": (
                "Check reported selection procedures, flow counts, reasons, "
                "and distinction between reports and studies; count "
                "arithmetic needs explicit exclusivity."
            ),
            "appraisal": (
                "Assess whether the stated appraisal approach fits included "
                "designs and how it affects synthesis. Do not apply "
                "intervention-review tools to normative reviews "
                "indiscriminately."
            ),
            "synthesis": (
                "Assess extraction units, comparability, synthesis method, "
                "context and content fit. For qualitative synthesis separate "
                "participant words, primary interpretations and review "
                "interpretations."
            ),
            "conclusions": (
                "Examine whether the displayed findings and stated "
                "uncertainty support the conclusion; do not independently "
                "certify included papers or unseen evidence."
            ),
        },
        [
            "PRISMA 2020, reporting: https://www.prisma-statement.org/",
            (
                "AMSTAR 2 (2017), healthcare intervention reviews only: "
                "https://amstar.ca/Amstar_Checklist.php"
            ),
            ("JBI evidence synthesis: https://jbi.global/critical-appraisal-tools"),
        ],
        (
            "No new literature search, independent inclusion decisions, "
            "full-text verification or automatic checklist quality score."
        ),
    ),
    "scoping-review": _module(
        "qualitative",
        ("question eligibility search selection charting source synthesis interpretation"),
        {
            "question": (
                "Identify the mapping question and "
                "population/concept/context where applicable; distinguish "
                "mapping from effectiveness inference."
            ),
            "search": (
                "Examine reported sources, dates, strategy and "
                "question-relevant limits; independent completeness cannot "
                "be established."
            ),
            "selection": (
                "Trace eligibility, screening, flow and source/report counts "
                "using manuscript evidence."
            ),
            "charting": (
                "Trace charted concepts, categories and extraction "
                "procedures to the mapping question."
            ),
            "appraisal": (
                "Check the stated role of critical appraisal if performed; "
                "absence is not automatically a flaw in a scoping review."
            ),
            "synthesis": (
                "Assess mapping categories, context preservation, conceptual "
                "drift and whether synthesis answers the actual question."
            ),
            "conclusions": (
                "Check whether conclusions stay within the mapping performed "
                "rather than assuming effectiveness or certainty."
            ),
        },
        [
            "PRISMA-ScR (2018): https://www.prisma-statement.org/scoping",
            ("JBI scoping review methodology: https://jbi.global/scoping-review-network"),
        ],
        (
            "Do not impose systematic-effectiveness-review, "
            "meta-analysis, GRADE or mandatory risk-of-bias requirements."
        ),
    ),
    "narrative-review": _module(
        "qualitative",
        ("question approach selection source concept synthesis interpretation"),
        {
            "purpose": (
                "Reconstruct the review's importance, aim, scope and intended contribution."
            ),
            "approach": (
                "Assess the explained approach to literature selection and "
                "organization relative to the stated purpose; do not demand "
                "SR procedures merely because this is a review."
            ),
            "content": (
                "Trace conceptual categories and the reasoning connecting "
                "selected material; identify internal selection imbalance "
                "only where evidenced in the manuscript."
            ),
            "evidence": (
                "Distinguish empirical evidence, examples, author "
                "interpretation and cited but unread sources; no independent "
                "completeness or source-validity certificate."
            ),
            "conclusions": (
                "Assess whether the presented argument and evidence support "
                "the scope and strength of the conclusions."
            ),
        },
        [
            (
                "SANRA (2019), appraisal-informed criteria without automated "
                "scoring: https://pmc.ncbi.nlm.nih.gov/articles/PMC6434870/"
            )
        ],
        (
            "No automatic SANRA score, systematic-search requirement or "
            "verification of unread cited articles."
        ),
    ),
    "logic": _module(
        "logic",
        (
            "question definition approach empirical_premise "
            "legal_premise normative_premise conclusion objection reply"
        ),
        {
            "approach": (
                "Reconstruct the actual ethical/legal/perspective question, "
                "framework and approach, rather than requiring an empirical "
                "design."
            ),
            "definitions": (
                "Trace definitions, actors, jurisdictions, populations, time "
                "and conditions; examine consequential changes in meaning or "
                "scope."
            ),
            "premises": (
                "Separate empirical, legal and normative premises, stated "
                "versus inferred assumptions, and descriptive versus "
                "evaluative claims."
            ),
            "connections": (
                "Assess whether conclusions follow under the stated "
                "premises; expose bridging assumptions rather than demanding "
                "a universally accepted moral position."
            ),
            "evidence": (
                "Assess how evidence is represented and used. Unread "
                "studies/authorities remain unchecked; citation identity or "
                "quotation matching does not validate their substance."
            ),
            "objections": (
                "Reconstruct objections, rebuttals, exceptions and "
                "qualifications actually present; don't invent a straw "
                "argument or require every possible objection."
            ),
            "conclusions": (
                "Assess consistency and proportionality of recommendations "
                "under the author's approach and evidence; disagreement "
                "alone is not a methodological defect."
            ),
        },
        [
            (
                "Structured source-grounded argument reconstruction, local "
                "protocol v1; not a universal ethics/legal checklist."
            )
        ],
        (
            "No formal validity certificate, moral verdict, current-law "
            "verification or independent factual validation of unread "
            "authorities."
        ),
    ),
}

RELATIONS = {
    "supports",
    "contradicts",
    "qualifies",
    "depends_on",
    "replies_to",
    "reports",
    "analyses",
}
STATUSES = {"supported", "concern", "not_located", "not_assessable", "not_applicable"}
KINDS = {"calculated_discrepancy", "reporting_gap", "methodological_concern", "not_assessable"}

ARTICLE_ROUTES = {
    "clinical-trial": ["statistics"],
    "observational-study": ["statistics"],
    "diagnostic-study": ["statistics"],
    "prognostic-study": ["statistics"],
    "qualitative-study": ["qualitative-study"],
    "systematic-review": ["systematic-review"],
    "meta-analysis": ["systematic-review", "statistics"],
    "scoping-review": ["scoping-review"],
    "narrative-review": ["narrative-review"],
    "mixed-methods": ["statistics", "qualitative-study"],
    "legal-analysis": ["logic"],
    "normative-perspective": ["logic"],
}


def route_modules(article_type: str) -> dict[str, Any]:
    from ..errors import ReviewError

    if article_type not in ARTICLE_ROUTES:
        raise ReviewError("unknown article type; choose one of: " + ", ".join(ARTICLE_ROUTES))
    return {
        "article_type": article_type,
        "suggested_modules": ARTICLE_ROUTES[article_type],
        "starts_run": False,
        "reviewer_scope_required": True,
        "note": "Advisory routing only. Select the requested focus explicitly; never infer a "
        "full review or run every branch. Add logic only when that is the requested focus.",
    }


def catalogue() -> dict[str, Any]:
    return {
        "protocol": "medical-methods-v1",
        "modules": MODULES,
        "article_routes": ARTICLE_ROUTES,
        "note": ("Select modules explicitly. Guidance is packaged, never fetched during review."),
    }
