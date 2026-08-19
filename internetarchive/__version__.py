"""Package version.

The version is derived from the git tag by hatch-vcs, which writes
``internetarchive/_version.py`` at build time. This module keeps the
historical ``internetarchive.__version__`` import working, and falls back to
the installed distribution metadata when ``_version.py`` is absent (for
example, when running from a source checkout that was never built).
"""

from __future__ import annotations

try:
    from ._version import __version__
except ImportError:  # pragma: no cover - only hit in an unbuilt checkout
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version('internetarchive')
    except PackageNotFoundError:
        __version__ = '0.0.0.dev0'

__all__ = ['__version__']
