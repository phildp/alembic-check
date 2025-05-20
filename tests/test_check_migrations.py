"""Tests for the migration validation logic."""

from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from alembic_check.check_migrations import (
    build_migration_chain,
    read_migration_file,
    validate_migration_chain,
    run_checks,
)
from alembic_check.exceptions import (
    CircularDependencyError,
    DuplicateDownRevisionError,
    DuplicateRevisionError,
    MigrationFileError,
    MissingDownRevisionError,
    MultipleInitialMigrationsError,
)


def test_read_migration_file(tmp_path: Path) -> None:
    """Test reading migration files with different configurations."""
    test_cases = [
        {
            "name": "initial migration",
            "content": """
# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = None
""",
            "expected": ("1a2b3c4d5e6f", None),
        },
        {
            "name": "migration with down_revision",
            "content": """
# revision identifiers, used by Alembic.
revision = '2b3c4d5e6f7g'
down_revision = '1a2b3c4d5e6f'
""",
            "expected": ("2b3c4d5e6f7g", "1a2b3c4d5e6f"),
        },
        {
            "name": "missing revision",
            "content": """
# revision identifiers, used by Alembic.
down_revision = None
""",
            "raises": MigrationFileError,
            "match": "Could not find revision",
        },
        {
            "name": "empty down_revision",
            "content": """
# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = ''
""",
            "raises": MigrationFileError,
            "match": "Empty down_revision",
        },
    ]

    for case in test_cases:
        # given
        file_path = tmp_path / "test.py"
        file_path.write_text(case["content"])

        # when/then
        if "raises" in case:
            with pytest.raises(case["raises"], match=case["match"]):
                read_migration_file(file_path)
        else:
            revision, down_revision = read_migration_file(file_path)
            assert (revision, down_revision) == case[
                "expected"
            ], f"Failed test case: {case['name']}"


def test_build_migration_chain_happy_path(tmp_path: Path) -> None:
    # given
    directory = tmp_path / "valid_chain"
    directory.mkdir()

    (directory / "initial.py").write_text(
        """
# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = None
"""
    )
    (directory / "second.py").write_text(
        """
# revision identifiers, used by Alembic.
revision = '2b3c4d5e6f7g'
down_revision = '1a2b3c4d5e6f'
"""
    )

    # when
    migrations = build_migration_chain(directory)

    # then
    assert migrations == {
        "1a2b3c4d5e6f": None,
        "2b3c4d5e6f7g": "1a2b3c4d5e6f",
    }


def test_build_migration_chain_duplicate_revision(tmp_path: Path) -> None:
    # given
    directory = tmp_path / "duplicate_revision"
    directory.mkdir()

    (directory / "first.py").write_text(
        """
# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = None
"""
    )
    (directory / "second.py").write_text(
        """
# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'  # Same revision as first.py
down_revision = None
"""
    )

    # when/then
    with pytest.raises(
        DuplicateRevisionError,
        match="Duplicate revision '1a2b3c4d5e6f' found.",
    ):
        build_migration_chain(directory)


def test_build_migration_chain_duplicate_down_revision(tmp_path: Path) -> None:
    # given
    directory = tmp_path / "duplicate_down_revision"
    directory.mkdir()

    (directory / "first.py").write_text(
        """
# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = '3c4d5e6f7g8h'
"""
    )
    (directory / "second.py").write_text(
        """
# revision identifiers, used by Alembic.
revision = '2b3c4d5e6f7g'
down_revision = '3c4d5e6f7g8h'
"""
    )

    # when/then
    with pytest.raises(
        DuplicateDownRevisionError,
        match="Duplicate down_revision '3c4d5e6f7g8h' found.",
    ):
        build_migration_chain(directory)


def test_build_migration_chain_missing_directory() -> None:
    # given
    directory = Path("/nonexistent")

    # when/then
    with pytest.raises(MigrationFileError, match="Migrations directory not found"):
        build_migration_chain(directory)


def test_build_migration_chain_malformed_file(tmp_path: Path) -> None:
    # given
    directory = tmp_path / "malformed"
    directory.mkdir()

    (directory / "malformed.py").write_text(
        """
# revision identifiers, used by Alembic.
down_revision = None  # Missing revision
"""
    )

    # when/then
    with pytest.raises(
        MigrationFileError, match="Could not find revision in malformed.py"
    ):
        build_migration_chain(directory)


