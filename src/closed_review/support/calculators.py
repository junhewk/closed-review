"Closed statistical registry. Models propose inputs, never calculation results or verdicts."

from __future__ import annotations

import math
import re
from bisect import bisect_left
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

from ..errors import ReviewError
from .sources import resolve_evidence

NUMERIC_LITERAL = (
    r"[-+−]?(?:(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?|\.[0-9]+)"
    r"(?:[eE][-+]?[0-9]+)?"
)
NUMBER = re.compile(r"(?<![\w.])" + NUMERIC_LITERAL + r"(?!\w|\.\d)")
INPUT_NAMES = {
    "percentage": "numerator denominator",
    "ratios_2x2": "a b c d",
    "pearson_2x2": "a b c d",
    "fisher_2x2": "a b c d",
    "student_t": "mean1 sd1 n1 mean2 sd2 n2",
    "welch_t": "mean1 sd1 n1 mean2 sd2 n2",
    "p_from_z": "statistic",
    "p_from_t": "statistic df",
    "p_from_chi2": "statistic df",
    "p_from_f": "statistic dfn dfd",
    "normal_ci": "estimate se confidence_percent",
    "t_ci": "estimate se confidence_percent df",
}
PARAMETER_NAMES = {
    "pearson_2x2": "correction",
    **{
        name: "alternative"
        for name in ("fisher_2x2", "student_t", "welch_t", "p_from_z", "p_from_t")
    },
}
SOURCE_OPERATORS = {"=": "=", "<": "<", ">": ">", "<=": "<=", ">=": ">=", "≤": "<=", "≥": ">="}
METHODS = {
    "count_sum": {
        "inputs": "part_1, part_2, ... (nonnegative integer exclusive counts)",
        "formula": "sum(parts)",
    },
    "percentage": {
        "inputs": "numerator denominator (unweighted counts)",
        "formula": "100 * numerator / denominator",
    },
    "ratios_2x2": {
        "inputs": "a b c d (event/non-event rows, unadjusted)",
        "formula": "OR=a*d/(b*c); RR=(a/(a+b))/(c/(c+d))",
    },
    "pearson_2x2": {
        "inputs": "a b c d; parameters.correction=true/false",
        "formula": "Pearson chi-square, declared Yates correction",
    },
    "fisher_2x2": {
        "inputs": "a b c d; parameters.alternative",
        "formula": "Fisher exact, declared alternative",
    },
    "student_t": {
        "inputs": "mean1 sd1 n1 mean2 sd2 n2; parameters.alternative",
        "formula": "independent Student t with pooled variance",
    },
    "welch_t": {
        "inputs": "mean1 sd1 n1 mean2 sd2 n2; parameters.alternative",
        "formula": "independent Welch t with Satterthwaite df",
    },
    "p_from_z": {
        "inputs": "statistic; parameters.alternative",
        "formula": "standard normal tail probability",
    },
    "p_from_t": {
        "inputs": "statistic df; parameters.alternative",
        "formula": "Student t tail probability",
    },
    "p_from_chi2": {"inputs": "statistic df", "formula": "chi-square upper tail"},
    "p_from_f": {"inputs": "statistic dfn dfd", "formula": "F upper tail"},
    "normal_ci": {
        "inputs": "estimate se confidence_percent",
        "formula": "estimate +/- normal quantile * SE",
    },
    "t_ci": {
        "inputs": "estimate se df confidence_percent",
        "formula": "estimate +/- t quantile * SE",
    },
}

# Output identifiers are part of the model-facing contract, not formula strings.
for _method, _outputs in {
    "count_sum": ["value"],
    "percentage": ["value"],
    "ratios_2x2": ["odds_ratio", "risk_ratio"],
    "pearson_2x2": ["statistic", "p_value", "df"],
    "fisher_2x2": ["odds_ratio", "p_value"],
    "student_t": ["statistic", "p_value"],
    "welch_t": ["statistic", "p_value"],
    "p_from_z": ["p_value"],
    "p_from_t": ["p_value"],
    "p_from_chi2": ["p_value"],
    "p_from_f": ["p_value"],
    "normal_ci": ["lower", "upper"],
    "t_ci": ["lower", "upper"],
}.items():
    METHODS[_method]["outputs"] = _outputs


