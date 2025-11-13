import ast
from collections import defaultdict

class DuplicatedCodeRule:
    id = "GCS003"
    name = "DuplicatedCode"
    description = "Detects duplicated code blocks that should be refactored."
    severity = "Medium"
    
    def __init__(self, min_lines=5, min_occurrences=2):
        """
        Args:
            min_lines: Minimum number of statements to consider as duplicated code
            min_occurrences: Minimum number of times code must appear to be flagged
        """
        self.min_lines = min_lines
        self.min_occurrences = min_occurrences
    
    def _normalize_code(self, node):
        """Normalize AST node to string for comparison, ignoring variable names."""
        if isinstance(node, ast.Name):
            return "VAR"
        elif isinstance(node, ast.Constant):
            return f"CONST_{type(node.value).__name__}"
        elif isinstance(node, list):
            return tuple(self._normalize_code(item) for item in node)
        elif isinstance(node, ast.AST):
            result = [node.__class__.__name__]
            for field, value in ast.iter_fields(node):
                if field in ('lineno', 'col_offset', 'end_lineno', 'end_col_offset', 'ctx'):
                    continue
                result.append((field, self._normalize_code(value)))
            return tuple(result)
        else:
            return node
    
    def _find_similar_functions(self, tree):
        """Find functions with very similar implementations."""
        function_bodies = {}
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip small functions
                if len(node.body) < 5:
                    continue
                    
                # Normalize entire function body
                normalized = tuple(self._normalize_code(stmt) for stmt in node.body)
                
                if normalized not in function_bodies:
                    function_bodies[normalized] = []
                function_bodies[normalized].append({
                    'name': node.name,
                    'lineno': node.lineno,
                    'statements': len(node.body)
                })
        
        return function_bodies
    
    def _extract_all_functions(self, tree):
        """Extract all functions with their statements."""
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if len(node.body) >= self.min_lines:
                    functions.append({
                        'name': node.name,
                        'lineno': node.lineno,
                        'body': node.body
                    })
        return functions
    
    def _find_duplicated_blocks(self, functions):
        """Find the LARGEST duplicated blocks to avoid reporting overlapping duplications."""
        # Map from normalized block to list of (function_name, start_line, end_line, size)
        all_blocks = defaultdict(list)
        
        # Extract all possible blocks from all functions
        for func in functions:
            statements = func['body']
            # Try all possible block sizes from largest to smallest
            for size in range(len(statements), self.min_lines - 1, -1):
                for i in range(len(statements) - size + 1):
                    block = statements[i:i + size]
                    normalized = tuple(self._normalize_code(stmt) for stmt in block)
                    
                    all_blocks[normalized].append({
                        'function': func['name'],
                        'start_line': block[0].lineno,
                        'end_line': block[-1].lineno if hasattr(block[-1], 'lineno') else block[0].lineno,
                        'size': size
                    })
        
        # Filter to keep only blocks that appear multiple times
        duplicated = {k: v for k, v in all_blocks.items() if len(v) >= self.min_occurrences}
        
        # Remove overlapping blocks - keep only the largest ones
        final_duplications = []
        reported_ranges = set()
        
        # Sort by block size (largest first)
        sorted_dups = sorted(duplicated.items(), key=lambda x: x[1][0]['size'], reverse=True)
        
        for normalized, occurrences in sorted_dups:
            # Group by unique function
            unique_funcs = {}
            for occ in occurrences:
                func_name = occ['function']
                if func_name not in unique_funcs:
                    unique_funcs[func_name] = occ
            
            # Check if at least min_occurrences different functions have this block
            if len(unique_funcs) < self.min_occurrences:
                continue
            
            # Check if this duplication overlaps with an already reported one
            current_ranges = set()
            overlaps = False
            
            for occ in unique_funcs.values():
                range_key = (occ['function'], occ['start_line'], occ['end_line'])
                
                # Check if this range overlaps with any reported range
                for reported_func, reported_start, reported_end in reported_ranges:
                    if occ['function'] == reported_func:
                        # Check for overlap
                        if not (occ['end_line'] < reported_start or occ['start_line'] > reported_end):
                            overlaps = True
                            break
                
                if overlaps:
                    break
                    
                current_ranges.add(range_key)
            
            # If no overlap, add this duplication
            if not overlaps:
                final_duplications.append((normalized, list(unique_funcs.values())))
                reported_ranges.update(current_ranges)
        
        return final_duplications
    
    def check(self, tree):
        issues = []
        
        # Extract all functions
        functions = self._extract_all_functions(tree)
        
        # Find duplicated blocks (without overlaps)
        duplicated_blocks = self._find_duplicated_blocks(functions)
        
        # Report duplicated blocks
        for normalized, occurrences in duplicated_blocks:
            occurrences.sort(key=lambda x: x['start_line'])
            
            locations = [f"{o['function']}() (line {o['start_line']}-{o['end_line']})" 
                        for o in occurrences]
            
            issues.append({
                "rule": self.name,
                "lineno": occurrences[0]['start_line'],
                "message": f"Duplicated code block ({occurrences[0]['size']} statements) found in {len(occurrences)} functions: {', '.join(locations)}"
            })
        
        # Check for similar/duplicated functions (entire function bodies)
        function_bodies = self._find_similar_functions(tree)
        
        for normalized_body, functions in function_bodies.items():
            if len(functions) >= 2:
                func_names = [f"{f['name']}()" for f in functions]
                issues.append({
                    "rule": self.name,
                    "lineno": functions[0]['lineno'],
                    "message": f"Identical function implementations ({functions[0]['statements']} statements): {', '.join(func_names)}. Consider refactoring into a single function."
                })
        
        return issues