.PHONY: docs

VERSION=$(shell grep -m1 __version__ internetarchive/__init__.py | cut -d\' -f2)

init:
	pip install responses==0.5.0 pytest-cov pytest-pep8
	pip install -e .

clean:
	find . -type f -name '*\.pyc' -delete
	find . -type d -name '__pycache__' -delete

pep8-test:
	py.test --pep8 -m pep8 --cov-report term-missing --cov internetarchive

test:
	py.test --pep8 --cov-report term-missing --cov internetarchive

publish: binary
	git tag -a v$(VERSION) -m 'version $(VERSION)'
	git push --tags
	python setup.py register
	python setup.py sdist upload
	python setup.py bdist_wheel upload
	./ia-$(VERSION)-py2.py3-none-any.pex upload ia-pex ia-$(VERSION)-py2.py3-none-any.pex --no-derive
	./ia-$(VERSION)-py2.py3-none-any.pex upload ia-pex ia-$(VERSION)-py2.py3-none-any.pex --remote-name=ia --no-derive

docs-init:
	pip install -r docs/requirements.txt

docs:
	cd docs && make html
	@echo "\033[95m\n\nBuild successful! View the docs homepage at docs/build/html/index.html.\n\033[0m"

binary:
	# This requires using https://github.com/jjjake/pex which has been hacked for multi-platform support.
	pex . --python python3 --python python2 --python-shebang='/usr/bin/env python' -e internetarchive.cli.ia:main -o ia-$(VERSION)-py2.py3-none-any.pex

publish-binary: binary
	./ia-$(VERSION)-py2.pex upload ia-pex ia-$(VERSION)-py2.pex --no-derive
	./ia-$(VERSION)-py2.pex upload ia-pex ia-$(VERSION)-py2.pex --remote-name=ia --no-derive
