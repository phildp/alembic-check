"""Custom exceptions for Alembic migration validation."""


class MigrationError(Exception):
    """Base exception for all migration-related errors."""


class MigrationFileError(MigrationError):
    """Raised when there's an error reading or parsing a migration file."""


class DuplicateRevisionError(MigrationError):
    """Raised when a revision ID appears in multiple migration files."""


class InvalidMigrationChainError(MigrationError):
    """Raised when the migration chain has structural issues."""


class MultipleInitialMigrationsError(InvalidMigrationChainError):
    """Raised when multiple migrations have no down_revision."""


class MissingDownRevisionError(InvalidMigrationChainError):
    """Raised when a migration points to a non-existent down_revision."""


class DuplicateDownRevisionError(InvalidMigrationChainError):
    """Raised when multiple migrations have the same down_revision."""


class CircularDependencyError(InvalidMigrationChainError):
    """Raised when a migration chain contains a cycle."""
