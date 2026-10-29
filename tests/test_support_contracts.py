import copy

import pytest
from jsonschema import Draft202012Validator

from closed_review.errors import ReviewError
from closed_review.support.calculators import (
    INPUT_NAMES,
    METHODS,
    PARAMETER_NAMES,
    calculate,
    reported_relation,
)
from closed_review.support.contracts import (
    answer_schema,
    calculators,
    validate_numeric_bindings,
    validate_references,
    validate_shape,
)
from closed_review.support.localization import EN, KO, labels_for
from closed_review.support.methods import MODULES


@pytest.mark.parametrize("module", list(MODULES))
@pytest.mark.parametrize("stage", ["extract", "appraise", "consolidate"])
def test_every_module_has_a_valid_explicit_contract(module, stage):
    schema = answer_schema(stage, module)
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False


def test_errors_report_multiple_paths_without_echoing_confidential_values():
    answer = {
        "task_id": "task-1",
        "assessments": [],
        "calculations": [
            {
                "method": "percentage",
                "inputs": {
                    "numerator": {"value": "2", "evidence": "PRIVATE-EVIDENCE"},
                    "denominator": {"value": "5", "evidence": []},
                },
                "method_evidence": "PRIVATE-METHOD",
                "assumptions": [],
                "reported": {"value": "1", "evidence": [], "output": "100*n/d"},
            }
        ],
    }
    with pytest.raises(ReviewError) as error:
        validate_shape(answer, "appraise", "statistics", None)
    message = str(error.value)
    assert "calculations.0.inputs.numerator.evidence: expected array" in message
    assert "calculations.0.method_evidence: expected array" in message
    assert "calculations.0.reported.output: choose one of value" in message
    assert "PRIVATE" not in message and "100*n/d" not in message


def test_calculator_contracts_do_not_leak_to_unselected_module_families():
    assert set(calculators("statistics")) == set(METHODS)
    assert set(calculators("systematic-review")) == {"count_sum", "percentage"}
    for module in ("logic", "qualitative-study", "narrative-review"):
        assert not calculators(module)
        with pytest.raises(ReviewError):
            validate_shape(
                {"task_id": "t", "assessments": [], "calculations": [{}]}, "appraise", module, None
            )


def test_english_korean_labels_have_identical_keys_and_no_raw_note_tokens():
    assert set(EN) == set(KO)
    for language in ("en", "ko", "English", "한국어"):
        labels = labels_for(language, {"calculation_note": "calculation_note"})
        assert labels["calculation_note"] != "calculation_note"
    custom = copy.deepcopy(EN)
    custom["calculation_note"] = "calculation_note"
    with pytest.raises(ReviewError, match="must explain"):
        labels_for("fr", custom)


def test_semantic_reference_errors_locate_counterevidence_without_echoing_it():
    source = {
        "blocks": [
            {
                "id": "seg-00008",
                "locator": "paragraph:1",
                "text": "PRIVATE: B and D had concerns; C had high bias.",
            }
        ],
        "tables": [],
    }
    answer = {
        "assessments": [
            {
                "evidence": [{"block_id": "seg-00008", "quote": "PRIVATE: B and D had concerns;"}],
                "counterevidence": [{"block_id": "seg-00008", "quote": "B and D had concerns."}],
            }
        ],
        "calculations": [{"method_evidence": [{"block_id": "seg-00008", "quote": "PRIVATE!"}]}],
    }
    with pytest.raises(ReviewError) as error:
        validate_references(answer, source)
    message = str(error.value)
    assert "$.assessments[0].counterevidence[0]" in message
    assert "$.calculations[0].method_evidence[0]" in message
    assert "source block seg-00008" in message
    assert "PRIVATE" not in message and "B and D" not in message
    answer["assessments"][0]["counterevidence"][0]["quote"] = "B and D had concerns;"
    answer["calculations"][0]["method_evidence"][0]["quote"] = "PRIVATE:"
    validate_references(answer, source)


def calculation(method="percentage"):
    binding = {"value": "2", "evidence": [{"block_id": "b1", "quote": "2 of 5"}]}
    return {
        "method": method,
        "inputs": {key: copy.deepcopy(binding) for key in ("numerator", "denominator")},
        "method_evidence": copy.deepcopy(binding["evidence"]),
        "assumptions": [],
    }


@pytest.mark.parametrize("value", ["Nine", "two", "90-10", "2/5", "NaN", "2\n", " 2", "２"])
def test_numeric_contract_rejects_words_expressions_and_nonliteral_tokens(value):
    raw = calculation()
    raw["inputs"]["numerator"]["value"] = value
    with pytest.raises(ReviewError, match="literal numeric token"):
        validate_shape(
            {"task_id": "t", "assessments": [], "calculations": [raw]},
            "appraise",
            "statistics",
            None,
        )


