.PHONY: build up down logs test lint shell-web shell-engine

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

# Placeholder for tests - assuming webapp and engine have their own test runners
test-web:
	@echo "Running webapp tests..."
	# docker-compose exec web <test_command>
	@echo "Webapp tests placeholder complete."

test-engine:
	@echo "Running engine tests..."
	# docker-compose exec engine <test_command>
	@echo "Engine tests placeholder complete."

test: test-web test-engine

# Placeholder for linters
lint-web:
	@echo "Linting webapp..."
	# docker-compose exec web <lint_command>
	@echo "Webapp linting placeholder complete."

lint-engine:
	@echo "Linting engine..."
	# docker-compose exec engine <lint_command>
	@echo "Engine linting placeholder complete."

lint: lint-web lint-engine

shell-web:
	docker-compose exec web /bin/sh

shell-engine:
	docker-compose exec engine /bin/sh

help:
	@echo "Available commands:"
	@echo "  build         Build docker images"
	@echo "  up            Start services in detached mode"
	@echo "  down          Stop services"
	@echo "  logs          Follow service logs"
	@echo "  test          Run all tests (placeholders)"
	@echo "  test-web      Run webapp tests (placeholder)"
	@echo "  test-engine   Run engine tests (placeholder)"
	@echo "  lint          Run all linters (placeholders)"
	@echo "  lint-web      Run webapp linter (placeholder)"
	@echo "  lint-engine   Run engine linter (placeholder)"
	@echo "  shell-web     Access web service shell"
	@echo "  shell-engine  Access engine service shell"