def test_validate_migration_chain() -> None:
    test_cases = [
        {
            "name": "valid chain",
            "migrations": {
                "1a2b3c4d5e6f": None,  # Initial migration
                "2b3c4d5e6f7g": "1a2b3c4d5e6f",  # Points to initial
                "3c4d5e6f7g8h": "2b3c4d5e6f7g",  # Points to second
            },
        },
        {
            "name": "duplicate down_revision",
            "migrations": {
                "1a2b3c4d5e6f": None,
                "2b3c4d5e6f7g": "1a2b3c4d5e6f",
                "3c4d5e6f7g8h": "2b3c4d5e6f7g",
                "4d5e6f7g8h9i": "2b3c4d5e6f7g",  # Points to same parent as third
            },
            "raises": DuplicateDownRevisionError,
            "match": "Multiple migrations have the same down_revision '2b3c4d5e6f7g': 3c4d5e6f7g8h, 4d5e6f7g8h9i",
        },
        {
            "name": "missing down_revision",
            "migrations": {
                "1a2b3c4d5e6f": None,
                "2b3c4d5e6f7g": "1a2b3c4d5e6f",
                "3c4d5e6f7g8h": "nonexistent",  # Points to non-existent revision
            },
            "raises": MissingDownRevisionError,
            "match": "Migration '3c4d5e6f7g8h' points to non-existent revision 'nonexistent'",
        },
        {
            "name": "multiple initial",
            "migrations": {
                "1a2b3c4d5e6f": None,
                "2b3c4d5e6f7g": "1a2b3c4d5e6f",
                "3c4d5e6f7g8h": None,  # Second initial migration
            },
            "raises": MultipleInitialMigrationsError,
            "match": "Multiple initial migrations found (with None as down_revision): 1a2b3c4d5e6f, 3c4d5e6f7g8h",
        },
        {
            "name": "empty chain",
            "migrations": {},
        },
        {
            "name": "circular dependency",
            "migrations": {
                "1a2b3c4d5e6f": None,
                "2b3c4d5e6f7g": "3c4d5e6f7g8h",
                "3c4d5e6f7g8h": "2b3c4d5e6f7g",
            },
            "raises": CircularDependencyError,
            "match": "Circular dependency found: 2b3c4d5e6f7g -> 3c4d5e6f7g8h -> 2b3c4d5e6f7g",
        },
    ]

    for case in test_cases:
        # when/then
        if "raises" in case:
            with pytest.raises(case["raises"]) as exc:
                validate_migration_chain(case["migrations"])
            assert str(exc.value) == case["match"], f"Failed test case: {case['name']}"
        else:
            res = validate_migration_chain(case["migrations"])
            assert res is None, f"Failed test case: {case['name']}"


@patch("alembic_check.check_migrations.build_migration_chain")
@patch("alembic_check.check_migrations.validate_migration_chain")
def test_run_checks(mock_validate: Mock, mock_build: Mock) -> None:
    test_cases = [
        {
            "name": "successful validation",
            "build_return": {"1a2b3c4d5e6f": None, "2b3c4d5e6f7g": "1a2b3c4d5e6f"},
            "validate_return": (True, []),
            "expected": 0,
        },
        {
            "name": "failed validation",
            "build_return": {"1a2b3c4d5e6f": None, "2b3c4d5e6f7g": "1a2b3c4d5e6f"},
            "validate_return": (False, ["Error message"]),
            "expected": 1,
        },
        {
            "name": "build error",
            "build_return": MigrationFileError("Directory not found"),
            "validate_return": None,
            "expected": 1,
        },
    ]

    for case in test_cases:
        # given
        if isinstance(case["build_return"], Exception):
            mock_build.side_effect = case["build_return"]
        else:
            mock_build.return_value = case["build_return"]

        if case["validate_return"] is not None:
            mock_validate.return_value = case["validate_return"]

        # when/then
        assert (
            run_checks("migrations/") == case["expected"]
        ), f"Failed test case: {case['name']}"
