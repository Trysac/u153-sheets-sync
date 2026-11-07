"""Tests for sheets_sync public API."""

from __future__ import annotations

import datetime
import decimal
from collections.abc import Sequence
from typing import Literal

import pytest

from sheets_sync import (
    Column,
    RangeUpdate,
    SheetSchema,
    SheetsPort,
    SyncError,
    column_letter,
    plan_sync,
    serialize,
    sync,
)


class FakeSheets(SheetsPort):
    """In-memory SheetsPort fake recording calls and returning configured values."""

    def __init__(self, values: list[list[str]] | None = None) -> None:
        self.values: list[list[str]] = values if values is not None else []
        self.read_calls: list[str] = []
        self.batch_update_calls: list[tuple[Sequence[RangeUpdate], str]] = []
        self.append_rows_calls: list[tuple[str, Sequence[Sequence[str]], str]] = []

    def read_values(self, range_a1: str) -> list[list[str]]:
        self.read_calls.append(range_a1)
        return [list(r) for r in self.values]

    def batch_update(
        self, updates: Sequence[RangeUpdate], *, value_input_option: Literal["RAW"]
    ) -> None:
        self.batch_update_calls.append((updates, value_input_option))

    def append_rows(
        self, range_a1: str, rows: Sequence[Sequence[str]], *, value_input_option: Literal["RAW"]
    ) -> None:
        self.append_rows_calls.append((range_a1, rows, value_input_option))


def test_acceptance_column_letter() -> None:
    # column_letter(1) == 'A', column_letter(26) == 'Z', column_letter(27) == 'AA',
    # column_letter(702) == 'ZZ', column_letter(703) == 'AAA', column_letter(18278) == 'ZZZ',
    # and column_letter(0) and column_letter(18279) raise SyncError with code 'invalid_range'
    assert column_letter(1) == "A"
    assert column_letter(26) == "Z"
    assert column_letter(27) == "AA"
    assert column_letter(702) == "ZZ"
    assert column_letter(703) == "AAA"
    assert column_letter(18278) == "ZZZ"

    with pytest.raises(SyncError) as exc_0:
        column_letter(0)
    assert exc_0.value.code == "invalid_range"

    with pytest.raises(SyncError) as exc_18279:
        column_letter(18279)
    assert exc_18279.value.code == "invalid_range"


def test_acceptance_plan_sync() -> None:
    # With columns id (key, 'str'), name ('str'), qty ('int'), sheet values
    # [['id', 'name', 'qty'], ['1', 'Ann', '2'], ['2', 'Bob', '5']] and records
    # [{'id': '1', 'name': 'Ann', 'qty': 2}, {'id': '2', 'name': 'Bob', 'qty': 6}, {'id': '3', 'name': 'Cy', 'qty': 0}]
    # on title 'Stock', plan_sync returns updates == [RangeUpdate("'Stock'!A3:C3", [['2', 'Bob', '6']])],
    # appends == [['3', 'Cy', '0']] and unchanged == 1
    schema = SheetSchema(
        (
            Column("id", "str", key=True),
            Column("name", "str"),
            Column("qty", "int"),
        )
    )
    values = [["id", "name", "qty"], ["1", "Ann", "2"], ["2", "Bob", "5"]]
    records = [
        {"id": "1", "name": "Ann", "qty": 2},
        {"id": "2", "name": "Bob", "qty": 6},
        {"id": "3", "name": "Cy", "qty": 0},
    ]
    plan = plan_sync(schema, "Stock", values, records)
    assert plan.updates == [RangeUpdate("'Stock'!A3:C3", [["2", "Bob", "6"]])]
    assert plan.appends == [["3", "Cy", "0"]]
    assert plan.unchanged == 1
    assert plan.cleared == 0


def test_acceptance_header_duplicate_key_invalid_schema() -> None:
    # A header ['id', 'qty', 'name'] raises SyncError with code 'header_mismatch',
    # two records with id '1' raise code 'duplicate_key', and a schema with zero or two key columns raises code 'invalid_schema'
    schema = SheetSchema(
        (
            Column("id", "str", key=True),
            Column("name", "str"),
            Column("qty", "int"),
        )
    )
    bad_header_values = [["id", "qty", "name"], ["1", "2", "Ann"]]
    records = [{"id": "1", "name": "Ann", "qty": 2}]
    with pytest.raises(SyncError) as exc_header:
        plan_sync(schema, "Stock", bad_header_values, records)
    assert exc_header.value.code == "header_mismatch"

    dup_records = [
        {"id": "1", "name": "Ann", "qty": 2},
        {"id": "1", "name": "Ann2", "qty": 3},
    ]
    with pytest.raises(SyncError) as exc_dup:
        plan_sync(schema, "Stock", [["id", "name", "qty"]], dup_records)
    assert exc_dup.value.code == "duplicate_key"

    with pytest.raises(SyncError) as exc_zero_keys:
        SheetSchema(
            (
                Column("id", "str", key=False),
                Column("name", "str", key=False),
            )
        )
    assert exc_zero_keys.value.code == "invalid_schema"

    with pytest.raises(SyncError) as exc_two_keys:
        SheetSchema(
            (
                Column("id", "str", key=True),
                Column("name", "str", key=True),
            )
        )
    assert exc_two_keys.value.code == "invalid_schema"


