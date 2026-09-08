.PHONY: test test-contracts test-python dev

test: test-contracts test-python

test-contracts:
	python3 scripts/validate_contracts.py

test-python:
	python3 -m pytest tests/unit tests/contract -q
	python3 test_party.py

dev:
	@echo "Flask product  : PORT=8090 python3 app.py"
	@echo "FastAPI (later): uvicorn backend.main:app --port 8000"
