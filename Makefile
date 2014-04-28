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
