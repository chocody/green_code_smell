# Release Checklist

Use this checklist when preparing a public PyPI release.

1. Update `version` in `pyproject.toml`.
2. Run the unit tests.
3. Build the source distribution and wheel:

   ```bash
   python -m build
   ```

4. Validate the built distributions:

   ```bash
   python -m twine check dist/*
   ```

5. Upload to TestPyPI first:

   ```bash
   python -m twine upload --repository testpypi dist/*
   ```

6. Upload the final release to PyPI:

   ```bash
   python -m twine upload dist/*
   ```