def test_acceptance_delete_missing() -> None:
    # With delete_missing=True and sheet row key '2' absent from the records, the plan contains
    # RangeUpdate("'Stock'!A3:C3", [['', '', '']]) and cleared == 1; with the default False that row is untouched and cleared == 0
    schema = SheetSchema(
        (
            Column("id", "str", key=True),
            Column("name", "str"),
            Column("qty", "int"),
        )
    )
    values = [["id", "name", "qty"], ["1", "Ann", "2"], ["2", "Bob", "5"]]
    records = [{"id": "1", "name": "Ann", "qty": 2}]

    plan_del = plan_sync(schema, "Stock", values, records, delete_missing=True)
    assert RangeUpdate("'Stock'!A3:C3", [["", "", ""]]) in plan_del.updates
    assert plan_del.cleared == 1

    plan_default = plan_sync(schema, "Stock", values, records)
    assert not any(u.range_a1 == "'Stock'!A3:C3" for u in plan_default.updates)
    assert plan_default.cleared == 0


def test_acceptance_serialize() -> None:
    # serialize maps True to 'TRUE', Decimal('1.50') to '1.50', date(2026, 1, 2) to '2026-01-02' and None to '',
    # while True for an 'int' column and a 50_001-character string raise SyncError with code 'invalid_value'
    col_bool = Column("active", "bool")
    assert serialize(col_bool, True) == "TRUE"
    assert serialize(col_bool, False) == "FALSE"

    col_dec = Column("price", "decimal")
    assert serialize(col_dec, decimal.Decimal("1.50")) == "1.50"

    col_date = Column("created", "date")
    assert serialize(col_date, datetime.date(2026, 1, 2)) == "2026-01-02"

    col_str = Column("notes", "str")
    assert serialize(col_str, None) == ""

    col_int = Column("qty", "int")
    with pytest.raises(SyncError) as exc_bool_int:
        serialize(col_int, True)
    assert exc_bool_int.value.code == "invalid_value"

    huge_str = "x" * 50_001
    with pytest.raises(SyncError) as exc_huge:
        serialize(col_str, huge_str)
    assert exc_huge.value.code == "invalid_value"


def test_acceptance_title_and_sync_port() -> None:
    # The title "O'Brien" makes sync read the range "'O''Brien'!A1:C"; with changes, sync calls batch_update
    # once and append_rows once with range "'Stock'!A1", both with value_input_option 'RAW'; with no changes neither write method is called
    schema = SheetSchema(
        (
            Column("id", "str", key=True),
            Column("name", "str"),
            Column("qty", "int"),
        )
    )
    fake_port_title = FakeSheets([["id", "name", "qty"]])
    sync(fake_port_title, schema, "O'Brien", [])
    assert fake_port_title.read_calls == ["'O''Brien'!A1:C"]

    # With changes on 'Stock'
    fake_port_changes = FakeSheets([["id", "name", "qty"], ["1", "Ann", "2"]])
    records = [
        {"id": "1", "name": "Ann", "qty": 10},
        {"id": "2", "name": "Bob", "qty": 20},
    ]
    sync(fake_port_changes, schema, "Stock", records)
    assert len(fake_port_changes.batch_update_calls) == 1
    assert fake_port_changes.batch_update_calls[0][1] == "RAW"
    assert len(fake_port_changes.append_rows_calls) == 1
    assert fake_port_changes.append_rows_calls[0][0] == "'Stock'!A1"
    assert fake_port_changes.append_rows_calls[0][2] == "RAW"

    # With no changes
    fake_port_no_changes = FakeSheets([["id", "name", "qty"], ["1", "Ann", "2"]])
    records_same = [{"id": "1", "name": "Ann", "qty": 2}]
    sync(fake_port_no_changes, schema, "Stock", records_same)
    assert len(fake_port_no_changes.batch_update_calls) == 0
    assert len(fake_port_no_changes.append_rows_calls) == 0


