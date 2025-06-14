.PHONY: build up down logs test lint shell-web shell-engine help

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

# Tests

test-web:
	@echo 'Running webapp tests...'
	pytest webapp/tests
	@echo 'Webapp tests complete.'

test-engine:
	@echo 'Running engine tests...'
	PYTHONPATH=$(PWD) pytest tests
	@echo 'Engine tests complete.'

test: test-web test-engine

# Linters

lint-web:
	@echo 'Linting webapp...'
	-node --check webapp/js/*.js
	@echo 'Webapp linting complete.'

lint-engine:
	@echo 'Linting engine...'
	ruff check engine tests webapp/tests || true
	@echo 'Engine linting complete.'

lint: lint-web lint-engine

shell-web:
	docker-compose exec web /bin/sh

shell-engine:
	docker-compose exec engine /bin/sh

help:
	@echo 'Available commands:'
	@echo '  build         Build docker images'
	@echo '  up            Start services in detached mode'
	@echo '  down          Stop services'
	@echo '  logs          Follow service logs'
	@echo '  test          Run all tests'
	@echo '  test-web      Run webapp tests'
	@echo '  test-engine   Run engine tests'
	@echo '  lint          Run all linters'
	@echo '  lint-web      Run webapp linter'
	@echo '  lint-engine   Run engine linter'
	@echo '  shell-web     Access web service shell'
	@echo '  shell-engine  Access engine service shell'
