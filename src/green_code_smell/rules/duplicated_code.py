import ast
from collections import defaultdict
from difflib import SequenceMatcher

class DuplicatedCodeRule:
    id = "GCS003"
    name = "DuplicatedCode"
    description = "Detects duplicated code blocks based on similarity."
    severity = "Medium"
    
    def __init__(self, similarity_threshold=0.85):
        """
        Args:
            similarity_threshold: Minimum similarity ratio (0.0 to 1.0) to consider as duplicate
        """
        self.similarity_threshold = similarity_threshold
    
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
        # Convert tuples to strings for comparison
        str1 = str(code1)
        str2 = str(code2)
        return SequenceMatcher(None, str1, str2).ratio()
    
    def _extract_all_functions(self, tree):
        """Extract all functions with their normalized bodies."""
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                normalized = tuple(self._normalize_code(stmt) for stmt in node.body)
                functions.append({
                    'name': node.name,
                    'lineno': node.lineno,
                    'statements': len(node.body),
                    'normalized': normalized
                })
        return functions
    
    def check(self, tree):
        issues = []
        
        # Extract all functions
        functions = self._extract_all_functions(tree)
        
        # Compare all pairs of functions for similarity
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
                    # Find or create a group for these similar functions
                    group_found = False
                    for group_key in list(similar_groups.keys()):
                        if func1['name'] in [f['name'] for f in similar_groups[group_key]]:
                            similar_groups[group_key].append(func2)
                            group_found = True
                            break
                        elif func2['name'] in [f['name'] for f in similar_groups[group_key]]:
                            similar_groups[group_key].append(func1)
                            group_found = True
                            break
                    
                    if not group_found:
                        group_id = f"{func1['name']}_{func2['name']}"
                        similar_groups[group_id] = [func1, func2]
        
        # Report similar function groups
        reported_functions = set()
        for group_id, group in similar_groups.items():
            # Remove duplicates in group
            unique_funcs = {}
            for func in group:
                if func['name'] not in unique_funcs:
                    unique_funcs[func['name']] = func
            
            group = list(unique_funcs.values())
            
            if len(group) >= 2:
                # Check if any function in this group was already reported
                group_names = set(f['name'] for f in group)
                if group_names.isdisjoint(reported_functions):
                    func_names = [f"{f['name']}() (line {f['lineno']}, {f['statements']} statements)" for f in group]
                    
                    # Calculate average similarity
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
                        "message": f"Similar function implementations (similarity: {avg_similarity:.1%}): {', '.join(func_names)}. Consider refactoring into a single function."
                    })
                    
                    reported_functions.update(group_names)
        
        return issues