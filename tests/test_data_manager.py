from __future__ import annotations

from types import TracebackType
from typing import Any, cast

import pandas as pd

from msTools.data_manager import DataManager


class FakeCursor:
    def __init__(
        self,
        *,
        fetchone_values: list[tuple[int] | None] | None = None,
        fetchall_value: list[tuple[Any, ...]] | None = None,
        description: list[tuple[str]] | None = None,
        rowcount: int = 1,
    ) -> None:
        self.fetchone_values = list(fetchone_values or [])
        self.fetchall_value = list(fetchall_value or [])
        self.description = description or [("id",), ("codeid",)]
        self.executed: list[tuple[object, object]] = []
        self.rowcount = rowcount

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def execute(self, query: Any, params: Any = None) -> None:
        self.executed.append((query, params))

    def fetchone(self) -> tuple[int] | None:
        return self.fetchone_values.pop(0)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.fetchall_value


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = 0

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def test_store_codeid_returns_existing_identifier_without_crashing() -> None:
    manager = DataManager.__new__(DataManager)
    cursor = FakeCursor(fetchone_values=[None, (42,)])
    manager.pg_conn = cast(Any, FakeConnection(cursor))

    codeid_id, is_new = DataManager.store_codeid(manager, "abc123", verbose=2)

    assert codeid_id == 42
    assert is_new is False
    assert len(cursor.executed) == 2


def test_recover_activity_all_batches_identifier_lookup() -> None:
    manager = DataManager.__new__(DataManager)
    cursor = FakeCursor(fetchall_value=[(10, "L001"), (11, "R001")])
    manager.pg_conn = cast(Any, FakeConnection(cursor))

    activity_all = pd.DataFrame(
        [
            {
                "start_time": pd.Timestamp("2026-01-01T10:00:00"),
                "end_time": pd.Timestamp("2026-01-01T10:05:00"),
                "codeid_ids": [10, 11],
                "active_legs": ["Left", "Right"],
            }
        ]
    )

    result = DataManager.recover_activity_all(manager, activity_all)

    assert len(cursor.executed) == 1
    assert cursor.executed[0][1] == ([10, 11],)
    assert result["CodeID"].tolist() == ["L001", "R001"]
    assert result["foot"].tolist() == ["Left", "Right"]


def test_update_codeid_seen_at_uses_min_max_semantics() -> None:
    manager = DataManager.__new__(DataManager)
    cursor = FakeCursor(rowcount=1)
    manager.pg_conn = cast(Any, FakeConnection(cursor))

    DataManager.update_codeid_seen_at(
        manager,
        codeid_id=42,
        first_seen_at="2024-06-25 08:30:00",
        last_seen_at="2024-06-25 09:15:00",
    )

    assert len(cursor.executed) == 1
    query, params = cursor.executed[0]
    assert "LEAST" in str(query)
    assert "GREATEST" in str(query)
    assert params == (
        pd.Timestamp("2024-06-25 06:30:00", tz="UTC"),
        pd.Timestamp("2024-06-25 06:30:00", tz="UTC"),
        pd.Timestamp("2024-06-25 07:15:00", tz="UTC"),
        pd.Timestamp("2024-06-25 07:15:00", tz="UTC"),
        42,
    )
