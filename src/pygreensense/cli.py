"""Public CLI module for PyGreenSense."""

from green_code_smell import cli as _legacy_cli


def main():
    """Run the PyGreenSense command-line interface."""
    return _legacy_cli.main()


if __name__ == "__main__":
    main()
