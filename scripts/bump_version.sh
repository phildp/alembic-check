#!/bin/bash
set -e

NEW_VERSION=$1

echo "Bumping version to $NEW_VERSION"

# Update version in pyproject.toml
sed -i "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml

# Commit the change (semantic-release will commit it as part of the release)
git add pyproject.toml
