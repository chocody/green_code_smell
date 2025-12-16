import ast
from pathlib import Path

def analyze_file(file_path, rules):
    avg = 0
    for n in range(31): # Rules of 30
        code = Path(file_path).read_text()
        tree = ast.parse(code)
        issues = []

        for rule in rules:
            issues.extend(rule.check(tree))
        avg += n
    avg /= 30

    return issues, avg

def warm_up(file_path, rules): # Warm up before actual analysis
    code = Path(file_path).read_text()
    tree = ast.parse(code)
    issues = []

    for rule in rules:
        issues.extend(rule.check(tree))

    return issues

def code_info(file_path):
    code = Path(file_path).read_text()
    tree = ast.parse(code)
    return {
        "lines": len(code.splitlines()),
        "functions": sum(isinstance(node, ast.FunctionDef) for node in ast.walk(tree)),
        "classes": sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree)),
    }   