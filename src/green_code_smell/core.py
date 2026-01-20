import ast
from pathlib import Path

def analyze_file(file_path, rules, project_root=None):
    """Analyze a single file with given rules"""
    code = Path(file_path).read_text()
    tree = ast.parse(code)
    issues = []

    for rule in rules:
        # Special handling for DeadCodeRule
        if rule.__class__.__name__ == 'DeadCodeRule':
            # For single file analysis, use the file's directory as project root
            rule.project_root = str(Path(file_path).parent)
            rule.single_file_mode = True  # ✅ Enable single-file mode
            rule.target_file = str(Path(file_path).resolve())  # ✅ Set target file
            rule_issues = rule.check(tree)
            # Add file path to each issue
            for issue in rule_issues:
                issue['file'] = file_path
            issues.extend(rule_issues)
        else:
            issues.extend(rule.check(tree))

    return issues

def analyze_project(project_path, rules):
    """Analyze entire project - used for project-wide rules like DeadCodeRule"""
    issues = []
    
    for rule in rules:
        # DeadCodeRule needs project-wide context
        if rule.__class__.__name__ == 'DeadCodeRule':
            rule.project_root = str(project_path)
            rule_issues = rule.check_project()
            # Issues from DeadCodeRule already have 'file' field, keep them
            issues.extend(rule_issues)
        else:
            # Other rules analyze each file
            py_files = list(Path(project_path).rglob("*.py"))
            exclude_dirs = {'venv', '.venv', 'env', '__pycache__', '.git', 'node_modules', '.pytest_cache', '.tox'}
            
            for py_file in py_files:
                if not any(parent.name in exclude_dirs for parent in py_file.parents):
                    try:
                        code = py_file.read_text()
                        tree = ast.parse(code)
                        rule_issues = rule.check(tree)
                        # Add file path to each issue
                        for issue in rule_issues:
                            issue['file'] = str(py_file)
                        issues.extend(rule_issues)
                    except Exception:
                        pass
    
    return issues

def code_info(file_path):
    code = Path(file_path).read_text()
    tree = ast.parse(code)
    return {
        "lines": len(code.splitlines()),
        "functions": sum(isinstance(node, ast.FunctionDef) for node in ast.walk(tree)),
        "classes": sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree)),
    }