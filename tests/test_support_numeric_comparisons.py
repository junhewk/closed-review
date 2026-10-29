"""Printed precision is not a universal epsilon, and count arithmetic stays exact."""

from decimal import Decimal, localcontext

import pytest

from closed_review.errors import ReviewError
from closed_review.support.calculators import calculate


def proposal(method, inputs, reported=None, *, output="value", relation="="):
    clauses = [f"{key}={value}" for key, value in inputs.items()]
    if reported is not None:
        clauses.append(f"reported {output} {relation} {reported}")
    source = {
        "blocks": [
            {"id": "b1", "locator": "paragraph:1", "text": "Declared method. " + "; ".join(clauses)}
        ],
        "tables": [],
    }

    def binding(value, quote):
        return {"value": value, "evidence": [{"block_id": "b1", "quote": quote}]}

    raw = {
        "method": method,
        "inputs": {key: binding(value, f"{key}={value}") for key, value in inputs.items()},
        "method_evidence": [{"block_id": "b1", "quote": "Declared method."}],
        "assumptions": ["Synthetic arithmetic input roles, not medical validation."],
    }
    if method == "p_from_z":
        raw["parameters"] = {"alternative": "two-sided"}
    if reported is not None:
        raw["reported"] = {
            **binding(reported, f"reported {output} {relation} {reported}"),
            "output": output,
        }
    return raw, source


@pytest.mark.parametrize(
    "statistic,reported,agrees",
    [
        ("7.2", "1e-30", False),
        ("7.2", "6.0e-13", True),
        ("7.2", "0.00000000000060", True),
        ("7.2", "7.0e-13", False),
        ("40", "5e-324", False),
        ("40", "0.00", True),
        ("0", "1.00", True),
    ],
)
def test_tiny_probabilities_follow_reported_precision_not_an_absolute_epsilon(
    statistic,
    reported,
    agrees,
):
    raw, source = proposal("p_from_z", {"statistic": statistic}, reported, output="p_value")
    result = calculate(raw, source)
    comparison = result["comparison"]
    assert comparison["numerical_match"] is agrees
    assert comparison["status"] == "conditional"
    assert comparison["reported"]["value"] == reported
    assert comparison["comparison_basis"] == "saved-float-decimal-v1"
    if reported == "5e-324":
        assert comparison["rounding_tolerance_decimal"] == "5E-325"
        assert comparison["rounding_tolerance"] == 0.0


@pytest.mark.parametrize(
    "relation,reported,agrees",
    [
        ("<", "1e-30", False),
        (">", "1e-30", True),
        ("≤", "6.1e-13", True),
        (">=", "6.0e-13", True),
    ],
)
def test_source_inequalities_are_not_changed_to_point_values_or_epsilon_comparisons(
    relation,
    reported,
    agrees,
):
    raw, source = proposal(
        "p_from_z", {"statistic": "7.2"}, reported, output="p_value", relation=relation
    )
    comparison = calculate(raw, source)["comparison"]
    assert comparison["numerical_match"] is agrees
    assert comparison["status"] == "conditional"


def test_a_precise_printed_bound_is_not_rounded_to_the_computed_float():
    raw, source = proposal("p_from_z", {"statistic": "1.96"})
    computed = calculate(raw, source)["outputs"]["p_value"]
    with localcontext() as context:
        context.prec = 100
        reported = format(Decimal(str(computed)) + Decimal("1e-40"), "f")
    assert float(reported) == computed
    raw, source = proposal(
        "p_from_z", {"statistic": "1.96"}, reported, output="p_value", relation="<"
    )
    assert calculate(raw, source)["comparison"]["numerical_match"] is True


@pytest.mark.parametrize(
    "numerator,denominator,reported,agrees",
    [
        ("1", "3", "33.3", True),
        ("1", "3", "33.33333333333333", True),
        ("1", "3", "33.33333333333334", False),
        ("1", "40", "2", True),
        ("1", "40", "3", True),
        ("1", "40", "2.49", False),
        ("1", "40", "2.50", True),
    ],
)
def test_count_percentages_use_exact_ratios_at_rounding_boundaries(
    numerator,
    denominator,
    reported,
    agrees,
):
    raw, source = proposal(
        "percentage", {"numerator": numerator, "denominator": denominator}, reported
    )
    comparison = calculate(raw, source)["comparison"]
    assert comparison["numerical_match"] is agrees
    assert comparison["status"] == ("match" if agrees else "mismatch")
    assert comparison["comparison_basis"] == "exact-count-ratio-v1"


def test_percentage_inequality_uses_the_ratio_not_its_inexact_float_display():
    raw, source = proposal(
        "percentage", {"numerator": "1", "denominator": "3"}, "33.3333333333333334", relation="<"
    )
    result = calculate(raw, source)
    assert Decimal(str(result["outputs"]["value"])) > Decimal("33.3333333333333334")
    assert result["comparison"]["numerical_match"] is True
    assert result["comparison"]["status"] == "conditional"


@pytest.mark.parametrize("reported", ["5e-13", "-5e-13"])
def test_exact_zero_count_does_not_match_a_small_nonzero_report(reported):
    raw, source = proposal("count_sum", {"part_1": "0"}, reported)
    comparison = calculate(raw, source)["comparison"]
    assert comparison["numerical_match"] is False and comparison["status"] == "mismatch"
    assert comparison["rounding_tolerance_decimal"] == "0"
    assert comparison["comparison_basis"] == "exact-integer-sum-v1"


@pytest.mark.parametrize(
    "inputs",
    [
        {"part_1": str(2**53), "part_2": "1"},
        {"part_1": str(2**53 - 1), "part_2": "2"},
        {"part_1": str(2**53), "part_2": "1", "part_3": "1"},
    ],
)
def test_count_totals_outside_the_shared_exact_range_are_refused(inputs):
    raw, source = proposal("count_sum", inputs)
    with pytest.raises(ReviewError, match="count sum exceeds the exact calculator range"):
        calculate(raw, source)


def test_count_sum_at_the_range_boundary_is_exact_and_keeps_its_output_type():
    raw, source = proposal("count_sum", {"part_1": str(2**53 - 1), "part_2": "1"}, str(2**53))
    result = calculate(raw, source)
    assert type(result["outputs"]["value"]) is float
    assert result["outputs"]["value"] == 2**53
    assert result["comparison"]["numerical_match"] is True


@pytest.mark.parametrize("reported", ["0e999999999", "0e-999999999"])
def test_zero_tokens_cannot_trigger_unbounded_rounding_exponent_arithmetic(reported):
    raw, source = proposal("p_from_z", {"statistic": "40"}, reported, output="p_value")
    with pytest.raises(ReviewError, match="reported rounding precision exceeds"):
        calculate(raw, source)
