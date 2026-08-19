.PHONY: docs clean clean-dist test binary test-binary check-release check-history \
        build check-dist tag push-tag upload-pypi publish-binary-upload github-release \
        publish publish-binary docs-init init release prepare-history

# The package version is derived from the git tag by hatch-vcs; there is no
# version string stored in the tree. Derive the same value here for artifact
# names and release notes. On an exact tag this is e.g. 5.11.2; between tags it
# is e.g. 5.11.1-3-gabc1234.
VERSION=$(shell git describe --tags --match 'v[0-9]*' 2>/dev/null | sed 's/^v//')

# ============ Development ============
init:
	uv pip install -e '.[all]'

clean:
	find . -type f -name '*\.pyc' -delete
	find . -type d -name '__pycache__' -delete

clean-dist:
	rm -rf dist/ build/ *.egg-info

test:
	ruff check
	ruff format --check
	pytest

# ============ Documentation ============
docs-init:
	uv pip install -r docs/requirements.txt

docs:
	cd docs && make html
	@echo "\033[95m\n\nBuild successful! View the docs homepage at docs/build/html/index.html.\n\033[0m"

# ============ Binary Building ============
binary:
	pex . --python-shebang='/usr/bin/env python3' --python python3 -e internetarchive.cli.ia:main -o ia-$(VERSION)-py3-none-any.pex -r pex-requirements.txt --use-pep517

test-binary: binary
	@echo "Testing pex binary..."
	./ia-$(VERSION)-py3-none-any.pex --version
	./ia-$(VERSION)-py3-none-any.pex --help > /dev/null
	./ia-$(VERSION)-py3-none-any.pex metadata --help > /dev/null
	@echo "Pex binary tests passed!"

# ============ Release Preparation ============
# Date the changelog heading for an upcoming release: `X.Y.Z (?)` -> `X.Y.Z (2026-08-19)`.
# This is the only file a release PR needs to touch -- the version itself comes
# from the tag.
# Usage: make prepare-history RELEASE=5.11.2
prepare-history:
ifndef RELEASE
	$(error RELEASE is required. Usage: make prepare-history RELEASE=5.11.2)
endif
	@python3 -c "import pathlib, datetime; \
		h = pathlib.Path('HISTORY.rst'); \
		h.write_text(h.read_text().replace('$(RELEASE) (?)', '$(RELEASE) (' + datetime.date.today().isoformat() + ')', 1))"
	@echo "Dated the $(RELEASE) section in HISTORY.rst"

# ============ Release Validation ============
check-release:
ifndef RELEASE
	$(error RELEASE is required. Usage: make release RELEASE=5.11.2)
endif
	@if echo "$(RELEASE)" | grep -q 'dev'; then \
		echo "Error: cannot release a dev version ($(RELEASE))"; exit 1; \
	fi
	@if [ "$$(git rev-parse --abbrev-ref HEAD)" != "master" ]; then \
		echo "Error: Must be on master branch to release"; exit 1; \
	fi
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working directory is not clean"; exit 1; \
	fi
	@if git rev-parse v$(RELEASE) >/dev/null 2>&1; then \
		echo "Error: Tag v$(RELEASE) already exists"; exit 1; \
	fi
	@git fetch origin master
	@if [ "$$(git rev-parse HEAD)" != "$$(git rev-parse origin/master)" ]; then \
		echo "Error: HEAD is not up to date with origin/master"; exit 1; \
	fi
	@echo "Release checks passed!"

# The GitHub release notes are extracted from HISTORY.rst, so a missing or
# undated section would produce an empty release body.
check-history:
	@grep -q '^$(RELEASE) (2' HISTORY.rst || { \
		echo "Error: HISTORY.rst has no dated '$(RELEASE) (YYYY-MM-DD)' section."; \
		echo "Run: make prepare-history RELEASE=$(RELEASE)"; exit 1; \
	}
	@echo "Changelog section for $(RELEASE) found."

# ============ Release Building ============
build: clean-dist
	uv build

# Validate built artifacts (metadata + long_description rendering) before any upload
check-dist:
	twine check dist/*

# ============ Release Publishing ============
tag:
	git tag -a v$(RELEASE) -m 'version $(RELEASE)'

# master is branch-protected; push only the tag, never the branch.
push-tag:
	git push origin v$(RELEASE)

upload-pypi:
	twine upload --repository pypi ./dist/*

publish-binary-upload:
	./ia-$(VERSION)-py3-none-any.pex upload ia-pex ia-$(VERSION)-py3-none-any.pex --no-derive
	./ia-$(VERSION)-py3-none-any.pex upload ia-pex ia-$(VERSION)-py3-none-any.pex --remote-name=ia --no-derive

# Extract the curated changelog section and create the GitHub release. The curated notes
# are prepended to GitHub's auto-generated "What's Changed" / "New Contributors" /
# "Full Changelog" section (--generate-notes). reST double-backticks are collapsed to
# Markdown single-backticks since the release body is rendered as Markdown.
github-release:
	@echo "Extracting changelog for v$(VERSION)..."
	@awk '/^$(VERSION) /{found=1; next} found && /^\++$$/{next} found && /^[0-9]+\.[0-9]+\.[0-9]+ /{exit} found' HISTORY.rst \
		| sed 's/``/`/g' > /tmp/ia-release-notes-$(VERSION).md
	@test -s /tmp/ia-release-notes-$(VERSION).md || \
		{ echo "Error: extracted release notes are empty -- check the '$(VERSION)' heading in HISTORY.rst"; exit 1; }
	gh release create v$(VERSION) \
		--title "Version $(VERSION)" \
		--notes-file /tmp/ia-release-notes-$(VERSION).md \
		--generate-notes
	@rm -f /tmp/ia-release-notes-$(VERSION).md
	@echo "GitHub release created!"

# ============ Main Release Targets ============

# The normal release: validate, then push the tag. Pushing a v* tag triggers the
# `release` workflow, which tests, builds the sdist/wheel and pex, publishes to
# PyPI via Trusted Publishing, and creates the GitHub release.
# Usage: make release RELEASE=5.11.2
release: check-release check-history tag push-tag
	@echo "\n\033[92mTag v$(RELEASE) pushed. The release workflow takes it from here:\033[0m"
	@echo "  https://github.com/jjjake/internetarchive/actions/workflows/release.yml"
	@echo "  Then run: make publish-binary"

# Laptop fallback for when the release workflow is unavailable: does everything
# the workflow does, locally.
# Usage: make publish RELEASE=5.11.2
publish: check-release check-history test tag push-tag build check-dist binary test-binary upload-pypi publish-binary-upload github-release
	@echo "\n\033[92mRelease v$(RELEASE) published to PyPI, archive.org, and GitHub!\033[0m"

# Binary-only publish. CI has no archive.org credentials, so this step stays
# manual after every release.
publish-binary: binary test-binary publish-binary-upload
	@echo "\n\033[92mBinary v$(VERSION) published to archive.org!\033[0m"
