.PHONY: docs

VERSION=$(shell grep -m1 version internetarchive/__init__.py | cut -d\' -f2)

init:
	pip install -e .

test:
	py.test -v --cov-report term-missing --cov internetarchive

publish:
	git tag -a v$(VERSION) -m 'version $(VERSION)'
	git push --tags
	python setup.py register
	python setup.py sdist upload

docs-init:
	pip install -r docs/requirements.txt

docs:
	cd docs && make html
	@echo "\033[95m\n\nBuild successful! View the docs homepage at docs/build/html/index.html.\n\033[0m"

binary:
	pip wheel .
	pex -v .  -e internetarchive.cli.ia:main -o ia-$(VERSION)-py2.pex --no-pypi --repo wheelhouse/

publish-binary: pex-binary
	./ia-$(VERSION)-py2.pex upload ia-pex ia-$(VERSION)-py2.pex
	./ia-$(VERSION)-py2.pex upload ia-pex ia-$(VERSION)-py2.pex --remote-name=ia
