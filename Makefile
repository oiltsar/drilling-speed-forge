.PHONY: all
all:
	PYTHONPATH=src uv run python -m forge.reports
	PYTHONPATH=src uv run python -m forge.balance
	PYTHONPATH=src uv run python -m forge.drilling
	PYTHONPATH=src uv run python -m forge.geomech
	PYTHONPATH=src uv run python -m forge.runs
	PYTHONPATH=src uv run python -m forge.connections
	PYTHONPATH=src uv run python -m forge.analysis
	PYTHONPATH=src uv run python -m forge.figures