def _number(
    raw: Any, source: dict[str, Any], *, exact: bool = True
) -> tuple[float, dict[str, Any]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("value"), str):
        raise ReviewError("each numeric input needs a string value and source evidence")
    value = raw["value"].replace("−", "-")
    if not NUMBER.fullmatch(value):
        raise ReviewError(
            "numeric inputs must be literal numbers, not expressions or invented data"
        )
    evidence = resolve_evidence(raw.get("evidence"), source)
    if not evidence:
        raise ReviewError("numeric input has missing or ambiguous source alignment")
    ambiguous_pages = {t.get("page") for t in source.get("tables", []) if t["ambiguous"]}
    for item in evidence:
        page = re.match(r"page:(\d+)/", item["locator"])
        if page and int(page[1]) in ambiguous_pages:
            raise ReviewError(
                "numeric inputs on a page with ambiguous table alignment are not assessable"
            )
    if any(e["ambiguous"] for e in evidence):
        raise ReviewError("numeric input has missing or ambiguous source alignment")
    tokens = [
        m.group().replace(",", "")
        for e in evidence
        for m in NUMBER.finditer(e["quote"].replace("−", "-"))
    ]
    literal = value.replace(",", "")
    if literal not in tokens:
        raise ReviewError("numeric input must preserve the exact reported numeric token")
    try:
        precise = Decimal(literal)
        if precise == precise.to_integral_value() and precise.copy_abs() > 2**53:
            raise ReviewError("integer input exceeds the exact calculator range")
        number = float(precise)
    except (InvalidOperation, OverflowError) as exc:
        raise ReviewError("invalid numeric input") from exc
    if not math.isfinite(number):
        raise ReviewError("numeric inputs must be finite")
    if (number == 0 and precise != 0) or (
        precise != precise.to_integral_value() and number.is_integer()
    ):
        raise ReviewError("numeric input loses its fractional precision in the calculator")
    binding = {"value": raw["value"], "evidence": evidence}
    relation = reported_relation({"value": raw["value"]}, binding, source)
    if exact and relation != "=":
        raise ReviewError("calculator inputs need point values, not source-qualified bounds")
    return number, binding


def reported_relation(raw: dict, binding: dict, source: dict) -> str:
    """Derive an unambiguous literal source qualifier; models never propose comparisons."""
    if "relation" in raw or "source_operator" in raw:
        raise ReviewError(
            "do not supply reported.relation or source_operator; quote the reported number "
            "with its printed qualifier. Python reads that qualifier and compares values"
        )
    literal = raw["value"].replace("−", "-").replace(",", "")
    relations = set()
    blocks = {block["id"]: block["text"] for block in source["blocks"]}
    for evidence in binding["evidence"]:
        text, quote = blocks[evidence["block_id"]], evidence["quote"]
        starts, cursor = [], 0
        while (start := text.find(quote, cursor)) >= 0:
            starts.append(start)
            cursor = start + 1
        # Read complete original-block tokens, not digit fragments or qualifiers clipped
        # from a model's quote. Binary search keeps repeated short quotes bounded in cost.
        normalized = text.replace("−", "-")
        for token in NUMBER.finditer(normalized):
            if token.group().replace(",", "") != literal:
                continue
            index = bisect_left(starts, token.end() - len(quote))
            if index < len(starts) and starts[index] <= token.start():
                operator = re.search(r"(<=|>=|<|>|=|≤|≥)\s*$", normalized[: token.start()])
                relations.add(SOURCE_OPERATORS[operator[1]] if operator else "=")
    if len(relations) == 1:
        return relations.pop()
    if not relations:
        raise ReviewError(
            "numeric evidence must contain a complete original source token, not a digit fragment"
        )
    raise ReviewError(
        "the reported numeric token has ambiguous source qualifiers; use a narrower exact "
        "quote identifying that reported quantity, or omit the unavailable comparison"
    )


