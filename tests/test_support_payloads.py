"""Real Hermes' default terminal capture is 50,000 characters, not unlimited JSON."""

import json

import pytest
from jsonschema import Draft202012Validator

from closed_review.support.calculators import INPUT_NAMES, METHODS, PARAMETER_NAMES
from closed_review.support.contracts import answer_schema
from closed_review.support.methods import MODULES
from closed_review.support.workflow import _instructions


@pytest.mark.parametrize("module", list(MODULES))
def test_appraisal_instructions_fit_the_terminal_capture_with_a_full_fact_index(module):
    guide = MODULES[module]
    run = {
        "id": "support-" + "a" * 32,
        "language": "ko",
        "resolved_language": None,
        "source": {"warnings": []},
        "modules": {
            module: {
                "facts": [
                    {"id": f"{module}-f{i:04d}", "role": guide["roles"][0], "label": "한" * 80}
                    for i in range(60)
                ],
                "criteria": [],
                "calculations": [],
            }
        },
    }
    task = {
        "id": "task-0002",
        "stage": "appraise",
        "module": module,
        "criteria": list(guide["criteria"])[:3],
    }
    instructions, context = _instructions(run, task)
    serialized = json.dumps(
        {"instructions": instructions, "context": context}, ensure_ascii=False, indent=2
    )
    assert len(serialized) < 40000
    Draft202012Validator.check_schema(context["answer_schema"])


def test_numeric_schema_reuses_definitions_without_widening_the_contract():
    schema = answer_schema("appraise", "statistics", ["calculation"])
    assert schema["$defs"]
    assert len(json.dumps(schema, indent=2)) < 25000
    validator = Draft202012Validator(schema)
    answer = {
        "task_id": "t",
        "assessments": [],
        "calculations": [
            {
                "method": "percentage",
                "inputs": {
                    "numerator": {"value": "2", "evidence": [{"block_id": "b1", "quote": "2"}]},
                    "denominator": {"value": "5", "evidence": [{"block_id": "b1", "quote": "5"}]},
                },
                "method_evidence": [{"block_id": "b1", "quote": "unweighted"}],
                "assumptions": [],
            }
        ],
    }
    assert validator.is_valid(answer)
    answer["calculations"][0]["inputs"]["numerator"]["evidence"] = "not a list"
    assert not validator.is_valid(answer)


@pytest.mark.parametrize("method", list(METHODS))
@pytest.mark.parametrize(
    "change", ["extra_input", "extra_parameter", "wrong_output", "missing_evidence"]
)
def test_factored_calculator_schema_keeps_every_method_closed(method, change):
    names = ["part_1"] if method == "count_sum" else INPUT_NAMES[method].split()

    def binding():
        return {"value": "2", "evidence": [{"block_id": "b1", "quote": "2"}]}

    calculation = {
        "method": method,
        "inputs": {name: binding() for name in names},
        "parameters": {
            name: False if name == "correction" else "two-sided"
            for name in PARAMETER_NAMES.get(method, "").split()
        },
        "method_evidence": [{"block_id": "b1", "quote": "2"}],
        "assumptions": [],
        "reported": {**binding(), "output": METHODS[method]["outputs"][0]},
    }
    validator = Draft202012Validator(answer_schema("appraise", "statistics", ["calculation"]))
    answer = {"task_id": "t", "assessments": [], "calculations": [calculation]}
    assert validator.is_valid(answer)
    if change == "extra_input":
        calculation["inputs"]["not_an_operand"] = binding()
    elif change == "extra_parameter":
        calculation["parameters"]["not_a_variant"] = False
    elif change == "wrong_output":
        calculation["reported"]["output"] = "not_an_output"
    else:
        calculation["inputs"][names[0]]["evidence"] = []
    assert not validator.is_valid(answer)
