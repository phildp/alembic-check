"""Tests for the migration validation logic."""

from io import StringIO
from pathlib import Path
import sys

import pytest
from unittest.mock import Mock, patch

from alembic_check.check_migrations import (
    build_migration_chain,
    has_migration_changes,
    main,
    read_migration_file,
    run_checks,
    validate_migration_chain,
)
from alembic_check.exceptions import (
    CircularDependencyError,
    DuplicateDownRevisionError,
    DuplicateRevisionError,
    MigrationError,
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


def test_has_migration_changes():
    test_cases = [
        {
            "name": "no staged files",
            "staged_files": [],
            "migrations_dir": Path("migrations"),
            "expected": False,
        },
        {
            "name": "staged file in migrations directory",
            "staged_files": ["migrations/001_initial.py"],
            "migrations_dir": Path("migrations"),
            "expected": True,
        },
        {
            "name": "staged file in subdirectory of migrations",
            "staged_files": ["migrations/subdir/file.py"],
            "migrations_dir": Path("migrations"),
            "expected": True,
        },
        {
            "name": "migrations directory itself is staged",
            "staged_files": ["migrations"],
            "migrations_dir": Path("migrations"),
            "expected": True,
        },
        {
            "name": "multiple files, one in migrations",
            "staged_files": [
                "src/file.py",
                "migrations/001_initial.py",
                "tests/test.py",
            ],
            "migrations_dir": Path("migrations"),
            "expected": True,
        },
        {
            "name": "no files in migrations directory",
            "staged_files": ["src/file.py", "tests/test.py"],
            "migrations_dir": Path("migrations"),
            "expected": False,
        },
        {
            "name": "staged file with same name as migrations directory",
            "staged_files": ["src/migrations.py"],
            "migrations_dir": Path("migrations"),
            "expected": False,
        },
        {
            "name": "staged file in parent directory of migrations",
            "staged_files": ["../migrations/001_initial.py"],
            "migrations_dir": Path("migrations"),
            "expected": False,
        },
    ]

    for case in test_cases:
        # when
        result = has_migration_changes(case["staged_files"], case["migrations_dir"])

        # then
        assert result == case["expected"], f"Failed test case: {case['name']}"


def test_no_revisions_only_init(tmp_path: Path) -> None:
    # given
    directory = tmp_path / "no_revisions_only_init"
    directory.mkdir()

    (directory / "__init__.py").write_text(
        """
# revision identifiers, used by Alembic.
# empty file
"""
    )

    # when/then
    with pytest.raises(
        MigrationFileError, match="No migration files found in the migrations directory"
    ):
        build_migration_chain(directory)


def test_no_revisions_only_empty_files(tmp_path: Path) -> None:
    # given
    directory = tmp_path / "no_revisions_only_empty_files"
    directory.mkdir()

    (directory / "empty.py").write_text(
        """
# empty file
"""
    )
    # when/then
    with pytest.raises(MigrationFileError, match="Could not find revision in empty.py"):
        build_migration_chain(directory)


def test_run_checks_directory_not_found() -> None:
    # given
    directory = Path("/nonexistent")
    argv = ["alembic-check", str(directory)]

    # when/then
    with patch.object(sys, "argv", argv):
        with patch("sys.stderr", new=StringIO()) as mock_stderr:
            assert main() == 1
            assert "Migrations directory does not exist" in mock_stderr.getvalue()


@patch("alembic_check.check_migrations.validate_migration_chain")
@patch("alembic_check.check_migrations.build_migration_chain")
def test_run_checks(
    mock_build_migration_chain: Mock, mock_validate_migration_chain: Mock
) -> None:
    # given
    directory = Path("migrations")
    mock_build_migration_chain.return_value = {
        "1a2b3c4d5e6f": None,
        "2b3c4d5e6f7g": "1a2b3c4d5e6f",
    }
    mock_validate_migration_chain.return_value = None
    # when/then
    assert run_checks(directory) == 0


@patch("alembic_check.check_migrations.validate_migration_chain")
@patch("alembic_check.check_migrations.build_migration_chain")
def test_run_checks_error(
    mock_build_migration_chain: Mock, mock_validate_migration_chain: Mock
) -> None:
    # given
    directory = Path("migrations")
    mock_build_migration_chain.side_effect = MigrationError("Test error")
    mock_validate_migration_chain.return_value = None
    # when/then
    with patch("sys.stderr", new=StringIO()) as mock_stderr:
        assert run_checks(directory) == 1
        assert "Error: Test error" in mock_stderr.getvalue()
    assert run_checks(directory) == 1
