.PHONY: docs

VERSION=$(shell grep -m1 version internetarchive/__init__.py | cut -d\' -f2)

init:
	pip install -e .

test:
	py.test --cov-report term-missing --cov internetarchive

publish:
	python setup.py register
	python setup.py sdist upload

docs-init:
	pip install -r docs/requirements.txt

docs:
	cd docs && make html
	@echo "\033[95m\n\nBuild successful! View the docs homepage at docs/build/html/index.html.\n\033[0m"

pyyaml-egg:
	pip install -d . pyyaml==3.10
	tar -zxf PyYAML-3.10.tar.gz
	cd PyYAML-3.10; \
	sed -i '1i import setuptools' setup.py; \
	python2.7 setup.py --without-libyaml bdist_egg; \
	python3.4 setup.py --without-libyaml bdist_egg
	mkdir -p pex-dist
	mv PyYAML-3.10/dist/*egg pex-dist/

pex-binary:
	rm -fr ia-pex "$$HOME/.pex/install/*" "$$HOME/.pex/build/*"
	rm -rf wheelhouse
	pip2.7 wheel .
	pip3.4 wheel .
	mv wheelhouse/* pex-dist/
	rmdir wheelhouse
	pex --python-shebang='/usr/bin/env python2.7' --python=python2.7 --no-pypi --repo=pex-dist -r pex-requirements.txt --entry-point=internetarchive.cli.ia:main --output-file=ia-$(VERSION)-py2.pex
	pex --python-shebang='/usr/bin/env python3.4' --python=python3.4 --no-pypi --repo=pex-dist -r pex-requirements.txt --entry-point=internetarchive.cli.ia:main --output-file=ia-$(VERSION)-py3.pex
	#pex -vvv --python=python2.7 --repo=pex-dist --no-pypi -r internetarchive -r PyYAML -e internetarchive.cli.ia:main -p ia-$(VERSION).pex
	#/Users/jake/github/jjjake/iamine/.venv/bin/pex -vvv --hashbang='#!/usr/bin/env python' --python=python2.7 --repo=pex-dist --no-pypi -r schema==0.3.1 -r internetarchive==1.0.0 -e internetarchive.cli.ia:main -p ia-$(VERSION).pex

clean-pyc:
	find . -name "*.pyc" -exec rm -f {} \;
