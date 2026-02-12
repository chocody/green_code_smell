import ast
from pathlib import Path

class DeadCodeRule:
    id = "GCS005"
    name = "DeadCode"
    description = "Detects unreachable code and unused definitions."
    severity = "Medium"
    
    def __init__(self, project_root=None):
        self.project_root = project_root
        self.all_definitions = {}  # {file_path: {name: (type, lineno)}}
        self.all_usages = {}       # {file_path: set of names}
        self.all_imports = {}      # {file_path: set of imported names}
        self.is_project_mode = False
    
    def check(self, tree, file_path=None):
        """Check single file"""
        issues = []
        
        # Check for unused definitions
        defined = self._collect_definitions(tree)
        used = self._collect_usage(tree)
        imports = self._collect_imports(tree)
        
        # In single-file mode, don't flag imported items as unused
        self._check_unused(defined, used, imports, issues)
        
        # Check for unreachable code
        self._check_unreachable(tree, issues)
        
        return issues
    
    def check_project(self):
        """Analyze entire project for unused definitions across files"""
        self.is_project_mode = True
        all_issues = []
        
        # Step 1: Collect all definitions and usages from all Python files
        py_files = list(Path(self.project_root).rglob("*.py"))
        
        if not py_files:
            return all_issues
        
        for py_file in py_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                    
                file_str = str(py_file)
                self.all_definitions[file_str] = self._collect_definitions(tree)
                self.all_usages[file_str] = self._collect_usage(tree)
                self.all_imports[file_str] = self._collect_imports(tree)
            except Exception:
                # Skip files that can't be parsed
                continue
        
        # Step 2: Check for unused definitions across files
        for file_path, definitions in self.all_definitions.items():
            for name, (def_type, lineno, end_lineno) in definitions.items():
                # Skip special names
                if name.startswith('_'):
                    continue
                
                # Check if used anywhere in the project
                if not self._is_used_anywhere(name, file_path):
                    all_issues.append({
                        "rule": self.name,
                        "lineno": lineno,
                        "end_lineno": end_lineno,
                        "file": file_path,  # ✅ Added file field
                        "message": f"Unused {def_type} '{name}' is never referenced. Suggest removing it."
                    })
        
        # Step 3: Check for unreachable code in all files
        for py_file in py_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                    file_str = str(py_file)
                    self._check_unreachable(tree, all_issues, file_str)  # Pass file_str
            except Exception:
                continue
        
        return all_issues
    
    def _collect_definitions(self, tree):
        """Collect all function, class, and variable definitions."""
        definitions = {}  # {name: (type, lineno, end_lineno)}
        
        for node in ast.walk(tree):
            # Function definitions
            if isinstance(node, ast.FunctionDef):
                definitions[node.name] = ('function', node.lineno, node.end_lineno)
            
            # Class definitions
            elif isinstance(node, ast.ClassDef):
                definitions[node.name] = ('class', node.lineno, node.end_lineno)
            
            # Variable assignments at module/class level
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        definitions[target.id] = ('variable', target.lineno, target.end_lineno)
        
        return definitions
    
    def _collect_usage(self, tree):
        """Collect all name usages."""
        used = set()
        
        for node in ast.walk(tree):
            # Name references (loading a variable)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used.add(node.id)
            
            # Attribute access (obj.method or obj.attr)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)

            # Function/method calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    used.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    # Handle obj.method() calls
                    used.add(node.func.attr)
        
        return used
    
    def _collect_imports(self, tree):
        """Collect all imported names."""
        imports = set()
        
        for node in ast.walk(tree):
            # from X import Y
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    # Use alias name if provided, otherwise use actual name
                    imports.add(alias.asname if alias.asname else alias.name)
            
            # import X
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.asname if alias.asname else alias.name)
        
        return imports
    
    def _is_used_anywhere(self, name, file_path):
        """Check if name is used anywhere in the project"""
        # Check if used in any file's usages
        for file_usages in self.all_usages.values():
            if name in file_usages:
                return True
        
        # Check if imported in any file (exported for use)
        for file_imports in self.all_imports.values():
            if name in file_imports:
                return True
        
        return False
    
    def _check_unused(self, defined, used, imports, issues):
        """Check for unused variables, functions, and classes."""
        for name, (def_type, lineno, end_lineno) in defined.items():
            # Skip special names (like __init__, __main__)
            if name.startswith('_'):
                continue
            
            # Skip if it's imported (might be re-exported)
            if name in imports:
                continue
            
            # Check if used
            if name not in used:
                issues.append({
                    "rule": self.name,
                    "lineno": lineno,
                    "end_lineno": end_lineno,
                    "message": f"Unused {def_type} '{name}' is never referenced. Suggest removing it."
                })
    
    def _check_unreachable(self, tree, issues, file_path=None):
        """Check for unreachable code after return, break, continue, raise."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.For, ast.While, ast.If, ast.With, ast.Try)):
                # Check main body
                if hasattr(node, 'body'):
                    self._check_body_reachability(node.body, issues, file_path)
                
                # Check else blocks
                if hasattr(node, 'orelse') and node.orelse:
                    self._check_body_reachability(node.orelse, issues, file_path)
                
                # Check except handlers
                if hasattr(node, 'handlers'):
                    for handler in node.handlers:
                        self._check_body_reachability(handler.body, issues, file_path)
                
                # Check finally blocks
                if hasattr(node, 'finalbody') and node.finalbody:
                    self._check_body_reachability(node.finalbody, issues, file_path)
    
    def _check_body_reachability(self, body, issues, file_path=None):
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
                issue = {
                    "rule": self.name,
                    "lineno": stmt.lineno,
                    "end_lineno": stmt.end_lineno,
                    "message": f"Unreachable code after statement at line {terminator_line}. Consider removing it."
                }
                # Add file field if in project mode
                if file_path and self.is_project_mode:
                    issue["file"] = file_path
                issues.append(issue)
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