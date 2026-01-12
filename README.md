# Green Code Smell

A Python code analysis tool that detects various code smells and quality issues in your codebase. It helps you write cleaner, more maintainable code by identifying problematic patterns.

## Features

- **Excessive Logging Detection** - Detects functions with too many logging statements
- **God Class Detection** - Identifies classes that are too large or complex
- **Duplicated Code Detection** - Finds similar code blocks across your project
- **Long Method Detection** - Detects methods that exceed size/complexity thresholds
- **Dead Code Detection** - Identifies unused variables and functions
- **Mutable Default Arguments** - Warns about mutable default arguments in functions

## Installation

```bash
pip install green-code-smell
```

## Quick Start

### Run analysis on current project (from root directory)

```bash
green-code-smell run
```

### Run analysis on specific directory

```bash
green-code-smell ./src
green-code-smell ./my_project
```

### Run analysis on single file

```bash
green-code-smell myfile.py
green-code-smell ./src/utils.py
```

## Usage with Rule Parameters

### Disable specific checks

Disable excessive logging detection:
```bash
green-code-smell run --no-log-check
```

Disable God Class detection:
```bash
green-code-smell . --no-god-class
```

Disable duplicated code detection:
```bash
green-code-smell . --no-dup-check
```

### God Class Parameters

Customize God Class thresholds:
```bash
green-code-smell run --max-methods 8 --max-cc 30 --max-loc 150
```

- `--max-methods` - Maximum allowed methods in a class (default: 10)
- `--max-cc` - Maximum cyclomatic complexity (default: 35)
- `--max-loc` - Maximum lines of code (default: 100)

### Duplicated Code Parameters

Fine-tune duplicate detection:
```bash
green-code-smell . --dup-similarity 0.80 --dup-min-statements 5
```

- `--dup-similarity` - Similarity threshold 0.0-1.0 (default: 0.85)
- `--dup-min-statements` - Minimum statements to check (default: 3)

### Long Method Parameters

Control method length detection:
```bash
green-code-smell run --method-max-loc 30 --max-cyclomatic 3
```

- `--method-max-loc` - Maximum lines of code for method (default: 25)
- `--max-cyclomatic` - Maximum cyclomatic complexity (default: 10)

## Advanced Options

### Disable carbon tracking

```bash
green-code-smell run --no-carbon
```

### Combine multiple options

```bash
green-code-smell ./src --no-log-check --max-methods 8 --dup-similarity 0.80
```

## Examples

Analyze entire project with strict rules:
```bash
green-code-smell run --max-methods 5 --method-max-loc 20
```

Analyze specific directory, skip logging checks:
```bash
green-code-smell ./app --no-log-check
```

Analyze with custom duplicated code detection:
```bash
green-code-smell . --dup-similarity 0.90 --dup-min-statements 10
```

## Output

The tool provides detailed analysis with:
- Issue location (file and line number)
- Issue type/rule
- Issue description
- Summary statistics grouped by rule type

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please check our GitHub repository for issues and pull requests.

## Support

For bugs, feature requests, or questions, please visit:
https://github.com/chocody/green_code_smell/issues