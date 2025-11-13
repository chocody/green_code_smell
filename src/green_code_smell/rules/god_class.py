import ast

class GodClassRule:
    id = "GCS002"
    name = "GodClass"
    description = "Detects classes that have too many responsibilities (God Class anti-pattern)."
    severity = "High"
    
    def __init__(self, max_methods=10, max_attributes=10, max_lines=200):
        self.max_methods = max_methods
        self.max_attributes = max_attributes
        self.max_lines = max_lines

    def check(self, tree):
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Count methods (functions defined in class)
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                method_count = len(methods)
                
                # Count attributes (assignments in __init__ or class level)
                attributes = set()
                for item in node.body:
                    # Class-level attributes
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        attributes.add(item.target.id)
                    elif isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                attributes.add(target.id)
                    
                    # Instance attributes in __init__
                    if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                        for n in ast.walk(item):
                            if isinstance(n, ast.Assign):
                                for target in n.targets:
                                    if isinstance(target, ast.Attribute) and \
                                       isinstance(target.value, ast.Name) and \
                                       target.value.id == 'self':
                                        attributes.add(target.attr)
                
                attribute_count = len(attributes)
                
                # Count lines in class
                if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                    line_count = node.end_lineno - node.lineno + 1
                else:
                    line_count = 0
                
                # Check thresholds
                problems = []
                if method_count > self.max_methods:
                    problems.append(f"{method_count} methods (max: {self.max_methods})")
                if attribute_count > self.max_attributes:
                    problems.append(f"{attribute_count} attributes (max: {self.max_attributes})")
                if line_count > self.max_lines:
                    problems.append(f"{line_count} lines (max: {self.max_lines})")
                
                if problems:
                    issues.append({
                        "rule": self.name,
                        "lineno": node.lineno,
                        "message": f"Class '{node.name}' is a God Class: {', '.join(problems)}"
                    })
        
        return issues