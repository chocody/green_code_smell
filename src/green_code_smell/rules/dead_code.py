import ast

class DeadCodeRule:
    id = "GCS005"
    name = "DeadCode"
    description = "Detects unreachable code and unused definitions."
    severity = "Medium"
    
    def __init__(self):
        pass

    def check(self, tree):
        issues = []
        
        # Check for unused definitions
        defined = self._collect_definitions(tree)
        used = self._collect_usage(tree)
        self._check_unused(defined, used, issues)
        
        # Check for unreachable code
        self._check_unreachable(tree, issues)
        
        return issues
    
    def _collect_definitions(self, tree):
        """Collect all function, class, and variable definitions."""
        definitions = {}  # {name: (type, lineno)}
        
        for node in ast.walk(tree):
            # Function definitions
            if isinstance(node, ast.FunctionDef):
                definitions[node.name] = ('function', node.lineno)
            
            # Class definitions
            elif isinstance(node, ast.ClassDef):
                definitions[node.name] = ('class', node.lineno)
            
            # Variable assignments at module/class level
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        definitions[target.id] = ('variable', target.lineno)
        
        return definitions
    
    def _collect_usage(self, tree):
        """Collect all name usages."""
        used = set()
        
        for node in ast.walk(tree):
            # Name references (loading a variable)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used.add(node.id)
            
            # Attribute access (obj.method)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)

            # Function calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    used.add(node.func.id)
        
        return used
    
    def _check_unused(self, defined, used, issues):
        print("defined", defined)
        print("used", used)
        """Check for unused variables, functions, and classes."""
        for name, (def_type, lineno) in defined.items():
            # Skip special names (like __init__, __main__)
            if name.startswith('_'):
                continue
            
            # Check if used
            if name not in used:
                issues.append({
                    "rule": self.name,
                    "lineno": lineno,
                    "message": f"Unused {def_type} '{name}' is never referenced"
                })
    
    def _check_unreachable(self, tree, issues):
        """Check for unreachable code after return, break, continue, raise."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.For, ast.While, ast.If, ast.With, ast.Try)):
                # Check main body
                if hasattr(node, 'body'):
                    self._check_body_reachability(node.body, issues)
                
                # Check else blocks
                if hasattr(node, 'orelse') and node.orelse:
                    self._check_body_reachability(node.orelse, issues)
                
                # Check except handlers
                if hasattr(node, 'handlers'):
                    for handler in node.handlers:
                        self._check_body_reachability(handler.body, issues)
                
                # Check finally blocks
                if hasattr(node, 'finalbody') and node.finalbody:
                    self._check_body_reachability(node.finalbody, issues)
    
    def _check_body_reachability(self, body, issues):
        """Check if statements after control flow terminators are unreachable."""
        terminator_found = False
        terminator_line = None
        
        for i, stmt in enumerate(body):
            # Check if current statement is a terminator
            if self._is_terminator(stmt):
                terminator_found = True
                terminator_line = stmt.lineno
            
            # Report unreachable code after terminator
            elif terminator_found and not self._is_docstring(stmt, i):
                issues.append({
                    "rule": self.name,
                    "lineno": stmt.lineno,
                    "message": f"Unreachable code after statement at line {terminator_line}"
                })
                # Only report first unreachable statement in sequence
                break
    
    def _is_terminator(self, stmt):
        """Check if statement terminates control flow."""
        # Return statement
        if isinstance(stmt, ast.Return):
            return True
        
        # Raise statement
        if isinstance(stmt, ast.Raise):
            return True
        
        # Break/Continue
        if isinstance(stmt, (ast.Break, ast.Continue)):
            return True
        
        # exit() or sys.exit() calls
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            if isinstance(stmt.value.func, ast.Name):
                if stmt.value.func.id in ['exit', 'quit']:
                    return True
            elif isinstance(stmt.value.func, ast.Attribute):
                if stmt.value.func.attr == 'exit':
                    return True
        
        return False
    
    def _is_docstring(self, stmt, index):
        """Check if statement is a docstring."""
        return (index == 0 and 
                isinstance(stmt, ast.Expr) and 
                isinstance(stmt.value, ast.Constant) and 
                isinstance(stmt.value.value, str))