.PHONY: install uninstall test

install:
	pip install --no-build-isolation .

uninstall:
	pip uninstall code_chart -y

test:
	python3 -m unittest discover -s tests -v
