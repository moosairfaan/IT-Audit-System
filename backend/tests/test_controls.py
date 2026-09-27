"""Each control's exception identifiers match ground_truth.json."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.engine import Engine

from app.controls.runner import fetch_run, run_control

GROUND_TRUTH = Path(__file__).resolve().parents[1] / "data_gen" / "generated" / "ground_truth.json"
REASONS = {
    "no approval",
    "deployed before approval",
    "approver is the requester",
    "approver is the deployer",
}


def test_control_exceptions_match_ground_truth(database: Engine) -> None:
    expected = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    assert set(expected) == {"ITGC-01", "ITGC-02", "ITGC-03", "ITGC-04", "ITGC-05"}
    for control_id, expected_ids in expected.items():
        result = run_control(database, control_id)
        found = [row["exception_id"] for row in result["exceptions"]]
        assert found == sorted(expected_ids)
        assert result["exception_count"] == len(expected_ids)
        assert result["population_count"] >= result["exception_count"]
        stored = fetch_run(database, control_id, result["run_id"])
        assert [row["exception_id"] for row in stored["exceptions"]] == found
        if control_id == "ITGC-01":
            assert all(row["days_after_termination"] >= 0 for row in result["exceptions"])
        if control_id == "ITGC-03":
            assert {row["reason"] for row in result["exceptions"]} == REASONS
