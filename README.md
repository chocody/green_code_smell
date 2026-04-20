# PyGreenSense

PyGreenSense is a Python code analysis tool that detects code smells and can optionally track carbon/emission metrics during execution.

## Features

- **God Class Detection** - Identifies classes that are too large or complex
- **Duplicated Code Detection** - Finds similar code blocks across your project
- **Long Method Detection** - Detects methods that exceed size/complexity thresholds
- **Dead Code Detection** - Identifies unreachable/unused definitions
- **Mutable Default Arguments** - Warns about mutable default arguments in functions
- **Carbon Emissions Tracking** - Tracks the carbon footprint of execution (optional)

## Setup (venv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

If `codecarbon` is missing, install it:

```bash
pip install codecarbon
```

## Run the Library

### Installed command

```bash
pygreensense .
pygreensense ./src
pygreensense ./some_file.py
```

### Local source command (without install)

```bash
python -m src.green_code_smell.cli .
```

### Common options

```bash
pygreensense . --no-god-class
pygreensense . --no-dup-check
pygreensense . --no-long-method
pygreensense . --no-dead-code
pygreensense . --no-mutable-default
pygreensense . --no-carbon
```

### Rule tuning examples

```bash
pygreensense . --max-methods 8 --max-cc 30 --max-loc 150
pygreensense . --dup-similarity 0.80 --dup-min-statements 5
pygreensense . --method-max-loc 30 --max-cyclomatic 3
```

## Run Unit Tests

```bash
source .venv/bin/activate
pytest tests/unit
```

### Run tests with coverage

```bash
pytest tests/unit --cov=src/green_code_smell --cov-report=term-missing
```

## Carbon Emission Comparison Validation

This repository includes a comparison note in `carbon_emission_validate` to cross-check carbon readings between approaches.

### Snapshot from `carbon_emission_validate`

- **pygreensense**
  - Average carbon emission: `1.7463339e-07 kg CO2`
  - Min carbon emission: `1.516343e-07 kg CO2`
  - Max carbon emission: `2.863806e-07 kg CO2`
  - Average diff between consecutive runs (signed): `-4.5652333e-09 kg CO2`
  - Average absolute diff between consecutive runs: `3.8392633e-08 kg CO2`
- **codeCarbon**
  - Average carbon emission: `2.488713665990e-09 kgCO2eq`
  - Min carbon emission: `1.404247309062e-09 kgCO2eq`
  - Max carbon emission: `4.240361297175e-09 kgCO2eq`
  - Average diff (signed): `-3.151237764570e-10 kgCO2eq`
  - Average absolute diff: `5.768756903969e-10 kgCO2eq`

Using `tests/validate_parity.py` to validate parity between both methods:

- Direct avg: `9.085950555049e-06 kgCO2eq`
- Lib avg: `9.032015317825e-06 kgCO2eq`
- Mean absolute percentage difference: `0.59%`
- Ratio (`lib/direct`): `0.9941x`

This parity check isolates carbon-emission workflows and helps verify that library-level metrics are close to direct measurements.

## Output

The tool provides:

- Issue location (file and line number)
- Rule/category
- Human-readable issue description
- Summary statistics grouped by rule

## License

MIT License - see `LICENSE`.

## Support

For bugs, feature requests, or questions:
[https://github.com/chocody/green_code_smell/issues](https://github.com/chocody/green_code_smell/issues)