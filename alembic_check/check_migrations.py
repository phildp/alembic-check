#!/usr/bin/env python3
"""
Script to validate Alembic migration chains.

This script checks for duplicate down_revision values in Alembic migrations.
It parses each migration file to extract the revision and down_revision,
and then checks for any down_revision values that appear more than once.

Usage:
    python -m alembic_check.check_migrations <migrations_directory>
"""

import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple, List

from alembic_check.exceptions import (
    CircularDependencyError,
    DuplicateDownRevisionError,
    DuplicateRevisionError,
    MigrationError,
    MigrationFileError,
    MissingDownRevisionError,
    MultipleInitialMigrationsError,
)


def read_migration_file(file_path: Path) -> Tuple[str, Optional[str]]:
    """
    Reads a migration file and extract revision and down_revision.

    :param file_path: Path to the migration file.

    :return: Tuple of (revision, down_revision). down_revision will be None for initial migrations.

    :raises: MigrationFileError: If the file is malformed or missing required fields.
    """
    content = file_path.read_text()

    revision_match = re.search(r'revision\s*=\s*["\']([^"\']+)["\']', content)
    if not revision_match:
        raise MigrationFileError(f"Could not find revision in {file_path.name}")

    down_revision_match = re.search(
        r'down_revision\s*=\s*(?:None|["\']([^"\']*)["\'])', content
    )

    revision = revision_match.group(1)
    down_revision = None
    if down_revision_match:
        down_revision = (
            down_revision_match.group(1)
            if down_revision_match.group(1) is not None
            else None
        )
        if down_revision == "":
            raise MigrationFileError(
                f"Empty down_revision found in {file_path.name}. Perhaps you meant to use None?"
            )

    return revision, down_revision


def build_migration_chain(migrations_dir: Path) -> Dict[str, Optional[str]]:
    """
    Builds a migration chain from a directory of migration files.

    :param migrations_dir: Path to the directory containing migration files.

    :return: Dictionary mapping revision IDs to their down_revision values.
        None indicates an initial migration.

    :raises: MigrationFileError: If the migrations directory doesn't exist or if any file is malformed.
    :raises: DuplicateRevisionError: If duplicate revisions are found.
    """
    if not migrations_dir.exists():
        raise MigrationFileError(f"Migrations directory not found: {migrations_dir}")

    migrations: Dict[str, Optional[str]] = {}

    for file_path in migrations_dir.glob("*.py"):
        try:
            revision, down_revision = read_migration_file(file_path)

            # Check for duplicate revisions
            if revision in migrations.keys():
                raise DuplicateRevisionError(f"Duplicate revision '{revision}' found.")
            if down_revision in migrations.values():
                raise DuplicateDownRevisionError(
                    f"Duplicate down_revision '{down_revision}' found."
                )

            migrations[revision] = down_revision
        except MigrationFileError:
            raise

    return migrations


def validate_migration_chain(
    migrations: Dict[str, Optional[str]],
) -> None:
    """
    Validates that migrations form a valid chain.

    :param migrations: Dictionary mapping revision IDs to their down_revision values.
        None indicates an initial migration.

    :return: None, if the migration chain is valid.
    :raises: MultipleInitialMigrationsError: If multiple migrations have no down_revision.
    :raises: MissingDownRevisionError: If a migration points to a non-existent down_revision.
    :raises: CircularDependencyError: If a migration chain contains a cycle.
    :raises: DuplicateDownRevisionError: If multiple migrations have the same down_revision.
    """
    if not migrations:
        return None

    sorted_migrations = sorted(migrations.items(), key=lambda x: x[0])

    # Check for multiple initial migrations
    initial_migrations = [rev for rev, down in sorted_migrations if down is None]
    if len(initial_migrations) > 1:
        raise MultipleInitialMigrationsError(
            f"Multiple initial migrations found (with None as down_revision): "
            f"{', '.join(initial_migrations)}"
        )

    # Check for missing down_revisions
    for rev, down in sorted_migrations:
        if down and down not in migrations.keys():
            raise MissingDownRevisionError(
                f"Migration '{rev}' points to non-existent revision '{down}'"
            )

    # Check for circular dependencies
    def check_cycle(start_revision: str) -> Optional[list[str]]:
        """Check if there's a cycle starting from the given revision."""
        path = []
        current = start_revision

        while current is not None:
            if current in path:
                # Found a cycle, return the path from the start of the cycle
                cycle_start = path.index(current)
                return path[cycle_start:] + [current]

            path.append(current)
            current = migrations.get(current)

        return None

    # Check for cycles starting from each revision
    for rev in migrations:
        cycle = check_cycle(rev)
        if cycle:
            raise CircularDependencyError(
                f"Circular dependency found: {' -> '.join(cycle)}"
            )

    # Check for duplicate down_revisions
    down_revisions: Dict[str, list[str]] = {}
    for rev, down in sorted_migrations:
        if down is not None:
            down_revisions.setdefault(down, []).append(rev)

    for down, revisions in down_revisions.items():
        if len(revisions) > 1:
            raise DuplicateDownRevisionError(
                f"Multiple migrations have the same down_revision '{down}': "
                f"{', '.join(revisions)}"
            )

    return None


def run_checks(migrations_dir: str) -> int:
    """
    Checks migration files in the given directory.

    :param migrations_dir: Path to the directory containing migration files.

    :return: 0 if all migrations are valid, 1 if there are any errors.
    """
    try:
        migrations = build_migration_chain(Path(migrations_dir))
        validate_migration_chain(migrations)
        return 0
    except MigrationError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1


def has_migration_changes(staged_files: List[str], migrations_dir: str) -> bool:
    """
    Check if any staged files are in the migrations directory.

    :param staged_files: List of staged file paths.
    :param migrations_dir: Path to the migrations directory.

    :return: True if any staged files are in the migrations directory, False otherwise.
    """
    migrations_path = Path(migrations_dir)
    return any(
        migrations_path in Path(f).parents or migrations_path == Path(f)
        for f in staged_files
    )


def main() -> int:
    args = (
        sys.argv[3:] if sys.argv[0] == "python" and "-m" in sys.argv else sys.argv[1:]
    )

    if len(args) < 1:
        print(
            "Usage: python -m alembic_check.check_migrations <migrations_directory> [staged_files...]",
            file=sys.stderr,
        )
        return 1

    migrations_dir = args[0]
    staged_files = args[1:]

    if staged_files and not has_migration_changes(staged_files, migrations_dir):
        return 0

    return run_checks(migrations_dir)


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
