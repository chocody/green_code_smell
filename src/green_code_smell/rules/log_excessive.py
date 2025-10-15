import ast

class LogExcessiveRule:
    id = "GCS001"
    name = "LogExcessive"
    description = "Detects functions with excessive logging statements."
    severity = "Medium"

    def check(self, tree):
        issues = []
        for node in ast.walk(tree):
            # Check for excessive logging in functions
            if isinstance(node, ast.FunctionDef):
                log_count = sum(
                    isinstance(n, ast.Call) and
                    isinstance(n.func, ast.Attribute) and
                    n.func.attr in {"debug", "info", "warning", "error", "critical"}
                    for n in ast.walk(node)
                )
                if log_count > 3:
                    issues.append({
                        "rule": self.name,
                        "lineno": node.lineno,
                        "message": f"Function '{node.name}' has {log_count} logging statements."
                    })
            # Check for logging inside loops
            if isinstance(node, (ast.For, ast.While)):
                for child in ast.walk(node):
                    if (isinstance(child, ast.Call) and
                        isinstance(child.func, ast.Attribute) and
                        getattr(child.func.value, 'id', None) == 'logging' and
                        child.func.attr in {"debug", "info", "warning", "error", "critical"}):
                        issues.append({
                            "rule": self.name,
                            "lineno": child.lineno,
                            "message": "Logging statement inside loop may lead to excessive logging."
                        })
        return issues