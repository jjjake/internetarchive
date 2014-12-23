.PHONY: docs

init:
	pip install -e .

init-speedups:
	pip install -e '.[speedups]'

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
	pip install -d . pyyaml==3.11
	tar -zxf PyYAML-3.11.tar.gz
	cd PyYAML-3.11; \
	sed -i '1i import setuptools' setup.py; \
	python2.7 setup.py --without-libyaml bdist_egg
	mkdir -p pex-dist
	mv PyYAML-3.11/dist/*egg pex-dist/

ia-egg:
	rm -rf build
	git checkout pex; \
	python2.7 setup.py bdist_egg
	mv dist/internetarchive-*.egg pex-dist/

pex-binary: pyyaml-egg ia-egg
	rm ia-pex
	pex -v --repo pex-dist/ -r PyYAML -r internetarchive -e internetarchive.iacli.ia:main -p ia-pex
