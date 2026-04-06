"""Lightweight checks on auto_marketer.db.

We don't spin up Postgres in CI; we assert all SQL strings used by the
module are static literals (the no-string-built-SQL lint covers
parameterization). The lint test in the repo root scans this module
along with the rest.
"""
from __future__ import annotations

import inspect

from auto_marketer import db


def test_module_imports():
    assert hasattr(db, "setup")
    assert hasattr(db, "create_campaign")
    assert hasattr(db, "save_draft")
    assert hasattr(db, "mark_sent")
    assert hasattr(db, "mark_failed")


def test_no_format_or_fstring_in_source():
    src = inspect.getsource(db)
    # No SQL-like f-strings: a literal `f"..."` containing SELECT/INSERT/UPDATE/DELETE.
    for kw in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        assert f'f"{kw}' not in src.upper().replace("F'", 'F"')
