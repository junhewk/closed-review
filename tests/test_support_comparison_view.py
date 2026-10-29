"""The static comparison view exposes saved arithmetic, not new reviewer verdicts."""

import copy
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

import pytest
from test_support import begin, bound_percentage, finish
from test_support import support_env as support_env

from closed_review.errors import ReviewError
from closed_review.io import read_json
from closed_review.receipts import verify_receipt
from closed_review.support.calculators import METHODS, calculate
from closed_review.support.localization import COMPARISON_LABELS, EN, KO, labels_for
from closed_review.support.render import export, render
from closed_review.support.workflow import _root

INPUTS = {
    "count_sum": {"part_1": "20", "part_2": "30"},
    "percentage": {"numerator": "1", "denominator": "3"},
    **{
        name: dict(a="20", b="80", c="10", d="90")
        for name in (
            "ratios_2x2",
            "pearson_2x2",
            "fisher_2x2",
        )
    },
    **{
        name: dict(mean1="10", sd1="2", n1="20", mean2="8", sd2="2", n2="20")
        for name in ("student_t", "welch_t")
    },
    "p_from_z": {"statistic": "1.96"},
    "p_from_t": {"statistic": "2", "df": "20"},
    "p_from_chi2": {"statistic": "3", "df": "1"},
    "p_from_f": {"statistic": "3", "dfn": "1", "dfd": "20"},
    "normal_ci": {"estimate": "10", "se": "1", "confidence_percent": "95"},
    "t_ci": {"estimate": "10", "se": "1", "confidence_percent": "95", "df": "20"},
}


def replay(method="percentage", *, agrees=True, reported=True, relation="=", token=None):
    """Make a real source-bound replay; never hardcode its comparison verdict."""
    identifier = "source-" + method
    text = "Declared method. Unweighted mutually exclusive counts. " + "; ".join(
        f"{key}={value}" for key, value in INPUTS[method].items()
    )
    source = {"blocks": [{"id": identifier, "locator": "paragraph:1", "text": text}], "tables": []}

    def binding(value, quote):
        return {"value": value, "evidence": [{"block_id": identifier, "quote": quote}]}

    raw = {
        "method": method,
        "inputs": {key: binding(value, f"{key}={value}") for key, value in INPUTS[method].items()},
        "method_evidence": [{"block_id": identifier, "quote": "Declared method."}],
        "assumptions": ["Input roles are provisional, not certified by this replay."],
    }
    if method == "pearson_2x2":
        raw["parameters"] = {"correction": False}
    if method in {"fisher_2x2", "student_t", "welch_t", "p_from_z", "p_from_t"}:
        raw["parameters"] = {"alternative": "two-sided"}
    initial = calculate(raw, source)
    if reported:
        output, value = next(iter(initial["outputs"].items()))
        token = token if token is not None else f"{value if agrees else value + 1:.6f}"
        quote = f"Reported {output} {relation} {token}"
        source["blocks"][0]["text"] += ". " + quote + "."
        raw["reported"] = {**binding(token, quote), "output": output}
    result = calculate(raw, source)
    result["id"] = "statistics-c-" + method
    return result, source


def dossier(calculations=(), *, language="en", labels=None, module="statistics"):
    return {
        "language": language,
        "resolved_language": language,
        "revision": 1,
        "tasks": [],
        "cursor": 0,
        "source": {"sha256": "a" * 64, "blocks": [], "tables": [], "warnings": []},
        "modules": {
            module: {
                "status": "complete",
                "title": "Bounded module",
                "summary": "No certification.",
                "provided_blocks": [],
                "facts": [],
                "connections": [],
                "observations": [],
                "criteria": [],
                "withdrawn": [],
                "failures": [],
                "calculations": list(calculations),
                "labels": labels if labels is not None else labels_for(language),
            }
        },
        "notes": [
            {
                "observation_id": "run",
                "disposition": "note",
                "verified": False,
                "words": "Reviewer-owned words, not a model judgment.",
            }
        ],
    }


class View(HTMLParser):
    """Read rendered cells, active elements and anchor ancestors without executing anything."""

    def __init__(self, document):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.targets = {}
        self.elements = []
        self.overview = False
        self.rows = []
        self.cell = None
        self.links = []
        self.details = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if attrs.get("id"):
            assert attrs["id"] not in self.targets
            self.targets[attrs["id"]] = list(self.stack)
        if tag == "table" and attrs.get("class") == "calculation-overview":
            self.overview = True
        if self.overview and tag == "tr":
            self.rows.append([])
        if self.overview and tag in {"td", "th"}:
            self.cell = []
        if tag == "br" and self.cell is not None:
            self.cell.append(" ")
        if self.overview and tag == "a":
            self.links.append(attrs["href"])
        if tag == "details":
            self.details.append(attrs)
        if tag not in {"meta", "br"}:
            self.stack.append((tag, attrs))

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.overview and tag in {"td", "th"}:
            self.rows[-1].append("".join(self.cell))
            self.cell = None
        if tag == "table":
            self.overview = False
        assert self.stack[-1][0] == tag
        self.stack.pop()


