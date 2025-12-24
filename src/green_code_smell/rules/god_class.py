import ast

class GodClassRule:
    id = "GCS002"
    name = "GodClass"
    description = "Detects classes that have too many responsibilities (God Class anti-pattern)."
    severity = "High"
    
    def __init__(self, max_methods=10, max_complexity=35, max_lines=100):
        self.max_methods = max_methods
        self.max_complexity = max_complexity
        self.max_lines = max_lines

    def calculate_complexity(self, node):
        """Calculate cyclomatic complexity for a node (method or class)."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            # Add 1 for each decision point
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, (ast.With, ast.AsyncWith)):
                complexity += 1
            elif isinstance(child, ast.Assert):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # Add for each additional condition in boolean operations
                complexity += len(child.values) - 1
            elif isinstance(child, ast.comprehension):
                # List/dict/set comprehensions with conditions
                complexity += len(child.ifs)
        
        return complexity

    def check(self, tree):
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Count methods (functions defined in class)
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                method_count = len(methods)
                
                # Calculate total cyclomatic complexity for the class
                total_complexity = 0
                for method in methods:
                    total_complexity += self.calculate_complexity(method)
                
                # Count lines in class
                if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                    line_count = node.end_lineno - node.lineno + 1
                else:
                    line_count = 0
                
                # Check thresholds
                problems = []
                if method_count > self.max_methods:
                    problems.append(f"{method_count} methods (max: {self.max_methods})")
                if total_complexity > self.max_complexity:
                    problems.append(f"complexity {total_complexity} (max: {self.max_complexity})")
                if line_count > self.max_lines:
                    problems.append(f"{line_count} lines (max: {self.max_lines})")
                
                if problems:
                    issues.append({
                        "rule": self.name,
                        "lineno": node.lineno,
                        "message": f"Class '{node.name}' is a God Class: {', '.join(problems)}"
                    })
        
        return issues