def calculate(raw: Any, source: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("method") not in METHODS:
        raise ReviewError("unsupported calculator; do not approximate an unregistered method")
    method = raw["method"]
    method_evidence = resolve_evidence(raw.get("method_evidence"), source)
    if not method_evidence:
        raise ReviewError(
            "calculation needs evidence for its population, denominator and declared method"
        )
    assumptions = raw.get("assumptions")
    if not isinstance(assumptions, list) or any(not isinstance(s, str) for s in assumptions):
        raise ReviewError("calculation assumptions must be an explicit list")
    if not isinstance(raw.get("inputs"), dict) or not raw["inputs"]:
        raise ReviewError("calculation needs named inputs")
    values, bindings = {}, {}
    for name, item in raw["inputs"].items():
        values[name], bindings[name] = _number(item, source)
    parameters = raw.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ReviewError("calculator parameters must be an object")
    expected_parameters = set(PARAMETER_NAMES.get(method, "").split())
    if set(parameters) != expected_parameters:
        raise ReviewError(
            f"{method} parameters must contain exactly: "
            + (", ".join(sorted(expected_parameters)) or "no keys")
        )

    def need(names: str) -> list[float]:
        keys = names.split()
        if set(values) != set(keys):
            raise ReviewError(f"{method} requires exactly: {names}")
        return [values[k] for k in keys]

    def counts(nums: list[float]) -> None:
        if any(n < 0 or not n.is_integer() for n in nums):
            raise ReviewError("counts must be nonnegative integers")

    def positive(*nums: float) -> None:
        if any(n <= 0 for n in nums):
            raise ReviewError("sample size, df, SE and denominators must be positive")

    def alternative() -> str:
        value = parameters.get("alternative")
        if value not in {"two-sided", "less", "greater"}:
            raise ReviewError("declare alternative: two-sided, less or greater")
        return value

    result = {}
    unavailable_outputs = []
    try:
        if method == "count_sum":
            if not all(re.fullmatch(r"part_[1-9]\d*", n) for n in values):
                raise ReviewError("count_sum inputs must be named part_1, part_2, ...")
            counts(list(values.values()))
            # Individual operands are exact integers, but a float sum can lose counts
            # when their total exceeds the shared exact numeric range.
            total = sum(int(value) for value in values.values())
            if total > 2**53:
                raise ReviewError("count sum exceeds the exact calculator range")
            result = {"value": float(total)}
        elif method == "percentage":
            numerator, denominator = need("numerator denominator")
            counts([numerator, denominator])
            positive(denominator)
            if numerator > denominator:
                raise ReviewError("percentage numerator exceeds its declared count denominator")
            result = {"value": 100 * numerator / denominator}
        else:
            from scipy import stats

            if method in {"ratios_2x2", "pearson_2x2", "fisher_2x2"}:
                a, b, c, d = need("a b c d")
                counts([a, b, c, d])
                positive(a + b, c + d)
                if method == "ratios_2x2":
                    positive(b, c)
                    result = {
                        "odds_ratio": a * d / (b * c),
                        "risk_ratio": (a / (a + b)) / (c / (c + d)),
                    }
                elif method == "pearson_2x2":
                    if type(parameters.get("correction")) is not bool:
                        raise ReviewError("declare whether Pearson uses Yates correction")
                    out = stats.chi2_contingency(
                        [[a, b], [c, d]], correction=parameters["correction"]
                    )
                    result = {
                        "statistic": float(out.statistic),
                        "p_value": float(out.pvalue),
                        "df": int(out.dof),
                    }
                else:
                    out = stats.fisher_exact([[a, b], [c, d]], alternative=alternative())
                    result = {"p_value": float(out.pvalue)}
                    if math.isfinite(float(out.statistic)):
                        result["odds_ratio"] = float(out.statistic)
                    else:
                        unavailable_outputs.append(
                            "odds_ratio: undefined or unbounded; no correction"
                        )
            elif method in {"student_t", "welch_t"}:
                m1, s1, n1, m2, s2, n2 = need("mean1 sd1 n1 mean2 sd2 n2")
                counts([n1, n2])
                positive(n1 - 1, n2 - 1)
                if min(s1, s2) < 0 or s1 == s2 == 0:
                    raise ReviewError("SDs must be nonnegative and supply nonzero variance")
                out = stats.ttest_ind_from_stats(
                    m1,
                    s1,
                    n1,
                    m2,
                    s2,
                    n2,
                    equal_var=method == "student_t",
                    alternative=alternative(),
                )
                result = {"statistic": float(out.statistic), "p_value": float(out.pvalue)}
            elif method in {"normal_ci", "t_ci"}:
                names = "estimate se confidence_percent" + (" df" if method == "t_ci" else "")
                nums = need(names)
                estimate, se, level = nums[:3]
                positive(se)
                if not 0 < level < 100:
                    raise ReviewError("confidence_percent must be between 0 and 100")
                if method == "t_ci":
                    positive(nums[3])
                q = (
                    stats.t.ppf((1 + level / 100) / 2, nums[3])
                    if method == "t_ci"
                    else stats.norm.ppf((1 + level / 100) / 2)
                )
                result = {"lower": float(estimate - q * se), "upper": float(estimate + q * se)}
            else:
                names = {
                    "p_from_z": "statistic",
                    "p_from_t": "statistic df",
                    "p_from_chi2": "statistic df",
                    "p_from_f": "statistic dfn dfd",
                }[method]
                nums = need(names)
                for n in nums[1:]:
                    positive(n)
                x = nums[0]
                if method in {"p_from_chi2", "p_from_f"}:
                    if x < 0:
                        raise ReviewError("F/chi-square statistic must be nonnegative")
                    distribution = (
                        stats.chi2(nums[1])
                        if method == "p_from_chi2"
                        else stats.f(nums[1], nums[2])
                    )
                    p = distribution.sf(x)
                else:
                    distribution = stats.norm if method == "p_from_z" else stats.t(nums[1])
                    alt = alternative()
                    p = (
                        2 * distribution.sf(abs(x))
                        if alt == "two-sided"
                        else distribution.cdf(x)
                        if alt == "less"
                        else distribution.sf(x)
                    )
                result = {"p_value": float(p)}
    except ImportError as exc:
        raise ReviewError("statistical calculators require the packaged scipy dependency") from exc
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ReviewError(f"calculation is not assessable: {exc}") from exc
    if any(not math.isfinite(v) for v in result.values()):
        raise ReviewError("calculation is undefined; no automatic continuity correction is allowed")

    comparison: dict[str, Any] = {"status": "not_compared"}
    if raw.get("reported") is not None:
        reported = raw["reported"]
        _, binding = _number(reported, source, exact=False)
        output = reported.get("output", "value")
        if output not in result:
            raise ReviewError(
                f"reported.output must name a calculator output: {', '.join(result)}; "
                "use an output identifier, never the formula"
            )
        relation = reported_relation(reported, binding, source)
        # A fixed epsilon would call tiny probabilities equal regardless of their
        # printed precision. Decimal comparisons preserve the reported token's scale.
        # 1000 digits cover finite binary64 exponents plus the bounded source tokens.
        with localcontext() as context:
            context.prec = 1000
            number = Decimal(binding["value"].replace(",", "").replace("−", "-"))
            exponent = number.as_tuple().exponent
            if not -324 <= exponent <= 308:
                raise ReviewError("reported rounding precision exceeds the calculator range")
            tolerance = Decimal(10) ** exponent / 2
            scale = 1
            if method == "count_sum":
                computed = Decimal(total)
                tolerance = Decimal(0)
                basis = "exact-integer-sum-v1"
            elif method == "percentage":
                # Compare the exact count ratio by cross multiplication; do not
                # misclassify a rounding boundary because its float display is inexact.
                computed = Decimal(100 * int(values["numerator"]))
                scale = int(values["denominator"])
                basis = "exact-count-ratio-v1"
            else:
                computed = Decimal(str(result[output]))
                basis = "saved-float-decimal-v1"
            target = number * scale
            match = {
                "=": abs(computed - target) <= tolerance * scale,
                "<": computed < target,
                ">": computed > target,
                "<=": computed <= target,
                ">=": computed >= target,
            }[relation]
        exact_counts = method in {"percentage", "count_sum"} and relation == "="
        comparison = {
            "status": ("match" if match else "mismatch") if exact_counts else "conditional",
            "numerical_match": match,
            "reported": binding,
            "output": output,
            "relation": relation,
            "rounding_tolerance": float(tolerance),
            "rounding_tolerance_decimal": str(tolerance),
            "comparison_basis": basis,
        }
    return {
        "method": method,
        "formula": METHODS[method]["formula"],
        "inputs": bindings,
        "parameters": parameters,
        "method_evidence": method_evidence,
        "assumptions": assumptions,
        "outputs": result,
        "unavailable_outputs": unavailable_outputs,
        "comparison": comparison,
        "arithmetic_verified": True,
        "input_interpretation_verified": False,
        "note": (
            "Checks arithmetic on selected inputs, not their semantic "
            "mapping or scientific validity."
        ),
    }