@pytest.mark.parametrize("method", list(METHODS))
@pytest.mark.parametrize("agrees", [True, False])
def test_all_calculators_expose_saved_comparison_without_creating_findings(method, agrees):
    calculation, source = replay(method, agrees=agrees)
    assert calculation["comparison"]["numerical_match"] is agrees
    run = dossier([calculation])
    run["source"]["blocks"] = source["blocks"]
    before = copy.deepcopy(run)
    document, markdown, notes = render(run)
    view = View(document)
    row = view.rows[1]
    comparison = calculation["comparison"]
    assert row == [
        f"{calculation['id']} {method}",
        comparison["output"],
        "= " + comparison["reported"]["value"],
        str(calculation["outputs"][comparison["output"]]),
        EN["numerically_matches" if agrees else "numerically_differs"],
        EN[comparison["status"]],
    ]
    if method not in {"percentage", "count_sum"}:
        assert row[-1] == EN["conditional"]
    assert run == before
    assert not run["modules"]["statistics"]["observations"]
    assert notes.count("Reviewer") == 2
    assert document.index(EN["comparison_overview"]) < document.index(EN["reconstruction"])
    raw_json = json.dumps(calculation, ensure_ascii=False, indent=2)
    assert html.escape(raw_json, quote=True) in document
    assert source["blocks"][0]["text"] in html.unescape(document)
    # GFM header, separator and data must be contiguous, not separated by blank paragraphs.
    table = next(part for part in markdown.split("\n\n") if part.startswith("| "))
    assert len(table.splitlines()) == 3
    assert table.splitlines()[1] == "| --- | --- | --- | --- | --- | --- |"
    target = unquote(view.links[0][1:])
    assert target == "calculation-" + calculation["id"]
    assert not any(tag == "details" for tag, _ in view.targets[target])
    assert {"class": "calculation-details"} in view.details
    assert EN["calculation_details"] in document
    overview = next(
        attrs for tag, attrs in view.elements if attrs.get("class") == "calculation-overview"
    )
    assert overview["tabindex"] == "0"
    assert overview["aria-label"] == EN["comparison_overview"]


def test_calculation_order_is_preserved_without_quota_sorting_or_filtering():
    calculations = [replay(method, agrees=(i % 2 == 0))[0] for i, method in enumerate(METHODS)]
    document, markdown, _ = render(dossier(calculations))
    view = View(document)
    assert len(view.rows) == 1 + len(METHODS)
    assert [row[0] for row in view.rows[1:]] == [f"{c['id']} {c['method']}" for c in calculations]
    table = next(part for part in markdown.split("\n\n") if part.startswith("| "))
    assert len(table.splitlines()) == len(calculations) + 2


@pytest.mark.parametrize("relation,token,agrees", [("<", ".01", False), ("≤", ".05", True)])
def test_inequality_comparison_keeps_relation_and_conditional_status(relation, token, agrees):
    calculation, _ = replay("p_from_z", relation=relation, token=token)
    row = View(render(dossier([calculation]))[0]).rows[1]
    assert row[2] == calculation["comparison"]["relation"] + " " + token
    assert row[-2] == EN["numerically_matches" if agrees else "numerically_differs"]
    assert row[-1] == EN["conditional"]


@pytest.mark.parametrize("token", ["3.0e1", "+30.00", "1,200", "−.5", ".30"])
def test_reported_numeric_tokens_are_not_reformatted(token):
    calculation, _ = replay(token=token)
    document, markdown, _ = render(dossier([calculation]))
    assert View(document).rows[1][2] == "= " + token
    assert calculation["comparison"]["reported"]["value"] == token
    # Markdown punctuation escapes change syntax, not the displayed numeric token.
    assert token in re.sub(r"\\([\\`*_{}\[\]()#+.!|>-])", r"\1", markdown)


def test_uncompared_replays_show_all_saved_outputs_without_an_implied_match():
    calculation, _ = replay("ratios_2x2", reported=False)
    row = View(render(dossier([calculation]))[0]).rows[1]
    assert row[1] == "odds_ratio, risk_ratio"
    assert row[2] == row[-2] == row[-1] == EN["not_compared"]
    assert row[3] == "; ".join(f"{k}: {v}" for k, v in calculation["outputs"].items())


@pytest.mark.parametrize("status", ["match", "mismatch", "conditional"])
@pytest.mark.parametrize("saved", [None, "false", 1])
def test_missing_or_nonboolean_agreement_is_never_inferred_from_status(status, saved):
    calculation, _ = replay()
    calculation["comparison"].pop("numerical_match")
    calculation["comparison"]["status"] = status
    if saved is not None:
        calculation["comparison"]["numerical_match"] = saved
    row = View(render(dossier([calculation]))[0]).rows[1]
    assert row[-2] == EN["agreement_unrecorded"]
    assert row[-1] == EN[status]


