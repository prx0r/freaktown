.PHONY: test test-contracts test-python dev

test: test-contracts test-python

test-contracts:
	python3 scripts/validate_contracts.py

test-python:
	python3 -m pytest tests/contract test_party.py -q

dev:
	@echo "Flask product  : PORT=8090 python3 app.py"
	@echo "FastAPI (later): uvicorn backend.main:app --port 8000"
