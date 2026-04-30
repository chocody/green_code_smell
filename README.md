# PyGreenSense

PyGreenSense is a Python code analysis tool that detects green code smells and
tracks carbon emission metrics during execution.

## Features

- God Class detection
- Duplicated code detection
- Long Method detection
- Dead code detection
- Mutable default argument detection
- Carbon emissions tracking with CodeCarbon

## Installation

Install the static-analysis tool:

```bash
pip install pygreensense
```

CodeCarbon is installed automatically with PyGreenSense.

## CLI Usage

Analyze a project or a single Python file:

```bash
pygreensense .
pygreensense ./src
pygreensense ./some_file.py
```

Run without carbon tracking:

```bash
pygreensense . --no-carbon
```

Specify the file to execute for carbon tracking:

```bash
pygreensense . --carbon-run main.py
```

Tune individual rules:

```bash
pygreensense . --max-methods 8 --max-cc 30 --max-loc 150
pygreensense . --dup-similarity 0.80 --dup-min-statements 5
pygreensense . --method-max-loc 30 --max-cyclomatic 3
```

Disable individual rules:

```bash
pygreensense . --no-god-class
pygreensense . --no-dup-check
pygreensense . --no-long-method
pygreensense . --no-dead-code
pygreensense . --no-mutable-default
```

You can also run the package module directly:

```bash
python -m pygreensense .
python -m green_code_smell .
```

## Python API

```python
from pygreensense import GodClassRule, analyze_file

issues = analyze_file("example.py", [GodClassRule()])
```

The original import package remains available for compatibility:

```python
from green_code_smell import analyze_project
```

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Build and validate distributions before publishing:

```bash
python -m build
python -m twine check dist/*
```

See [docs/release.md](docs/release.md) for the release checklist.

## Carbon Validation

Carbon emission parity notes live in
[docs/carbon_emission_validation.md](docs/carbon_emission_validation.md).

## License

MIT License. See [LICENSE](LICENSE).

## Support

For bugs, feature requests, or questions, use the
[GitHub issue tracker](https://github.com/u6587051/PyGreenSense-Library/issues).
