import ast

class MutableDefaultArgumentsRule:
    id = "GCS006"
    name = "MutableDefaultArguments"
    description = "Detects functions that use mutable default arguments."
    severity = "Medium"

    def check(self, tree):
        issues = []
        mutable_types = (ast.List, ast.Dict, ast.Set)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults:
                        if isinstance(default, mutable_types):
                            issues.append({
                                "rule": self.name,
                                "lineno": node.lineno,
                                "end_lineno": node.end_lineno,
                                "message": f"Function '{node.name}' has a mutable default argument. Consider using None and initializing inside the function.",
                            })
        return issues