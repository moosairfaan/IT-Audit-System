"""CSV loading rejects a bad file and round-trips the generated population."""

from datetime import date

import pytest
from sqlalchemy import create_engine

from app.datasets import HR_ROSTER
from app.load import LoadError, parse_csv, replace_dataset, rows_to_csv
from app.models import HrRoster
from data_gen.checks import detect
from data_gen.catalog import AS_OF
from data_gen.generate import generate


def test_csv_round_trip_keeps_the_exception_ids() -> None:
    tables, truth = generate()
    restored = {name: parse_csv(name, rows_to_csv(name, rows)) for name, rows in tables.items()}
    assert restored == tables
    assert detect(restored, AS_OF) == truth


def test_malformed_csv_is_rejected() -> None:
    with pytest.raises(LoadError, match="columns"):
        parse_csv(HR_ROSTER, "employee_id,name\nE0001,Ada\n")
    with pytest.raises(LoadError, match="invalid date"):
        parse_csv(
            HR_ROSTER,
            "employee_id,name,department,job_title,hire_date,termination_date\n"
            "E0001,Ada,Finance,Accountant,not-a-date,\n",
        )
    with pytest.raises(LoadError, match="empty"):
        parse_csv(HR_ROSTER, "   ")


def test_replace_dataset_loads_a_roster() -> None:
    engine = create_engine("sqlite://")
    HrRoster.__table__.create(engine)
    csv_text = rows_to_csv(
        HR_ROSTER,
        [
            {
                "employee_id": "E0001",
                "name": "Ada Adler",
                "department": "Finance",
                "job_title": "Accountant",
                "hire_date": date(2020, 1, 15),
                "termination_date": None,
            }
        ],
    )
    assert replace_dataset(engine, HR_ROSTER, csv_text) == 1
