.PHONY: install uninstall

install:
	pip install --no-build-isolation -e .

uninstall:
	pip uninstall code-chart -y
