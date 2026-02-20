# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python library and `ia` CLI for interacting with archive.org. Used for uploading, downloading, searching, and managing items and their metadata. Also provides catalog task management and account administration utilities. Items are identified by a unique identifier and contain files and metadata.

## Common Commands

```bash
# Install for development
pip install -e .

# Run tests
pytest

# Run tests with linting
ruff check && pytest

# Run a single test file
pytest tests/test_api.py

# Run a specific test
pytest tests/test_api.py::test_get_item

# Multi-version testing (requires Python 3.9-3.14 installed)
tox

# Lint only
ruff check

# Build docs
pip install -r docs/requirements.txt
cd docs && make html
```

## Architecture

The library has a three-layer architecture:

**Layer 1 - Public API (`internetarchive/api.py`)**
Convenience functions that wrap the core classes: `get_item()`, `search_items()`, `upload()`, `download()`, `modify_metadata()`, `delete()`, `configure()`, `get_session()`.

**Layer 2 - Core Classes**
- `ArchiveSession` (`session.py`) - Extends `requests.Session`. Manages config, credentials, HTTP headers, connection pooling.
- `Item` (`item.py`) - Represents an Archive.org item. Contains files, metadata, and methods for download/upload/modify.
- `File` (`files.py`) - Represents a single file within an item. Handles download, delete, checksum verification.
- `Search` (`search.py`) - Query interface with pagination and field selection.

**Layer 3 - Supporting Modules**
- `config.py` - INI-based configuration (credentials at `~/.config/internetarchive/ia.ini` or `~/.ia`)
- `iarequest.py` - HTTP request builders (`MetadataRequest`, `S3Request`)
- `auth.py` - S3 authentication handlers
- `catalog.py` - Catalog task management

**CLI (`internetarchive/cli/`)**
- Entry point: `ia.py:main()` → registered as `ia` console script
- Subcommands: `ia_download.py`, `ia_upload.py`, `ia_metadata.py`, `ia_search.py`, `ia_list.py`, `ia_delete.py`, `ia_copy.py`, `ia_move.py`, `ia_tasks.py`, `ia_configure.py`, etc.

## Code Style

- Line length: 90 characters
- Linter: ruff (configured in `pyproject.toml`)
- Formatter: black
- Type checking: mypy (type stubs in `options.extras_require` under `types`)
- Docstrings: Always add or update docstrings when editing or adding code. Use Sphinx-style format with `:param:`, `:returns:`, and `:raises:` sections

## Key Dependencies

- `requests` - HTTP client
- `jsonpatch` - JSON patching for metadata updates
- `tqdm` - Progress bars
- `responses` - HTTP mocking for tests

## Contributing Notes

- All new features should be developed on a feature branch, not directly on master
- PRs require tests and must pass ruff linting
- New features must include documentation updates (see `docs/source/`)
- Avoid introducing new dependencies
- Support Python 3.9+

## Git Workflow

- `main` is protected by GitHub rulesets — never push directly
- Always create feature branches and open PRs
- Required CI checks must pass before merge: `lint_python`, `pre-commit`, `install_internetarchive`, `tox`
- **NEVER push without running `ruff check && pytest` locally first and confirming all tests pass.** No exceptions.

## Versioning

After a release, bump the version to a dev suffix (e.g., `5.7.3.dev0`) to indicate development builds. The version in `internetarchive/__version__.py` should always be either:
- A release version (e.g., `5.7.2`) - only during the release process
- A dev version (e.g., `5.7.3.dev0`) - at all other times

When merging new features to master, increment the dev number if needed (e.g., `5.7.3.dev0` → `5.7.3.dev1`).

## Releasing

To release a new version (must be on master with clean working directory):

```bash
# 1. Prepare release (updates __version__.py and HISTORY.rst date)
make prepare-release RELEASE=X.Y.Z

# 2. Review and commit version changes
git diff
git add -A && git commit -m "Bump version to X.Y.Z"

# 3. Publish to PyPI + archive.org + GitHub
make publish-all
```

Individual release targets:
- `make publish` - PyPI + GitHub release (no binary)
- `make publish-all` - PyPI + pex binary + GitHub release
- `make publish-binary` - pex binary only (after PyPI release)

The release process will:
- Run tests and linting
- Build the package
- Build and test the pex binary
- Create and push a git tag
- Upload to PyPI
- Upload binary to archive.org
- Create a GitHub release with changelog from HISTORY.rst

## Related

- [internet-archive-skills](https://github.com/internetarchive/internet-archive-skills) — AI-facing documentation for the `ia` CLI and Python library. Consult when working on upload, metadata, item creation, or search logic — it documents Archive.org platform constraints (item size/file limits, metadata schema, identifier rules, rate limiting). Update if CLI or API interfaces change.
- Latest skill docs: https://raw.githubusercontent.com/internetarchive/internet-archive-skills/main/SKILL.md
