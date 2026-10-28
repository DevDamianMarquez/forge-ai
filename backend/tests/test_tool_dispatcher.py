"""Tests for the explicit, allowlisted FORGE tool dispatcher.

No real Meta API involved -- this exercises dispatch_tool_call directly.
"""

from __future__ import annotations

import pytest

from app.models.physics import ExperimentStatus
from app.services.forge_tools import GEAR_TRAIN_EXPERIMENT_TOOL_NAME
from app.services.tool_dispatcher import (
    InvalidToolArgumentsError,
    UnknownToolError,
    dispatch_tool_call,
)

VALID_ARGUMENTS = {
    "train": {
        "input_rpm": 1200,
        "connections": [
            {
                "driver": {"id": "driver", "teeth": 20},
                "driven": {"id": "driven", "teeth": 60},
            }
        ],
    },
    "constraints": [
        {"name": "max-output-rpm", "metric": "output_rpm", "operator": "lte", "value": 500}
    ],
}


def test_dispatch_executes_known_tool_and_returns_canonical_result():
    execution = dispatch_tool_call(GEAR_TRAIN_EXPERIMENT_TOOL_NAME, VALID_ARGUMENTS)

    assert execution.tool_name == GEAR_TRAIN_EXPERIMENT_TOOL_NAME
    assert execution.result.status == ExperimentStatus.SUCCESS
    assert execution.result.result == pytest.approx(400.0)
    assert execution.result.constraint_results[0].passed is True


def test_dispatch_rejects_unknown_tool():
    with pytest.raises(UnknownToolError):
        dispatch_tool_call("delete_database", {})


def test_dispatch_rejects_unknown_tool_that_looks_like_code_execution():
    with pytest.raises(UnknownToolError):
        dispatch_tool_call("os.system", {"command": "echo hi"})


def test_dispatch_rejects_invalid_arguments_empty_connections():
    with pytest.raises(InvalidToolArgumentsError):
        dispatch_tool_call(
            GEAR_TRAIN_EXPERIMENT_TOOL_NAME,
            {"train": {"input_rpm": 1200, "connections": []}},
        )


def test_dispatch_rejects_missing_required_fields():
    with pytest.raises(InvalidToolArgumentsError):
        dispatch_tool_call(GEAR_TRAIN_EXPERIMENT_TOOL_NAME, {})


def test_dispatch_rejects_invalid_teeth_count():
    with pytest.raises(InvalidToolArgumentsError):
        dispatch_tool_call(
            GEAR_TRAIN_EXPERIMENT_TOOL_NAME,
            {
                "train": {
                    "input_rpm": 1200,
                    "connections": [
                        {
                            "driver": {"id": "driver", "teeth": 0},
                            "driven": {"id": "driven", "teeth": 60},
                        }
                    ],
                }
            },
        )