def test_acceptance_limits_and_empty_rows() -> None:
    # 10_001 records raise SyncError with code 'too_many_rows' before any port call;
    # trailing sheet rows that are [] or all '' are ignored, short rows are padded with '',
    # and a non-empty row with an empty key cell raises 'invalid_value' naming row 4
    schema = SheetSchema(
        (
            Column("id", "str", key=True),
            Column("name", "str"),
            Column("qty", "int"),
        )
    )
    many_records = [{"id": str(i), "name": "name", "qty": i} for i in range(10_001)]
    fake_port = FakeSheets()
    with pytest.raises(SyncError) as exc_too_many:
        sync(fake_port, schema, "Stock", many_records)
    assert exc_too_many.value.code == "too_many_rows"
    assert len(fake_port.read_calls) == 0

    # Trailing rows that are [] or all '' ignored, short row padded
    values = [
        ["id", "name", "qty"],
        ["1", "Ann"],  # short row, should be padded to ['1', 'Ann', '']
        [],  # trailing empty
        ["", "", ""],  # trailing empty
    ]
    plan = plan_sync(schema, "Stock", values, [{"id": "1", "name": "Ann", "qty": 0}])
    assert plan.updates == [RangeUpdate("'Stock'!A2:C2", [["1", "Ann", "0"]])]

    # Non-empty row with empty key cell naming row 4
    bad_values = [
        ["id", "name", "qty"],  # row 1
        ["1", "Ann", "2"],  # row 2
        ["2", "Bob", "3"],  # row 3
        ["", "Cy", "4"],  # row 4 has empty key
    ]
    with pytest.raises(SyncError) as exc_key:
        plan_sync(schema, "Stock", bad_values, [{"id": "1", "name": "Ann", "qty": 2}])
    assert exc_key.value.code == "invalid_value"
    assert "row 4" in str(exc_key.value)


def test_schema_validations() -> None:
    with pytest.raises(SyncError) as exc_empty:
        SheetSchema(())
    assert exc_empty.value.code == "invalid_schema"

    with pytest.raises(SyncError) as exc_name:
        SheetSchema((Column("   ", "str", key=True),))
    assert exc_name.value.code == "invalid_schema"

    with pytest.raises(SyncError) as exc_dup:
        SheetSchema(
            (
                Column("id", "str", key=True),
                Column("id", "int"),
            )
        )
    assert exc_dup.value.code == "invalid_schema"


def test_serialize_type_checks() -> None:
    col_key = Column("id", "str", key=True)
    with pytest.raises(SyncError) as exc_none_key:
        serialize(col_key, None)
    assert exc_none_key.value.code == "invalid_value"

    with pytest.raises(SyncError) as exc_empty_key:
        serialize(col_key, "")
    assert exc_empty_key.value.code == "invalid_value"

    with pytest.raises(SyncError) as exc_bad_str:
        serialize(Column("name", "str"), 123)
    assert exc_bad_str.value.code == "invalid_value"

    with pytest.raises(SyncError) as exc_bad_bool:
        serialize(Column("active", "bool"), "true")
    assert exc_bad_bool.value.code == "invalid_value"

    with pytest.raises(SyncError) as exc_bad_date:
        serialize(Column("dt", "date"), datetime.datetime.now())
    assert exc_bad_date.value.code == "invalid_value"

    with pytest.raises(SyncError) as exc_bad_dec_bool:
        serialize(Column("price", "decimal"), True)
    assert exc_bad_dec_bool.value.code == "invalid_value"

    with pytest.raises(SyncError) as exc_bad_dec_str:
        serialize(Column("price", "decimal"), "1.23")
    assert exc_bad_dec_str.value.code == "invalid_value"

    with pytest.raises(SyncError) as exc_nan:
        serialize(Column("price", "decimal"), decimal.Decimal("NaN"))
    assert exc_nan.value.code == "invalid_value"

    assert serialize(Column("price", "decimal"), 42) == "42"


def test_empty_sheet_and_missing_record_field() -> None:
    schema = SheetSchema((Column("id", "str", key=True), Column("val", "str")))
    with pytest.raises(SyncError) as exc_empty:
        plan_sync(schema, "Tab", [], [])
    assert exc_empty.value.code == "header_mismatch"

    with pytest.raises(SyncError) as exc_missing:
        plan_sync(schema, "Tab", [["id", "val"]], [{"id": "1"}])
    assert exc_missing.value.code == "invalid_value"
    assert "val" in str(exc_missing.value)


def test_duplicate_key_in_sheet() -> None:
    schema = SheetSchema((Column("id", "str", key=True), Column("val", "str")))
    values = [["id", "val"], ["1", "a"], ["1", "b"]]
    with pytest.raises(SyncError) as exc:
        plan_sync(schema, "Tab", values, [])
    assert exc.value.code == "duplicate_key"


def test_port_error_propagates() -> None:
    class FailingPort(SheetsPort):
        def read_values(self, range_a1: str) -> list[list[str]]:
            raise RuntimeError("Network connection refused")

        def batch_update(
            self, updates: Sequence[RangeUpdate], *, value_input_option: Literal["RAW"]
        ) -> None:
            pass

        def append_rows(
            self,
            range_a1: str,
            rows: Sequence[Sequence[str]],
            *,
            value_input_option: Literal["RAW"],
        ) -> None:
            pass

    schema = SheetSchema((Column("id", "str", key=True),))
    with pytest.raises(RuntimeError, match="Network connection refused"):
        sync(FailingPort(), schema, "Sheet1", [{"id": "1"}])
