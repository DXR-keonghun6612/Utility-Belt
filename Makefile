.PHONY: install uninstall

install:
	pip install --no-build-isolation .

uninstall:
	pip uninstall code_chart -y
