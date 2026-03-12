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
            check_between_functions: Check for duplicated code between different functions/methods
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
        """
        Extract all functions/methods with their normalized bodies.
        Each entry includes a 'qualified_name' (ClassName.method or just func_name)
        so that same-named methods in different classes are never conflated.
        """
        functions = []

        # Walk top-level and collect class contexts so we can tag each method.
        def _walk_with_class(node, class_name=None):
            if isinstance(node, ast.ClassDef):
                for child in ast.iter_child_nodes(node):
                    _walk_with_class(child, class_name=node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if len(node.body) >= self.min_statements:
                    qualified = f"{class_name}.{node.name}" if class_name else node.name
                    normalized = tuple(self._normalize_code(stmt) for stmt in node.body)
                    functions.append({
                        'name': node.name,
                        'qualified_name': qualified,
                        'class_name': class_name,
                        'lineno': node.lineno,
                        'end_lineno': node.end_lineno,
                        'statements': len(node.body),
                        'normalized': normalized,
                        'body': node.body
                    })
                # Also recurse into nested functions (no class context change)
                for child in ast.iter_child_nodes(node):
                    _walk_with_class(child, class_name=class_name)
            else:
                for child in ast.iter_child_nodes(node):
                    _walk_with_class(child, class_name=class_name)

        _walk_with_class(tree)
        return functions

    def _extract_all_classes(self, tree):
        """
        Extract all class definitions with their normalized bodies
        (excluding method definitions, keeping only class-level statements).
        """
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Class-level statements only (exclude method defs themselves)
                class_stmts = [
                    stmt for stmt in node.body
                    if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                if len(class_stmts) >= self.min_statements:
                    normalized = tuple(self._normalize_code(stmt) for stmt in class_stmts)
                    classes.append({
                        'name': node.name,
                        'qualified_name': node.name,
                        'lineno': node.lineno,
                        'end_lineno': node.end_lineno,
                        'statements': len(class_stmts),
                        'normalized': normalized,
                        'body': class_stmts
                    })
        return classes

    def _extract_code_blocks(self, statements, min_size, parent_name="module", parent_lineno=0):
        """Extract all code blocks of minimum size from a list of statements."""
        blocks = []
        
        if len(statements) < min_size:
            return blocks
        
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
        """
        Check for duplicated code between different functions/methods.
        Uses 'qualified_name' (ClassName.method) as the unique key so that
        identically-named methods in different classes are always compared.
        """
        issues = []
        compared = set()
        similar_groups = defaultdict(list)
        
        for i, func1 in enumerate(functions):
            for j, func2 in enumerate(functions):
                if i >= j:
                    continue
                
                # Use qualified names so ClassA.process vs ClassB.process are distinct
                pair_key = tuple(sorted([func1['qualified_name'], func2['qualified_name']]))
                if pair_key in compared:
                    continue
                compared.add(pair_key)
                
                similarity = self._calculate_similarity(func1['normalized'], func2['normalized'])
                
                if similarity >= self.similarity_threshold:
                    group_found = False
                    for group_key in list(similar_groups.keys()):
                        existing_qnames = [f['qualified_name'] for f in similar_groups[group_key]]
                        if func1['qualified_name'] in existing_qnames:
                            if func2['qualified_name'] not in existing_qnames:
                                similar_groups[group_key].append(func2)
                            group_found = True
                            break
                        elif func2['qualified_name'] in existing_qnames:
                            if func1['qualified_name'] not in existing_qnames:
                                similar_groups[group_key].append(func1)
                            group_found = True
                            break
                    
                    if not group_found:
                        group_id = f"{func1['qualified_name']}_{func2['qualified_name']}"
                        similar_groups[group_id] = [func1, func2]
        
        reported_qnames = set()
        for group_id, group in similar_groups.items():
            # Deduplicate by qualified_name
            unique_funcs = {}
            for func in group:
                if func['qualified_name'] not in unique_funcs:
                    unique_funcs[func['qualified_name']] = func
            group = list(unique_funcs.values())
            
            if len(group) >= 2:
                group_qnames = set(f['qualified_name'] for f in group)
                if group_qnames.isdisjoint(reported_qnames):
                    func_names = [
                        f"{f['qualified_name']}() (line {f['lineno']}, {f['statements']} statements)"
                        for f in group
                    ]
                    
                    similarities = []
                    for ii, f1 in enumerate(group):
                        for jj, f2 in enumerate(group):
                            if ii < jj:
                                sim = self._calculate_similarity(f1['normalized'], f2['normalized'])
                                similarities.append(sim)
                    
                    avg_similarity = sum(similarities) / len(similarities) if similarities else 0
                    
                    issues.append({
                        "rule": self.name,
                        "lineno": group[0]['lineno'],
                        "end_lineno": group[0]['end_lineno'],
                        "message": (
                            f"Similar function/method implementations "
                            f"(similarity: {avg_similarity:.1%}): {', '.join(func_names)}. "
                            f"Consider refactoring into a single function."
                        )
                    })
                    
                    reported_qnames.update(group_qnames)
        
        return issues

    def _check_class_to_class(self, classes):
        """Check for duplicated class-level code between different classes."""
        issues = []
        compared = set()
        similar_groups = defaultdict(list)

        for i, cls1 in enumerate(classes):
            for j, cls2 in enumerate(classes):
                if i >= j:
                    continue

                pair_key = tuple(sorted([cls1['name'], cls2['name']]))
                if pair_key in compared:
                    continue
                compared.add(pair_key)

                similarity = self._calculate_similarity(cls1['normalized'], cls2['normalized'])

                if similarity >= self.similarity_threshold:
                    group_found = False
                    for group_key in list(similar_groups.keys()):
                        existing_names = [c['name'] for c in similar_groups[group_key]]
                        if cls1['name'] in existing_names:
                            if cls2['name'] not in existing_names:
                                similar_groups[group_key].append(cls2)
                            group_found = True
                            break
                        elif cls2['name'] in existing_names:
                            if cls1['name'] not in existing_names:
                                similar_groups[group_key].append(cls1)
                            group_found = True
                            break

                    if not group_found:
                        group_id = f"{cls1['name']}_{cls2['name']}"
                        similar_groups[group_id] = [cls1, cls2]

        reported_classes = set()
        for group_id, group in similar_groups.items():
            unique_classes = {}
            for cls in group:
                if cls['name'] not in unique_classes:
                    unique_classes[cls['name']] = cls
            group = list(unique_classes.values())

            if len(group) >= 2:
                group_names = set(c['name'] for c in group)
                if group_names.isdisjoint(reported_classes):
                    cls_names = [
                        f"{c['name']} (line {c['lineno']}, {c['statements']} class-level statements)"
                        for c in group
                    ]

                    similarities = []
                    for ii, c1 in enumerate(group):
                        for jj, c2 in enumerate(group):
                            if ii < jj:
                                sim = self._calculate_similarity(c1['normalized'], c2['normalized'])
                                similarities.append(sim)

                    avg_similarity = sum(similarities) / len(similarities) if similarities else 0

                    issues.append({
                        "rule": self.name,
                        "lineno": group[0]['lineno'],
                        "end_lineno": group[0]['end_lineno'],
                        "message": (
                            f"Similar class-level code (similarity: {avg_similarity:.1%}): "
                            f"{', '.join(cls_names)}. "
                            f"Consider extracting shared logic into a base class or mixin."
                        )
                    })

                    reported_classes.update(group_names)

        return issues

    def _check_within_functions(self, functions):
        """Check for duplicated code blocks within each function."""
        issues = []
        
        for func in functions:
            if func['statements'] < self.min_statements * 2:
                continue
            
            blocks = self._extract_code_blocks(
                func['body'], 
                self.min_statements, 
                f"function:{func['qualified_name']}", 
                func['lineno']
            )
            
            reported_pairs = set()
            
            for i, block1 in enumerate(blocks):
                for j, block2 in enumerate(blocks):
                    if i >= j:
                        continue
                    
                    # Skip overlapping blocks
                    if not (block1['end_line'] < block2['start_line'] or block2['end_line'] < block1['start_line']):
                        continue
                    
                    pair_key = (
                        min(block1['start_line'], block2['start_line']),
                        max(block1['start_line'], block2['start_line'])
                    )
                    
                    if pair_key in reported_pairs:
                        continue
                    
                    similarity = self._calculate_similarity(block1['normalized'], block2['normalized'])
                    
                    if similarity >= self.similarity_threshold:
                        issues.append({
                            "rule": self.name,
                            "lineno": block1['start_line'],
                            "end_lineno": block1['end_line'],
                            "message": (
                                f"Duplicated code block in '{func['qualified_name']}' "
                                f"(similarity: {similarity:.1%}): "
                                f"lines {block1['start_line']}-{block1['end_line']} and "
                                f"{block2['start_line']}-{block2['end_line']} "
                                f"({block1['statements']} statements). "
                                f"Consider extracting to a separate function."
                            )
                        })
                        reported_pairs.add(pair_key)
                        break
                if reported_pairs:
                    break
        
        return issues
    
    def check(self, tree):
        issues = []
        
        functions = self._extract_all_functions(tree)
        classes = self._extract_all_classes(tree)

        # Check for similar functions/methods (across all classes and module level)
        if self.check_between_functions and len(functions) >= 2:
            issues.extend(self._check_function_to_function(functions))

        # Check for similar class-level code between different classes
        if self.check_between_functions and len(classes) >= 2:
            issues.extend(self._check_class_to_class(classes))
        
        # Check for duplicated blocks within a function/method
        if self.check_within_functions:
            issues.extend(self._check_within_functions(functions))
        
        return issues