setup:
	rm dist -R
	cp setup37.py setup.py
	python setup.py sdist
	cp setup38.py setup.py
	python setup.py sdist
	rm setup.py

testpypi:
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*

pypi:
	twine upload dist/*

.PHONY: docs
docs:
	cd docs_source && make html