.DEFAULT_GOAL := run

PYTHON ?= $(if $(wildcard venv/bin/python),venv/bin/python,python3)
APP_MODULE ?= app.main:app
HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: run install test compile

run:
	$(PYTHON) -m uvicorn $(APP_MODULE) --reload --host $(HOST) --port $(PORT)

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest

compile:
	$(PYTHON) -m compileall app
