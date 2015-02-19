.PHONY: docs

VERSION=$(shell grep -m1 version internetarchive/__init__.py | cut -d\' -f2)

init:
	pip install -e .

test:
	py.test --verbose

coverage:
	py.test --verbose --cov-report html --cov=internetarchive

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
	python2.7 setup.py --without-libyaml bdist_egg
	mkdir -p pex-dist
	mv PyYAML-3.10/dist/*egg pex-dist/
	rm -rf PyYAML-3.10*

pex-binary: pyyaml-egg
	rm -fr ia-pex "$$HOME/.pex/install/*" "$$HOME/.pex/build/*"
	rm -rf wheelhouse
	pip wheel .
	rm -f wheelhouse/PyYAML-3.1*macosx*
	mv wheelhouse/* pex-dist/
	pex -vvv --python=python2.7 --repo=pex-dist --no-pypi -r internetarchive -r PyYAML -e internetarchive.iacli.ia:main -p ia-$(VERSION).pex
