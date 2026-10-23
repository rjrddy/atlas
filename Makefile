SHELL := /bin/sh
PY := .venv/bin/python
BUILD ?= build
.PHONY: setup build lint test bench data demo asan tsan scan proto web
setup:
	python3 -m venv .venv
	$(PY) -m pip install -r requirements-dev.txt
	cd apps/web && npm ci
proto:
	$(PY) -m grpc_tools.protoc -I proto --python_out=sdk --grpc_python_out=sdk proto/atlas.proto
build:
	cmake -S . -B $(BUILD) -DCMAKE_BUILD_TYPE=Release -DPython_EXECUTABLE=$(CURDIR)/$(PY)
	cmake --build $(BUILD) -j 4
web:
	cd apps/web && npm run build
lint:
	.venv/bin/clang-format --dry-run --Werror src/*.cpp src/*.hpp tests/*.cpp
	.venv/bin/ruff check scripts sdk/client.py tests
	.venv/bin/ruff format --check scripts sdk/client.py tests
	cd apps/web && npm run lint
test: build proto
	./$(BUILD)/core_tests
	PYTHONPATH=$(BUILD):sdk $(PY) -m pytest -q
data:
	$(PY) scripts/data.py
bench: build data
	PYTHONPATH=$(BUILD) $(PY) scripts/bench.py
demo: setup build proto web
	PYTHONPATH=$(BUILD):sdk $(PY) scripts/server.py
asan:
	cmake -S . -B build-asan -DCMAKE_BUILD_TYPE=RelWithDebInfo -DPYTHON_BINDINGS=OFF -DSANITIZER=address
	cmake --build build-asan -j 4
	ASAN_OPTIONS=halt_on_error=1 ./build-asan/core_tests
tsan:
	cmake -S . -B build-tsan -DCMAKE_BUILD_TYPE=RelWithDebInfo -DPYTHON_BINDINGS=OFF -DSANITIZER=thread
	cmake --build build-tsan -j 4
	TSAN_OPTIONS=halt_on_error=1 ./build-tsan/core_tests
scan:
	$(PY) -m pip_audit -r requirements-dev.txt -r requirements-browser.txt -r requirements-plot.txt --progress-spinner off
	cd apps/web && npm audit --audit-level=low