@pytest.mark.parametrize("language", ["en", "English", "en-US", "ko", "한국어", "ko-KR"])
def test_historical_builtin_labels_gain_display_defaults_without_mutating_snapshot(language):
    original = labels_for(language)
    historical = {k: v for k, v in original.items() if k not in COMPARISON_LABELS}
    run = dossier([replay()[0]], language=language, labels=historical)
    before = copy.deepcopy(run)
    document, markdown, _ = render(run)
    assert original["comparison_overview"] in document
    assert original["numerical_agreement"] in markdown
    assert run == before
    assert f"<html lang='{'ko' if language in {'ko', '한국어', 'ko-KR'} else 'en'}'>" in document


@pytest.mark.parametrize("missing", ["one", "all", "no-labels"])
def test_historical_custom_language_keeps_detail_only_view_without_inventing_translations(missing):
    labels = {k: "custom " + v for k, v in EN.items()}
    if missing == "one":
        labels.pop(COMPARISON_LABELS[0])
    elif missing == "all":
        labels = {k: v for k, v in labels.items() if k not in COMPARISON_LABELS}
    else:
        labels = {}
    run = dossier([replay()[0]], language="fr", labels=labels)
    before = copy.deepcopy(run)
    document, markdown, _ = render(run)
    assert not View(document).rows
    assert "calculation-overview" not in document
    assert "calculation-details" not in document
    assert EN["comparison_overview"] not in markdown
    assert run == before


def test_new_custom_language_uses_only_supplied_labels_and_requires_the_extended_contract():
    custom = {k: "custom " + v for k, v in EN.items()}
    document, markdown, _ = render(dossier([replay()[0]], language="fr", labels=custom))
    assert "custom " + EN["comparison_overview"] in document
    assert "custom " + EN["numerical_agreement"] in markdown
    assert View(document).rows
    labels_for("fr", custom)
    for key in COMPARISON_LABELS:
        incomplete = {k: v for k, v in custom.items() if k != key}
        with pytest.raises(ReviewError, match="provide all navigation labels"):
            labels_for("fr", incomplete)


@pytest.mark.parametrize(
    "module",
    [
        "statistics",
        "qualitative-study",
        "systematic-review",
        "scoping-review",
        "narrative-review",
        "logic",
    ],
)
def test_empty_calculations_do_not_add_a_comparison_section(module):
    document, markdown, _ = render(dossier(module=module))
    assert not View(document).rows
    assert EN["comparison_overview"] not in document + markdown


def test_hostile_display_strings_are_inert_and_calculation_links_cannot_inject_markup():
    calculation, _ = replay()
    hostile = '</td><script src="https://external.invalid/a">alert(1)</script> | * [x](https://x)'
    calculation["id"] = hostile
    calculation["method"] = hostile
    calculation["outputs"]["value"] = hostile
    calculation["comparison"]["reported"]["value"] = hostile
    calculation["assumptions"] = [hostile]
    custom = {**EN, "comparison_overview": hostile}
    document, markdown, _ = render(dossier([calculation], labels=custom))
    view = View(document)
    assert not {tag for tag, _ in view.elements} & {"script", "iframe", "img", "form", "input"}
    assert not any(key.startswith("on") for _, attrs in view.elements for key in attrs)
    assert all(attrs.get("href", "#").startswith("#") for _, attrs in view.elements)
    assert unquote(view.links[0][1:]) in view.targets
    assert html.escape(hostile, quote=True) in document
    assert '<script src="https://external.invalid/a">' not in markdown
    table = next(part for part in markdown.split("\n\n") if part.startswith("| "))
    assert len(table.splitlines()) == 3
    assert r"\|" in table and r"\*" in table


def test_new_export_keeps_full_saved_run_original_source_and_reviewer_record(support_env):
    run_id = begin(support_env)
    run = finish(run_id, calculations=[bound_percentage(run_id)], withdraw_calculations=True)
    root = _root(run_id)
    before = (root / "run.json").read_bytes()
    result = export(run_id)
    directory = Path(result["directory"])
    assert (root / "run.json").read_bytes() == before
    assert read_json(directory / "support.json") == run
    assert verify_receipt(directory / "receipt.json")["verified"]
    view = View(Path(result["html"]).read_text())
    assert len(view.rows) == 2
    state = run["modules"]["statistics"]
    assert not state["observations"] and len(state["withdrawn"]) == 1
    assert view.rows[1][-2] == EN["numerically_differs"]
    assert view.rows[1][-1] == EN["mismatch"]
    assert EN.keys() == KO.keys()