@pytest.mark.parametrize("value", ["2", "1,200", "−.5", "-2.10", "+4", "1.2e-3"])
def test_numeric_contract_accepts_supported_literal_notations(value):
    raw = calculation()
    raw["inputs"]["numerator"]["value"] = value
    validate_shape(
        {"task_id": "t", "assessments": [], "calculations": [raw]}, "appraise", "statistics", None
    )


def test_exact_method_keys_parameters_and_output_are_explicit():
    raw = calculation("count_sum")
    answer = {"task_id": "t", "assessments": [], "calculations": [raw]}
    with pytest.raises(ReviewError, match="calculations.0.inputs"):
        validate_shape(answer, "appraise", "scoping-review", None)
    raw["inputs"] = {"part_1": raw["inputs"]["numerator"]}
    validate_shape(answer, "appraise", "scoping-review", None)
    raw["method"] = "p_from_t"
    raw["inputs"] = {key: copy.deepcopy(raw["inputs"]["part_1"]) for key in ("statistic", "df")}
    raw["reported"] = copy.deepcopy(raw["inputs"]["df"])
    with pytest.raises(ReviewError) as error:
        validate_shape(answer, "appraise", "statistics", None)
    assert "parameters" in str(error.value) and "output" in str(error.value)
    raw["parameters"] = {"alternative": "two-sided"}
    raw["reported"]["output"] = "p_value"
    validate_shape(answer, "appraise", "statistics", None)
    raw["parameters"]["correction"] = False
    with pytest.raises(ReviewError, match="parameters"):
        validate_shape(answer, "appraise", "statistics", None)


def test_numeric_diagnostics_report_multiple_paths_without_echoing_evidence():
    source = {
        "blocks": [{"id": "b1", "locator": "paragraph:1", "text": "PRIVATE: 2 of 5"}],
        "tables": [],
    }
    raw = calculation()
    raw["inputs"]["numerator"]["value"] = "3"
    raw["inputs"]["denominator"]["value"] = "6"
    with pytest.raises(ReviewError) as error:
        validate_numeric_bindings({"calculations": [raw]}, source)
    assert "$.calculations[0].inputs.numerator" in str(error.value)
    assert "$.calculations[0].inputs.denominator" in str(error.value)
    assert "PRIVATE" not in str(error.value)


def test_unprinted_number_is_diagnosed_even_when_its_quote_is_also_inexact():
    source = {
        "blocks": [{"id": "b1", "locator": "paragraph:1", "text": "PRIVATE: four of 5"}],
        "tables": [],
    }
    raw = calculation()
    raw["inputs"]["numerator"] = {
        "value": "4",
        "evidence": [{"block_id": "b1", "quote": "PRIVATE: Four of 5"}],
    }
    raw["inputs"]["denominator"]["value"] = "5"
    with pytest.raises(ReviewError, match="exact reported numeric token") as error:
        validate_numeric_bindings({"calculations": [raw]}, source)
    assert "$.calculations[0].inputs.numerator" in str(error.value)
    assert "omit the ENTIRE calculation" in str(error.value)
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize("method", list(METHODS))
def test_every_calculator_has_exact_input_parameter_and_output_contracts(method):
    raw = calculation(method)
    binding = raw["inputs"]["numerator"]
    names = ["part_1", "part_2"] if method == "count_sum" else INPUT_NAMES[method].split()
    raw["inputs"] = {key: copy.deepcopy(binding) for key in names}
    raw["parameters"] = {
        key: False if key == "correction" else "two-sided"
        for key in PARAMETER_NAMES.get(method, "").split()
    }
    raw["reported"] = {**copy.deepcopy(binding), "output": METHODS[method]["outputs"][0]}
    answer = {"task_id": "t", "assessments": [], "calculations": [raw]}
    validate_shape(answer, "appraise", "statistics", None)
    raw["inputs"]["invented_name"] = copy.deepcopy(binding)
    with pytest.raises(ReviewError, match="inputs"):
        validate_shape(answer, "appraise", "statistics", None)


def test_calculator_runtime_does_not_silently_ignore_extra_parameters():
    raw = calculation()
    raw["parameters"] = {"correction": True}
    source = {"blocks": [{"id": "b1", "locator": "paragraph:1", "text": "2 of 5"}], "tables": []}
    with pytest.raises(ReviewError, match="no keys"):
        calculate(raw, source)


@pytest.mark.parametrize(
    "quote,value,expected",
    [
        ("35", "35", "="),
        ("p<0.05", "0.05", "<"),
        ("p > .05", ".05", ">"),
        ("p<=0.05", "0.05", "<="),
        ("p≥0.05", "0.05", ">="),
        ("p ≤ 0.05", "0.05", "<="),
        ("p<0.05; estimate 0.10", "0.10", "="),
        ("estimate > −0.5", "−0.5", ">"),
    ],
)
def test_source_qualifier_is_derived_from_the_bound_number_not_model_comparison(
    quote, value, expected
):
    source = {"blocks": [{"id": "b1", "text": quote}]}
    assert (
        reported_relation(
            {"value": value}, {"evidence": [{"block_id": "b1", "quote": quote}]}, source
        )
        == expected
    )


