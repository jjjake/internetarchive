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

## Key Dependencies

- `requests` - HTTP client
- `jsonpatch` - JSON patching for metadata updates
- `tqdm` - Progress bars
- `responses` - HTTP mocking for tests

## Contributing Notes

- PRs require tests and must pass ruff linting
- Avoid introducing new dependencies
- Support Python 3.9+
