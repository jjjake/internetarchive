.PHONY: docs clean clean-dist test binary test-binary check-release check-version \
        build check-dist tag push-tag upload-pypi publish-binary-upload github-release \
        publish publish-binary docs-init init prepare-release

VERSION=$(shell grep -m1 __version__ internetarchive/__version__.py | cut -d\' -f2)

# ============ Development ============
init:
	pip install -e '.[all]'

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
	pip install -r docs/requirements.txt

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
# Usage: make prepare-release RELEASE=5.7.2
prepare-release:
ifndef RELEASE
	$(error RELEASE is required. Usage: make prepare-release RELEASE=5.7.2)
endif
	@if echo "$(RELEASE)" | grep -q 'dev'; then \
		echo "Error: RELEASE should not contain 'dev'"; exit 1; \
	fi
	sed -i '' "s/__version__ = '.*'/__version__ = '$(RELEASE)'/" internetarchive/__version__.py
	sed -i '' "s/^$(RELEASE) (?)$$/$(RELEASE) ($$(date +%Y-%m-%d))/" HISTORY.rst
	@echo "Updated to version $(RELEASE) with date $$(date +%Y-%m-%d)"
	@echo "Review changes and commit when ready"

# ============ Release Validation ============
check-release:
	@if [ "$$(git rev-parse --abbrev-ref HEAD)" != "master" ]; then \
		echo "Error: Must be on master branch to release"; exit 1; \
	fi
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working directory is not clean"; exit 1; \
	fi
	@if git rev-parse v$(VERSION) >/dev/null 2>&1; then \
		echo "Error: Tag v$(VERSION) already exists"; exit 1; \
	fi
	@echo "Release checks passed!"

check-version:
	@if echo "$(VERSION)" | grep -q 'dev'; then \
		echo "Error: Cannot release dev version $(VERSION)"; exit 1; \
	fi
	@echo "Version $(VERSION) is valid for release"

# ============ Release Building ============
build: clean-dist
	python -m build

# Validate built artifacts (metadata + long_description rendering) before any upload
check-dist:
	twine check dist/*

# ============ Release Publishing ============
tag:
	git tag -a v$(VERSION) -m 'version $(VERSION)'

# master is branch-protected; push only the tag, never the branch. The version
# bump is already on master via its release PR.
push-tag:
	git push origin v$(VERSION)

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

# Full release. We always publish everywhere, so this is the single release target:
# it tests, builds the sdist/wheel and pex binary, tags and pushes the tag (never
# master), uploads to PyPI and the pex to the archive.org item, and creates the
# GitHub release.
publish: check-version check-release test build check-dist binary test-binary tag push-tag upload-pypi publish-binary-upload github-release
	@echo "\n\033[92mRelease v$(VERSION) published to PyPI, archive.org, and GitHub!\033[0m"

# Binary-only release (for publishing binary after PyPI release)
publish-binary: binary test-binary publish-binary-upload
	@echo "\n\033[92mBinary v$(VERSION) published to archive.org!\033[0m"
