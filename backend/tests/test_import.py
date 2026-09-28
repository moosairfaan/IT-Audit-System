"""Company-file mapping, and demo controls that still match ground truth."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from app.audit_context import RealDataDisabled, activate, load_rules, save_rules
from app.controls.runner import run_control
from app.importer import commit_import, inspect_csv, suggest_mapping, suggest_status, validate_bundle

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "import"
GROUND_TRUTH = Path(__file__).resolve().parents[1] / "data_gen" / "generated" / "ground_truth.json"


def _files() -> dict[str, dict[str, object]]:
    files: dict[str, dict[str, object]] = {}
    for name in ("hr_roster", "iam_accounts", "role_permissions", "change_tickets"):
        csv_text = (FIXTURES / f"{name}.csv").read_text(encoding="utf-8")
        inspected = inspect_csv(name, csv_text)
        files[name] = {
            "csv": csv_text,
            "mapping": inspected["mapping"],
            "status_map": inspected["status_map"],
        }
    return files


def test_messy_headers_map_and_statuses_normalize() -> None:
    roster = (FIXTURES / "hr_roster.csv").read_text(encoding="utf-8")
    mapping = suggest_mapping("hr_roster", ["Emp ID", "Full Name", "Dept", "Job Title", "Start Date", "Termination"])
    assert mapping["employee_id"] == "Emp ID"
    assert mapping["hire_date"] == "Start Date"
    assert mapping["termination_date"] == "Termination"
    accounts = inspect_csv("iam_accounts", (FIXTURES / "iam_accounts.csv").read_text(encoding="utf-8"))
    assert accounts["mapping"]["status"] == "Account Status"
    assert accounts["status_map"]["Active"] == "active"
    assert accounts["status_map"]["A"] == "active"
    assert accounts["status_map"]["Enabled"] == "active"
    assert accounts["status_map"]["1"] == "active"
    assert accounts["status_map"]["Disabled"] == "disabled"
    assert accounts["status_map"]["NotAStatus"] == ""
    assert suggest_status("Enabled") == "active"
    inspected = inspect_csv("hr_roster", roster)
    assert inspected["mapping"]["name"] == "Full Name"


def test_validation_report_counts_skips_and_blocks_an_unmapped_field() -> None:
    report = validate_bundle(_files())
    by_name = {item["dataset"]: item for item in report["datasets"]}
    assert by_name["hr_roster"]["rows_seen"] == 6
    assert by_name["hr_roster"]["rows_loaded"] == 3
    assert by_name["hr_roster"]["rows_skipped"] == 3
    reasons = [item["reason"] for item in by_name["hr_roster"]["skipped"]]
    assert "missing employee_id" in reasons
    assert "bad date in hire_date" in reasons
    assert "duplicate employee_id" in reasons
    assert by_name["iam_accounts"]["rows_loaded"] == 4
    assert by_name["iam_accounts"]["rows_skipped"] == 4
    account_reasons = [item["reason"] for item in by_name["iam_accounts"]["skipped"]]
    assert "status value has no mapping" in account_reasons
    assert "duplicate account_id" in account_reasons
    assert "bad date in last_login" in account_reasons
    assert "employee_id is not on the HR roster" in account_reasons
    assert by_name["role_permissions"]["rows_loaded"] == 4
    assert by_name["role_permissions"]["rows_skipped"] == 0
    assert by_name["change_tickets"]["rows_loaded"] == 2
    assert by_name["change_tickets"]["rows_skipped"] == 1
    assert report["can_import"] is True

    blocked = _files()
    blocked["hr_roster"]["mapping"]["employee_id"] = ""
    rejected = validate_bundle(blocked)
    roster = next(item for item in rejected["datasets"] if item["dataset"] == "hr_roster")
    assert roster["blocked"] is True
    assert rejected["can_import"] is False


def test_demo_controls_still_match_ground_truth(database: Engine) -> None:
    expected = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    for control_id, expected_ids in expected.items():
        result = run_control(database, control_id)
        found = [row["exception_id"] for row in result["exceptions"]]
        assert found == sorted(expected_ids)
        assert result["dataset"] == "demo"
        assert result["dataset_label"] == "Demo data"
        completeness = result["completeness"]
        assert completeness["records_tested"] == result["population_count"]
        assert completeness["records_loaded"] == completeness["records_tested"] + completeness["records_excluded"]
        assert sum(item["count"] for item in completeness["exclusions"]) == completeness["records_excluded"]
        if control_id == "ITGC-01":
            reasons = " ".join(item["reason"] for item in completeness["exclusions"])
            assert "active" not in reasons


def test_dormancy_setting_is_what_the_control_reads(database: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    rules = load_rules(database)
    original = int(rules["dormant_days"])
    assert original == 90
    try:
        save_rules(database, {**rules, "dormant_days": 1})
        widened = run_control(database, "ITGC-04")
        assert widened["exception_count"] > 6
        save_rules(database, {**rules, "dormant_days": 90})
        restored = run_control(database, "ITGC-04")
        assert restored["exception_count"] == 6
    finally:
        save_rules(database, {**rules, "dormant_days": original})
    monkeypatch.setenv("ALLOW_REAL_DATA", "false")
    with pytest.raises(RealDataDisabled):
        commit_import(database, _files())


def test_company_import_restores_demo_data(database: Engine) -> None:
    before = run_control(database, "ITGC-01")["exception_count"]
    try:
        imported = commit_import(database, _files())
        assert imported["label"] == "Company data"
        company = run_control(database, "ITGC-01")
        assert company["dataset"] == "company"
        assert company["exception_count"] != before
        activate(database, "demo")
        demo = run_control(database, "ITGC-01")
        assert demo["dataset"] == "demo"
        assert demo["exception_count"] == before
    finally:
        activate(database, "demo")
