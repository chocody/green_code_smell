import typer
from rich.console import Console
from .core import analyze_file
from .rules.log_excessive import LogExcessiveRule

app = typer.Typer()
console = Console()

@app.command()
def check(path: str):
    rules = [LogExcessiveRule()]
    issues = analyze_file(path, rules)

    if not issues:
        console.print("[green]✅ No issues found![/green]")
    else:
        for issue in issues:
            console.print(f"[red]{issue['rule']}[/red] line {issue['lineno']}: {issue['message']}")

if __name__ == "__main__":
    app()
