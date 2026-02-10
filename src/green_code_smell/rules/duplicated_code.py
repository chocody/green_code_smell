import ast
from collections import defaultdict
from difflib import SequenceMatcher

class DuplicatedCodeRule:
    id = "GCS003"
    name = "DuplicatedCode"
    description = "Detects duplicated code blocks based on similarity."
    severity = "Medium"
    
    def __init__(self, similarity_threshold=0.85, min_statements=3, check_within_functions=True, check_between_functions=True):
        """
        Args:
            similarity_threshold: Minimum similarity ratio (0.0 to 1.0) to consider as duplicate
            min_statements: Minimum number of statements in a code block to check for duplication
            check_within_functions: Check for duplicated code within the same function
            check_between_functions: Check for duplicated code between different functions
        """
        self.similarity_threshold = similarity_threshold
        self.min_statements = min_statements
        self.check_within_functions = check_within_functions
        self.check_between_functions = check_between_functions
    
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
    
    def _calculate_similarity(self, code1, code2):
        """Calculate similarity ratio between two normalized code blocks."""
        str1 = str(code1)
        str2 = str(code2)
        return SequenceMatcher(None, str1, str2).ratio()
    
    def _extract_all_functions(self, tree):
        """Extract all functions with their normalized bodies."""
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only check functions with enough statements
                if len(node.body) >= self.min_statements:
                    normalized = tuple(self._normalize_code(stmt) for stmt in node.body)
                    functions.append({
                        'name': node.name,
                        'lineno': node.lineno,
                        'end_lineno': node.end_lineno,
                        'statements': len(node.body),
                        'normalized': normalized,
                        'body': node.body
                    })
        return functions
    
    def _extract_code_blocks(self, statements, min_size, parent_name="module", parent_lineno=0):
        """Extract all code blocks of minimum size from a list of statements."""
        blocks = []
        
        # Only extract blocks if we have enough statements
        if len(statements) < min_size:
            return blocks
        
        # Extract sliding windows of code blocks
        for i in range(len(statements) - min_size + 1):
            for window_size in range(min_size, min(len(statements) - i + 1, min_size + 5)):
                block = statements[i:i + window_size]
                normalized = tuple(self._normalize_code(stmt) for stmt in block)
                
                blocks.append({
                    'parent': parent_name,
                    'parent_lineno': parent_lineno,
                    'start_line': block[0].lineno if hasattr(block[0], 'lineno') else 0,
                    'end_line': block[-1].lineno if hasattr(block[-1], 'lineno') else 0,
                    'statements': len(block),
                    'normalized': normalized
                })
        
        return blocks
    
    def _check_function_to_function(self, functions):
        """Check for duplicated code between different functions."""
        issues = []
        compared = set()
        similar_groups = defaultdict(list)
        
        for i, func1 in enumerate(functions):
            for j, func2 in enumerate(functions):
                if i >= j:
                    continue
                
                pair_key = tuple(sorted([func1['name'], func2['name']]))
                if pair_key in compared:
                    continue
                compared.add(pair_key)
                
                similarity = self._calculate_similarity(func1['normalized'], func2['normalized'])
                
                if similarity >= self.similarity_threshold:
                    group_found = False
                    for group_key in list(similar_groups.keys()):
                        if func1['name'] in [f['name'] for f in similar_groups[group_key]]:
                            if func2 not in similar_groups[group_key]:
                                similar_groups[group_key].append(func2)
                            group_found = True
                            break
                        elif func2['name'] in [f['name'] for f in similar_groups[group_key]]:
                            if func1 not in similar_groups[group_key]:
                                similar_groups[group_key].append(func1)
                            group_found = True
                            break
                    
                    if not group_found:
                        group_id = f"{func1['name']}_{func2['name']}"
                        similar_groups[group_id] = [func1, func2]
        
        reported_functions = set()
        for group_id, group in similar_groups.items():
            unique_funcs = {}
            for func in group:
                if func['name'] not in unique_funcs:
                    unique_funcs[func['name']] = func
            
            group = list(unique_funcs.values())
            
            if len(group) >= 2:
                group_names = set(f['name'] for f in group)
                if group_names.isdisjoint(reported_functions):
                    func_names = [f"{f['name']}() (line {f['lineno']}, {f['statements']} statements)" for f in group]
                    
                    similarities = []
                    for i, func1 in enumerate(group):
                        for j, func2 in enumerate(group):
                            if i < j:
                                sim = self._calculate_similarity(func1['normalized'], func2['normalized'])
                                similarities.append(sim)
                    
                    avg_similarity = sum(similarities) / len(similarities) if similarities else 0
                    
                    issues.append({
                        "rule": self.name,
                        "lineno": group[0]['lineno'],
                        "end_lineno": group[0]['end_lineno'],
                        "message": f"Similar function implementations (similarity: {avg_similarity:.1%}): {', '.join(func_names)}. Consider refactoring into a single function."
                    })
                    
                    reported_functions.update(group_names)
        
        return issues
    
    def _check_within_functions(self, functions):
        """Check for duplicated code blocks within each function."""
        issues = []
        
        for func in functions:
            # Need at least 2x the minimum statements to have duplicates
            if func['statements'] < self.min_statements * 2:
                continue
            
            blocks = self._extract_code_blocks(
                func['body'], 
                self.min_statements, 
                f"function:{func['name']}", 
                func['lineno']
            )
            
            # Track reported pairs to avoid duplicates
            reported_pairs = set()
            
            for i, block1 in enumerate(blocks):
                for j, block2 in enumerate(blocks):
                    if i >= j:
                        continue
                    
                    # Skip overlapping blocks
                    if not (block1['end_line'] < block2['start_line'] or block2['end_line'] < block1['start_line']):
                        continue
                    
                    # Create a unique key for this pair
                    pair_key = (min(block1['start_line'], block2['start_line']), 
                               max(block1['start_line'], block2['start_line']))
                    
                    if pair_key in reported_pairs:
                        continue
                    
                    similarity = self._calculate_similarity(block1['normalized'], block2['normalized'])
                    
                    if similarity >= self.similarity_threshold:
                        issues.append({
                            "rule": self.name,
                            "lineno": block1['start_line'],
                            "end_lineno": block1['end_line'],
                            "message": f"Duplicated code block in function '{func['name']}' (similarity: {similarity:.1%}): lines {block1['start_line']}-{block1['end_line']} and {block2['start_line']}-{block2['end_line']} ({block1['statements']} statements). Consider extracting to a separate function."
                        })
                        reported_pairs.add(pair_key)
                        # Only report the first duplicate found in this function
                        break
                if reported_pairs:
                    break
        
        return issues
    
    def check(self, tree):
        issues = []
        
        functions = self._extract_all_functions(tree)
        
        # Check for similar functions (whole function comparison)
        if self.check_between_functions and len(functions) >= 2:
            issues.extend(self._check_function_to_function(functions))
        
        # Check for duplicated blocks within a function
        if self.check_within_functions:
            issues.extend(self._check_within_functions(functions))
        
        return issues