@pytest.mark.parametrize("field", ["relation", "source_operator"])
def test_models_cannot_supply_comparison_operators_in_shape_or_runtime(field):
    raw = calculation()
    raw["inputs"]["denominator"]["value"] = "5"
    raw["reported"] = {
        "value": "50",
        "evidence": [{"block_id": "b1", "quote": "50%"}],
        "output": "value",
    }
    source = {
        "blocks": [{"id": "b1", "locator": "paragraph:1", "text": "2 of 5. Reported 50%."}],
        "tables": [],
    }
    result = calculate(raw, source)
    assert result["comparison"]["status"] == "mismatch"
    assert result["comparison"]["relation"] == "="
    raw["reported"][field] = ">"
    with pytest.raises(ReviewError, match="do not supply reported.relation or source_operator"):
        validate_shape(
            {"task_id": "t", "assessments": [], "calculations": [raw]},
            "appraise",
            "statistics",
            None,
        )
    with pytest.raises(ReviewError, match="do not supply reported.relation or source_operator"):
        calculate(raw, source)


def test_ambiguous_source_qualifiers_are_refused_with_path_and_safe_omission_action():
    raw = calculation()
    raw["reported"] = {
        "value": "0.05",
        "evidence": [{"block_id": "b1", "quote": "p<0.05; estimate 0.05"}],
        "output": "value",
    }
    source = {
        "blocks": [
            {"id": "b1", "locator": "paragraph:1", "text": "PRIVATE 2 of 5; p<0.05; estimate 0.05"}
        ],
        "tables": [],
    }
    with pytest.raises(ReviewError) as error:
        validate_numeric_bindings({"calculations": [raw]}, source)
    message = str(error.value)
    assert "$.calculations[0].reported" in message and "ambiguous source qualifiers" in message
    assert "omit the ENTIRE calculation" in message
    assert "PRIVATE" not in message


def test_legacy_model_verdict_fields_are_diagnosed_for_every_calculation_together():
    raw = calculation()
    raw["reported"] = {**copy.deepcopy(raw["inputs"]["numerator"]), "relation": ">"}
    with pytest.raises(ReviewError) as error:
        validate_shape(
            {"task_id": "t", "assessments": [], "calculations": [raw, copy.deepcopy(raw)]},
            "appraise",
            "statistics",
            None,
        )
    assert "calculations.0.reported" in str(error.value)
    assert "calculations.1.reported" in str(error.value)


def test_qualified_bounds_are_not_silently_used_as_exact_calculator_inputs():
    raw = calculation()
    raw["inputs"]["numerator"]["evidence"][0]["quote"] = "events <2 of 5"
    source = {
        "blocks": [{"id": "b1", "locator": "paragraph:1", "text": "events <2 of 5; exact 2 of 5"}],
        "tables": [],
    }
    with pytest.raises(ReviewError, match="point values"):
        calculate(raw, source)


@pytest.mark.parametrize(
    "text,value,quote",
    [
        ("150", "50", "50"),
        ("-5", "5", "5"),
        ("1e-3", "-3", "-3"),
    ],
)
def test_digit_fragments_cannot_become_source_bound_numbers(text, value, quote):
    from closed_review.support.calculators import _number

    source = {"blocks": [{"id": "b1", "locator": "paragraph:1", "text": text}], "tables": []}
    with pytest.raises(ReviewError, match="complete original source token"):
        _number({"value": value, "evidence": [{"block_id": "b1", "quote": quote}]}, source)


def test_narrow_quote_cannot_hide_a_printed_source_qualifier():
    from closed_review.support.calculators import _number

    source = {"blocks": [{"id": "b1", "locator": "paragraph:1", "text": "p <0.05"}], "tables": []}
    binding = {"value": "0.05", "evidence": [{"block_id": "b1", "quote": "0.05"}]}
    with pytest.raises(ReviewError, match="point values"):
        _number(binding, source)
    _, resolved = _number(binding, source, exact=False)
    assert reported_relation(binding, resolved, source) == "<"


@pytest.mark.parametrize("value", ["1e-999999999", "9007199254740992.1", "1e999999999"])
def test_unrepresentable_literals_are_refused_without_becoming_exact_counts(value):
    from closed_review.support.calculators import _number

    source = {"blocks": [{"id": "b1", "locator": "paragraph:1", "text": value}], "tables": []}
    with pytest.raises(ReviewError, match="precision|range"):
        _number({"value": value, "evidence": [{"block_id": "b1", "quote": value}]}, source)
