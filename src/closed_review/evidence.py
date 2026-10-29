"""The checks creview makes of what a model writes, whatever the host: a quote is verbatim at a real
locator, arithmetic is computed rather than judged, and a mismatched figure is identified by what is
stated and what it computes to."""

from __future__ import annotations

import ast
import operator
import re
from typing import Any

# A mismatched figure that recurs this often (outside the reference list) is load-bearing: totals
# and denominators built on it inherit the error, so the entry is major whatever the screening says.
LOAD_BEARING_BLOCKS = 3


def flat(value: str) -> str:
    return " ".join(value.split())


def check_quote(
    label: str, item: Any, sources: dict[str, dict[str, Any]]
) -> tuple[dict[str, str] | None, str]:
    """A verbatim {source_id, locator, quote}; a wrong or empty locator is found from the quote."""
    if not isinstance(item, dict):
        return None, f"{label} must be an object"
    source = sources.get(str(item.get("source_id") or "manuscript"))
    locator = str(item.get("locator") or "")
    quote = str(item.get("quote") or "").strip()
    if source is None:
        return None, f"{label} cites an unknown source"
    if not quote:
        return None, f"{label} has no quote"
    blocks = source["segments"]
    block = next((b for b in blocks if b["locator"] == locator), None)
    if block is None or flat(quote) not in flat(block["text"]):
        # A quote from another segment often comes without its locator: find it.
        found = [b for b in blocks if flat(quote) in flat(b["text"])]
        if not found:
            where = f"at {locator}" if block else "anywhere in the source"
            return None, f"{label} quote is not verbatim {where}"
        if len(found) > 1:
            return None, (
                f"{label} quote appears at {len(found)} locators; give one of "
                + ", ".join(b["locator"] for b in found[:5])
            )
        locator = found[0]["locator"]
    return {"source_id": source["source_id"], "locator": locator, "quote": quote}, ""


_ARITHMETIC = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def evaluate(expression: str) -> float:
    """+, -, *, / and parentheses over plain numbers; nothing else is evaluated."""

    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in _ARITHMETIC:
            return _ARITHMETIC[type(node.op)](walk(node.left), walk(node.right))
        raise ValueError("only numbers, + - * / and parentheses are allowed")

    if len(expression) > 200:
        raise ValueError("expression is too long")
    return walk(ast.parse(expression.replace(",", ""), mode="eval"))


def number_checks(
    raw: Any, sources: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Compute the agent's arithmetic: language models misjudge sums, differences, percentages."""
    if raw in (None, []):
        return [], []
    if not isinstance(raw, list):
        return [], ["number_checks must be a list"]
    results, problems = [], []
    for index, item in enumerate(raw, start=1):
        label = f"number check {index}"
        if not isinstance(item, dict):
            problems.append(f"{label} must be an object")
            continue
        expression = str(item.get("expression") or "").strip()
        stated_text = str(item.get("stated") or "").replace(",", "").strip().rstrip("%")
        stated_text = number_word(stated_text) or stated_text
        if re.fullmatch(r"\d+(?:\.\d+)?\s+(?:of|out of|/)\s+\d+(?:\.\d+)?", stated_text):
            problems.append(
                f'{label}: stated "{stated_text}" is a count out of a total, which the manuscript '
                "states rather than computes; stated must be one figure the expression should "
                "give (a percentage the manuscript reports, a sum, a difference), or leave the "
                "check out"
            )
            continue
        try:
            computed = evaluate(expression)
            stated = float(stated_text)
        except (ValueError, SyntaxError, ZeroDivisionError) as exc:
            problems.append(
                f"{label} needs an expression and a stated number, one figure such as 38 or "
                f"thirty-eight with no other words: {exc}"
            )
            continue
        if stated in numbers_in(expression):
            # "31 - 24" against a stated 31 checks nothing: stated is what the expression gives.
            problems.append(
                f"{label}: stated must be the figure the manuscript gives for the result of the "
                "expression, not one of its operands"
            )
            continue
        evidence, issue_text = check_quote(label, item, sources)
        if evidence is None:
            problems.append(issue_text)
            continue
        decimals = len(stated_text.split(".")[1]) if "." in stated_text else 0
        matches = abs(computed - stated) <= 0.5 * 10**-decimals + 1e-9
        results.append(
            {
                "expression": expression,
                "stated": stated_text,
                "computed": round(computed, 6),
                "matches": matches,
                "evidence": evidence,
            }
        )
    return results, problems


_UNITS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def number_word(text: str) -> str | None:
    """A whole number written in English words, as digits ("Thirty-eight" -> "38"), up to
    9,999; None when the text is anything else."""
    words = re.split(r"[\s-]+", text.strip().lower().replace(" and ", " "))
    if not words or words == [""]:
        return None
    total = current = 0
    for w in words:
        if w in _UNITS:
            current += _UNITS.index(w)
        elif w in _TENS:
            current += 20 + 10 * _TENS.index(w)
        elif w == "hundred" and 0 < current < 10:
            current *= 100
        elif w == "thousand" and 0 < current < 10 and total == 0:
            total, current = current * 1000, 0
        else:
            return None
    return str(total + current)


def numbers_in(text: str) -> set[float]:
    return {float(n) for n in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))}


def same_check(check: dict[str, Any]) -> tuple[float, float]:
    """What makes two number checks one: the figure the manuscript states and what the arithmetic
    gives. `100 / 6.5` and `1 / 0.065` against a stated 9 are one mismatch, which the reviewer
    answers once, however each pass wrote the expression."""
    return float(check["stated"]), round(float(check["computed"]), 2)


REFERENCE_HEADING = re.compile(r"^heading:(references|bibliography|works cited|notes)\b", re.I)
