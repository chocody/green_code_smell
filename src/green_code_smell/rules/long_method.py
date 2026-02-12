import ast

class LongMethodRule:
    id = "GCS004"
    name = "LongMethod"
    description = "Detects methods that are too long based on LOC and cyclomatic complexity."
    severity = "Medium"
    
    def __init__(self, max_loc=30, max_cc=10):
        self.max_loc = max_loc
        self.max_cc = max_cc

    def calculate_cyclomatic_complexity(self, node):
        """
        Calculate cyclomatic complexity of a function.
        CC = number of decision points + 1
        Decision points include: if, for, while, and, or, except, with
        """
        complexity = 1  # Start with 1
        
        for child in ast.walk(node):
            # Conditional statements
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            # Exception handlers
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            # Boolean operators (and, or)
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            # List/Dict/Set comprehensions with if clauses
            elif isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                for generator in child.generators:
                    complexity += len(generator.ifs)
            # With statements
            elif isinstance(child, (ast.With, ast.AsyncWith)):
                complexity += 1
        
        return complexity

    def count_loops(self, node):
        """Count the number of loops in a function."""
        loop_count = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.While, ast.AsyncFor)):
                loop_count += 1
        return loop_count

    def check(self, tree):
        issues = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Calculate LOC (Lines of Code)
                if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                    loc = node.end_lineno - node.lineno + 1
                else:
                    loc = 0
                
                # Calculate Cyclomatic Complexity
                cyclomatic = self.calculate_cyclomatic_complexity(node)
                
                # Count loops
                loop_count = self.count_loops(node)
                
                # Check thresholds
                problems = []
                if loc > self.max_loc:
                    problems.append(f"LOC: {loc} (max: {self.max_loc})")
                if cyclomatic > self.max_cc:
                    problems.append(f"Cyclomatic Complexity: {cyclomatic} (max: {self.max_cc})")
                
                if problems:
                    issues.append({
                        "rule": self.name,
                        "lineno": node.lineno,
                        "end_lineno": node.end_lineno,
                        "message": f"Method '{node.name}' is too long: {', '.join(problems)}. Consider refactoring by extracting smaller methods.",
                    })
        
        return issues