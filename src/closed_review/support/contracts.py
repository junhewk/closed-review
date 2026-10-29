"""Explicit bounded answer contracts. Shape checks never coerce manuscript evidence."""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator

from ..errors import ReviewError
from .calculators import (
    INPUT_NAMES,
    METHODS,
    NUMBER,
    NUMERIC_LITERAL,
    PARAMETER_NAMES,
    _number,
    reported_relation,
)
from .methods import MODULES, RELATIONS, STATUSES
from .sources import resolve_evidence

VERSION = 10
COVERAGE_KINDS = (
    "unreadable_content",
    "ambiguous_structure",
    "unreconstructed_content",
    "fact_cap",
)


def text(*, empty: bool = False, maximum: int = 4000) -> dict:
    return {"type": "string", "minLength": 0 if empty else 1, "maxLength": maximum}


def array(item: dict, maximum: int = 48) -> dict:
    return {"type": "array", "items": item, "maxItems": maximum}


def obj(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


EVIDENCE = array(
    obj({"block_id": text(maximum=100), "quote": text(maximum=12000)}, ["block_id", "quote"])
)
REQUIRED_EVIDENCE = {**EVIDENCE, "minItems": 1}
BINDING = obj(
    {
        "value": {**text(maximum=100), "pattern": "^(?:" + NUMERIC_LITERAL + r")$(?![\s\S])"},
        "evidence": REQUIRED_EVIDENCE,
    },
    ["value", "evidence"],
)


def calculators(module: str) -> dict[str, Any]:
    names = (
        list(METHODS)
        if module == "statistics"
        else ["count_sum", "percentage"]
        if module in {"systematic-review", "scoping-review"}
        else []
    )
    return {name: METHODS[name] for name in names}


def calculation_schema(module: str) -> dict:
    methods = calculators(module)
    if not methods:
        return False
    variants = []
    for method, guide in methods.items():
        parameter_types = {
            "alternative": {"enum": ["two-sided", "less", "greater"]},
            "correction": {"type": "boolean"},
        }
        parameter_names = PARAMETER_NAMES.get(method, "").split()
        inputs = (
            {
                "type": "object",
                "minProperties": 1,
                "maxProperties": 32,
                "patternProperties": {r"^part_[1-9][0-9]*$(?![\s\S])": BINDING},
                "additionalProperties": False,
            }
            if method == "count_sum"
            else obj(
                {key: BINDING for key in INPUT_NAMES[method].split()}, INPUT_NAMES[method].split()
            )
        )
        variants.append(
            {
                "properties": {
                    "method": {"const": method},
                    "inputs": inputs,
                    "parameters": obj(
                        {key: parameter_types[key] for key in parameter_names}, parameter_names
                    ),
                    "reported": {
                        "properties": {"output": {"enum": guide["outputs"]}},
                        "required": [] if "value" in guide["outputs"] else ["output"],
                    },
                },
                "required": ["parameters"] if parameter_names else [],
            }
        )
    schema = obj(
        {
            "method": {"enum": list(methods)},
            "inputs": {"type": "object"},
            "parameters": {"type": "object"},
            "method_evidence": REQUIRED_EVIDENCE,
            "assumptions": array(text(), 24),
            "reported": obj(
                {
                    **BINDING["properties"],
                    "output": {"enum": sorted({o for m in methods.values() for o in m["outputs"]})},
                },
                ["value", "evidence"],
            ),
        },
        ["method", "inputs", "method_evidence", "assumptions"],
    )
    schema["oneOf"] = variants
    return schema


def consolidation_references(state: dict) -> dict[str, list[str]]:
    """Only existing actionable records may become observations; positive checks remain visible."""
    return {
        "criteria": [
            c["id"] for c in state["criteria"]
            if c["status"] == "concern" or (c["status"] == "not_located" and c.get("why_matters"))
        ],
        "calculations": [
            c["id"] for c in state["calculations"] if c["comparison"]["status"] == "mismatch"
        ],
    }


def _bind_consolidation(schema: dict, references: dict[str, list[str]]) -> dict[str, Any]:
    """Expose the existing semantic reference contract in the issued JSON Schema as well."""
    criteria = {"enum": list(references["criteria"])} if references["criteria"] else False
    calculations = (
        {"enum": list(references["calculations"])} if references["calculations"] else False
    )
    combined = references["criteria"] + references["calculations"]
    properties = schema["properties"]
    if not combined:
        # Do not emit dozens of nested false-schema errors for a normal no-concern result.
        for name in ("groups", "withdrawn", "priority"):
            properties[name] = {"type": "array", "maxItems": 0}
        return {}
    group = properties["groups"]["items"]
    group["properties"]["criteria"].update(items=criteria, uniqueItems=True)
    group["properties"]["calculations"].update(items=calculations, uniqueItems=True)
    group["anyOf"] = [
        {"properties": {"criteria": {"minItems": 1}}},
        {"properties": {"calculations": {"minItems": 1}}, "required": ["calculations"]},
    ]
    properties["withdrawn"]["items"]["properties"].update(
        criterion=criteria, calculation_id=calculations
    )
    properties["priority"].update(items={"enum": list(combined)}, uniqueItems=True)
    return {
        "candidate_criterion_id": criteria,
        "mismatch_calculation_id": calculations,
        "consolidation_reference_id": {"enum": list(combined)},
    }


def answer_schema(
    stage: str,
    module: str,
    criteria: list[str] | None = None,
    *,
    references: dict[str, list[str]] | None = None,
) -> dict:
    """Share repeated definitions without changing accepted answers or required evidence."""
    schema = _answer_schema(stage, module, criteria)
    definitions = {
        "evidence": EVIDENCE,
        "required_evidence": REQUIRED_EVIDENCE,
        "number_binding": BINDING,
        "text": text(),
        "optional_text": text(empty=True),
    }
    if stage == "consolidate" and references is not None:
        definitions.update(_bind_consolidation(schema, references))
    if stage == "appraise" and calculators(module):
        calculation = calculation_schema(module)
        definitions["calculation"] = calculation
        variants = calculation["oneOf"]
        definitions.update(
            {
                f"calculator_{name}": variant
                for name, variant in zip(calculators(module), variants, strict=True)
            }
        )
    signatures = {json.dumps(value, sort_keys=True): name for name, value in definitions.items()}
    used = set()

    def compact(value, skip=None):
        if isinstance(value, dict):
            match = signatures.get(json.dumps(value, sort_keys=True))
            if match and match != skip:
                used.add(match)
                return {"$ref": f"#/$defs/{match}"}
            return {key: compact(child) for key, child in value.items()}
        if isinstance(value, list):
            return [compact(child) for child in value]
        return value

    result = compact(schema)
    resolved = {}
    while used - resolved.keys():
        for name in sorted(used - resolved.keys()):
            resolved[name] = compact(definitions[name], skip=name)
    if resolved:
        result["$defs"] = {name: resolved[name] for name in sorted(resolved)}
    return result


def _answer_schema(stage: str, module: str, criteria: list[str] | None = None) -> dict:
    properties = {"task_id": text(maximum=40)}
    required = ["task_id"]
    if stage == "extract":
        fact = obj(
            {
                "role": {"enum": MODULES[module]["roles"]},
                "label": text(maximum=200),
                "value": text(maximum=1000),
                "evidence": REQUIRED_EVIDENCE,
            },
            ["role", "label", "value", "evidence"],
        )
        properties.update(
            facts=array(fact, 24),
            scope_limits=array(text(), 24),
            coverage_gaps=array(
                obj(
                    {
                        "kind": {"enum": list(COVERAGE_KINDS)},
                        "block_ids": {
                            **array(text(maximum=100), 48),
                            "minItems": 1,
                            "uniqueItems": True,
                        },
                        "role": {"enum": MODULES[module]["roles"]},
                        "detail": text(),
                    },
                    ["kind", "block_ids", "role", "detail"],
                ),
                24,
            ),
        )
        return obj(properties, required + ["facts", "scope_limits", "coverage_gaps"])
    if stage == "appraise":
        assessment = obj(
            {
                "criterion": {"enum": criteria or list(MODULES[module]["criteria"])},
                "status": {"enum": sorted(STATUSES)},
                "analysis": text(),
                "why_matters": text(empty=True),
                "evidence": EVIDENCE,
                "counterevidence": EVIDENCE,
                "limits": text(empty=True),
            },
            ["criterion", "status", "analysis", "why_matters", "evidence", "limits"],
        )
        connection = obj(
            {
                "from": {**array(text(maximum=100)), "minItems": 1},
                "to": {**array(text(maximum=100)), "minItems": 1},
                "relation": {"enum": sorted(RELATIONS)},
                "basis": {"enum": ["explicit", "inferred"]},
                "explanation": text(),
                "evidence": EVIDENCE,
            },
            ["from", "to", "relation", "basis", "explanation", "evidence"],
        )
        properties.update(
            assessments=array(assessment, 12),
            calculations=array(calculation_schema(module), 24),
            connections=array(connection, 48),
        )
        return obj(properties, required + ["assessments"])
    group = obj(
        {
            "criteria": array(text(maximum=100)),
            "calculations": array(text(maximum=100)),
            "title": text(maximum=200),
            "explanation": text(),
        },
        ["criteria", "title", "explanation"],
    )
    withdrawn = obj(
        {
            "criterion": text(maximum=100),
            "calculation_id": text(maximum=100),
            "reason": text(),
            "evidence": EVIDENCE,
        },
        ["reason", "evidence"],
    )
    withdrawn["oneOf"] = [{"required": ["criterion"]}, {"required": ["calculation_id"]}]
    properties.update(
        language=text(maximum=80),
        title=text(maximum=200),
        summary=text(),
        labels={"type": "object", "additionalProperties": text(maximum=400)},
        groups=array(group, 48),
        withdrawn=array(withdrawn, 72),
        priority=array(text(maximum=100), 3),
    )
    return obj(
        properties, required + ["language", "title", "summary", "groups", "withdrawn", "priority"]
    )


def validate_shape(
    answer: Any,
    stage: str,
    module: str,
    criteria: list[str] | None,
    *,
    references: dict[str, list[str]] | None = None,
) -> None:
    schema = answer_schema(stage, module, criteria, references=references)
    errors = list(Draft202012Validator(schema).iter_errors(answer))
    if not errors:
        return
    # Do not echo confidential values into validation diagnostics. Return actionable paths
    # and shape expectations together, so one repair can address all shape errors.
    issues = []
    for error in errors[:12]:
        if error.validator == "oneOf" and error.context:
            method = error.instance.get("method") if isinstance(error.instance, dict) else None
            if isinstance(method, str) and method in calculators(module):
                matching = [
                    e
                    for e in error.context
                    if e.schema_path[0] == list(calculators(module)).index(method)
                ]
                if matching:
                    for child in matching[:8]:
                        path = ".".join(map(str, child.absolute_path)) or "$"
                        issues.append(f"{path}: {expectation(child)}")
                    continue
        path = ".".join(map(str, error.absolute_path)) or "$"
        issues.append(f"{path}: {expectation(error)}")
    raise ReviewError("answer format errors:\n" + "\n".join(dict.fromkeys(issues)))


def expectation(error) -> str:
    if error.schema is False:
        return "no eligible reference of this kind; use only this task's listed candidate IDs"
    if error.validator == "maxItems" and error.validator_value == 0:
        return (
            "must be []: this task has no candidate criteria or mismatch calculations; "
            "put positive checks and ordinary limits in summary, not observation groups"
        )
    if error.validator == "type":
        if "coverage_gaps" in error.absolute_path and error.validator_value == "object":
            return (
                "expected a gap object with kind/block_ids/role/detail; normal uncertainty "
                "or lack of certification belongs in scope_limits, not coverage_gaps"
            )
        return f"expected {error.validator_value}"
    if error.validator == "enum":
        return "choose one of " + ", ".join(map(str, error.validator_value))
    if error.validator == "required":
        return "required fields: " + ", ".join(error.validator_value)
    if error.validator == "additionalProperties":
        if "output" in error.schema.get("properties", {}) and any(
            field in error.instance for field in ("relation", "source_operator")
        ):
            return (
                "do not supply reported.relation or source_operator. Quote the reported "
                "number with its source qualifier; Python reads it and compares the values"
            )
        if "patternProperties" in error.schema:
            return "count_sum input keys must be part_1, part_2, ...; see answer_schema"
        return "unknown fields; use only keys shown in answer_schema"
    if error.validator == "pattern":
        return (
            "use one literal numeric token printed in the quoted source, not words or expressions; "
            "omit unavailable calculations and explain the limit in the assessment"
        )
    return f"does not satisfy {error.validator}; see answer_schema"


def validate_references(answer: dict, source: dict) -> None:
    """Diagnose every malformed source reference before semantic writes, without quoting secrets.

    Shape validation runs first, so these are only the contract's recognized evidence fields.
    Do not normalize punctuation, relocate a quote, or infer a missing source reference.
    """
    failures = []

    def inspect(value: Any, path: str = "$") -> None:
        if isinstance(value, dict):
            if "block_id" in value and "quote" in value:
                try:
                    resolve_evidence([value], source)
                except ReviewError:
                    identifier = value["block_id"]
                    known = any(b["id"] == identifier for b in source["blocks"])
                    failures.append(
                        f"{path}: "
                        + (
                            f"quote is not an exact substring of source block {identifier}; "
                            "read that block again and preserve its punctuation"
                            if known
                            else "unknown block_id; select a block from this run's source"
                        )
                    )
                return
            for key, child in value.items():
                inspect(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                inspect(child, f"{path}[{index}]")

    inspect(answer)
    if failures:
        raise ReviewError("answer source-reference errors:\n" + "\n".join(failures[:12]))


def validate_numeric_bindings(answer: dict, source: dict) -> None:
    """Expose all invalid numeric bindings at once; never invent or repair a token."""
    failures = []
    for index, calculation in enumerate(answer.get("calculations", [])):
        reported_binding = None
        bindings = [(f"inputs.{key}", value) for key, value in calculation["inputs"].items()]
        if "reported" in calculation:
            bindings.append(("reported", calculation["reported"]))
        for field, binding in bindings:
            try:
                literal = binding["value"].replace("−", "-").replace(",", "")
                quoted = {
                    token.group().replace(",", "")
                    for evidence in binding["evidence"]
                    for token in NUMBER.finditer(evidence["quote"].replace("−", "-"))
                }
                if literal not in quoted:
                    raise ReviewError(
                        "numeric input must preserve the exact reported numeric token"
                    )
                _, resolved = _number(binding, source, exact=field != "reported")
                if field == "reported":
                    reported_binding = resolved
            except ReviewError as exc:
                failures.append(f"$.calculations[{index}].{field}: {exc}")
        if reported_binding is not None:
            try:
                reported_relation(calculation["reported"], reported_binding, source)
            except ReviewError as exc:
                failures.append(f"$.calculations[{index}].reported: {exc}")
    if failures:
        raise ReviewError(
            "answer numeric-binding errors:\n"
            + "\n".join(failures[:12])
            + "\nIf a required literal input is unavailable, omit the ENTIRE calculation and "
            "explain the limit in the assessment. Do not drop terms, substitute a different "
            "quantity, or invent an inequality to salvage a replay."
        )
