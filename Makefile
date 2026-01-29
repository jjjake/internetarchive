.PHONY: docs clean clean-dist test binary test-binary check-release check-version \
        build tag push-tag upload-pypi publish-binary-upload github-release \
        publish publish-all publish-binary docs-init init pep8-test

VERSION=$(shell grep -m1 __version__ internetarchive/__version__.py | cut -d\' -f2)

# ============ Development ============
init:
	pip install responses==0.5.0 pytest-cov pytest-pep8
	pip install -e .

clean:
	find . -type f -name '*\.pyc' -delete
	find . -type d -name '__pycache__' -delete

clean-dist:
	rm -rf dist/ build/ *.egg-info

pep8-test:
	py.test --pep8 -m pep8 --cov-report term-missing --cov internetarchive

test:
	ruff check
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

# ============ Release Publishing ============
tag:
	git tag -a v$(VERSION) -m 'version $(VERSION)'

push-tag:
	git push --tags origin master

upload-pypi:
	twine upload --repository pypi ./dist/*

publish-binary-upload:
	./ia-$(VERSION)-py3-none-any.pex upload ia-pex ia-$(VERSION)-py3-none-any.pex --no-derive
	./ia-$(VERSION)-py3-none-any.pex upload ia-pex ia-$(VERSION)-py3-none-any.pex --remote-name=ia --no-derive

# Extract changelog and create GitHub release
github-release:
	@echo "Extracting changelog for v$(VERSION)..."
	@awk '/^$(VERSION) /{found=1; next} found && /^[0-9]+\.[0-9]+\.[0-9]+ /{exit} found' HISTORY.rst > /tmp/ia-release-notes-$(VERSION).md
	gh release create v$(VERSION) \
		--title "v$(VERSION)" \
		--notes-file /tmp/ia-release-notes-$(VERSION).md
	@rm -f /tmp/ia-release-notes-$(VERSION).md
	@echo "GitHub release created!"

# ============ Main Release Targets ============

# PyPI-only release (no binary)
publish: check-version check-release test build tag push-tag upload-pypi github-release
	@echo "\n\033[92mRelease v$(VERSION) published to PyPI and GitHub!\033[0m"

# Full release including pex binary
publish-all: check-version check-release test build binary test-binary tag push-tag upload-pypi publish-binary-upload github-release
	@echo "\n\033[92mRelease v$(VERSION) published everywhere!\033[0m"

# Binary-only release (for publishing binary after PyPI release)
publish-binary: binary test-binary publish-binary-upload
	@echo "\n\033[92mBinary v$(VERSION) published to archive.org!\033[0m"
