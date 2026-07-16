.PHONY: install lint format typecheck test cov build publish clean

install:
	pip install -e ".[dev]"

lint:
	ruff check lexkit/ tests/

format:
	black lexkit/ tests/

typecheck:
	mypy lexkit/

test:
	pytest

cov:
	pytest --cov=lexkit --cov-report=html --cov-report=term-missing

build:
	python -m build

publish: build
	twine check dist/*
	twine upload dist/*

publish-test: build
	twine check dist/*
	twine upload --repository testpypi dist/*

clean:
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage

bump-patch:
	@echo "Edit pyproject.toml version manually, then commit and tag."
