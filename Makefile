.PHONY: docs

VERSION=$(shell grep version internetarchive/__init__.py | cut -d"'" -f2)

init:
	pip install -e .

init-speedups:
	pip install -e '.[speedups]'

test:
	py.test --verbose

coverage:
	py.test --verbose --cov-report html --cov=internetarchive

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

pyyaml-egg:
	pip install --no-use-wheel -d . pyyaml==3.11
	tar -zxf PyYAML-3.11.tar.gz
	cd PyYAML-3.11; \
	gsed -i '1i import setuptools' setup.py; \
	python2.7 setup.py --without-libyaml bdist_egg
	mkdir -p wheelhouse
	mv PyYAML-3.11/dist/*egg wheelhouse/

clean-pex:
	rm -fr ia-pex "$$HOME/.pex/install/*" "$$HOME/.pex/build/*"

pex-binary: clean-pex pyyaml-egg
	pip wheel .
	find wheelhouse -name 'PyYAML-3.11*whl' -delete
	pex -v --repo wheelhouse/ -r pex-requirements.txt  -e internetarchive.iacli.ia:main -o ia-$(VERSION)-py2.pex --no-pypi

publish-binary: pex-binary
	./ia-$(VERSION)-py2.pex upload ia-pex ia-$(VERSION)-py2.pex
	./ia-$(VERSION)-py2.pex upload ia-pex ia-$(VERSION)-py2.pex --remote-name=ia
