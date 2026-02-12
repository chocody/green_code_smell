import sys
import argparse
from pathlib import Path
from datetime import datetime
import subprocess
import ast
import json
import os

# Try to import from installed package first, then relative
try:
    from green_code_smell.core import analyze_file
    from green_code_smell.rules.god_class import GodClassRule
    from green_code_smell.rules.duplicated_code import DuplicatedCodeRule
    from green_code_smell.rules.long_method import LongMethodRule
    from green_code_smell.rules.dead_code import DeadCodeRule
    from green_code_smell.rules.mutable_default_arguments import MutableDefaultArgumentsRule
    from green_code_smell.core import analyze_project, analyze_file
    from green_code_smell.constants import BREAK_LINE_NO, KG_GRAMS, SEC_HOUR
except ImportError:
    # If running directly, use relative imports
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.green_code_smell.core import analyze_file
    from src.green_code_smell.rules.god_class import GodClassRule
    from src.green_code_smell.rules.duplicated_code import DuplicatedCodeRule
    from src.green_code_smell.rules.long_method import LongMethodRule
    from src.green_code_smell.rules.dead_code import DeadCodeRule
    from src.green_code_smell.rules.mutable_default_arguments import MutableDefaultArgumentsRule
    from src.green_code_smell.core import analyze_project, analyze_file
    from src.green_code_smell.constants import BREAK_LINE_NO, KG_GRAMS, SEC_HOUR

# Import CodeCarbon
try:
    from codecarbon import EmissionsTracker
    CODECARBON_AVAILABLE = True
except ImportError:
    CODECARBON_AVAILABLE = False
    print("⚠️  Warning: codecarbon not installed. Carbon tracking disabled.")
    print("   Install with: pip install codecarbon\n")

def calculate_cosmic_cfp(file_path):
    """
    Calculate COSMIC Function Points (CFP) from Python source code.
    Compliant with ISO/IEC 19761:2011 (COSMIC v4.0.2).
    
    Data movements:
    - E (Entry): User data input from external sources
    - X (Exit): Results output to external systems
    - R (Read): Data retrieval from persistent storage (DB, files)
    - W (Write): Data write to persistent storage (DB, files)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        total_cfp = 0
        
        # Database operations (persistent storage access)
        db_read_patterns = {
            'query', 'select', 'find', 'fetch', 'get', 'load', 'filter',
            'all', 'first', 'one', 'read', 'execute'
        }
        db_write_patterns = {
            'insert', 'update', 'delete', 'save', 'create', 'put',
            'commit', 'execute', 'upsert', 'bulk_write'
        }
        
        # User/External input sources
        entry_patterns = {
            'input', 'getline', 'stdin', 'request', 'parse_args', 'argv',
            'json', 'loads', 'yaml', 'parse', 'environ'
        }
        
        # User/External output destinations
        exit_patterns = {
            'print', 'write', 'return', 'render', 'jsonify', 'dump',
            'response', 'send', 'emit', 'stdout', 'stderr'
        }
        
        # File I/O operations (persistent storage)
        file_read_patterns = {'open', 'read', 'load', 'pickle'}
        file_write_patterns = {'open', 'write', 'dump', 'save', 'pickle'}

        # Extract functions (1 Function = 1 Functional Process per ISO/IEC 19761)
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        
        if not functions:
            functions = [tree]

        for func_node in functions:
            movements = {'E': 0, 'X': 0, 'R': 0, 'W': 0}
            
            for node in ast.walk(func_node):
                # Analyze function/method calls for data movements
                if isinstance(node, ast.Call):
                    func_name = ''
                    full_call = ''
                    
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id.lower()
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr.lower()
                        # Try to get full call chain for better detection
                        if isinstance(node.func.value, ast.Name):
                            full_call = f"{node.func.value.id}.{func_name}".lower()
                        elif isinstance(node.func.value, ast.Attribute):
                            full_call = f"*.{func_name}".lower()
                    
                    if func_name:
                        # Detect persistent storage READ (database/file operations)
                        if any(pattern in func_name for pattern in db_read_patterns):
                            if any(keyword in full_call for keyword in {'query', 'select', 'find', 'filter'}):
                                movements['R'] += 1
                                continue
                        
                        if func_name in file_read_patterns or 'read' in func_name:
                            movements['R'] += 1
                            continue
                        
                        # Detect persistent storage WRITE (database/file operations)
                        if any(pattern in func_name for pattern in db_write_patterns):
                            movements['W'] += 1
                            continue
                        
                        if func_name in file_write_patterns or 'dump' in func_name:
                            movements['W'] += 1
                            continue
                        
                        # Detect user/external INPUT (Entry)
                        if any(pattern in func_name for pattern in entry_patterns):
                            movements['E'] += 1
                            continue
                        
                        # Detect user/external OUTPUT (Exit)
                        if any(pattern in func_name for pattern in exit_patterns):
                            if func_name != 'return':  # return is handled separately
                                movements['X'] += 1
                                continue
                
                # Count explicit Return statements as Exit (function result output)
                if isinstance(node, ast.Return) and node.value is not None:
                    movements['X'] += 1
                
                # Count Yield as Exit (generator output)
                if isinstance(node, (ast.Yield, ast.YieldFrom)):
                    movements['X'] += 1
            
            # Calculate CFP for this process (sum of all data movements)
            # According to COSMIC: minimum process size = 2 CFP (at least 1 movement in and 1 movement out)
            # But we count movements, not processes, so minimum is 0
            process_size = sum(movements.values())
            total_cfp += process_size
        
        # Ensure minimum 1 CFP to prevent division by zero in SCI calculation
        return max(total_cfp, 1)
        
    except Exception as e:
        print(f"⚠️  Warning: Could not calculate COSMIC CFP for {file_path}: {e}")
        return 1

def calculate_green_metrics(
    energy_consumed_kwh,
    emissions_rate_grams_per_kwh,
    total_lines_of_code,
    embodied_carbon=0 # Because we use the same environment so no need to calculate for compare the result
):
    """
    Calculate comprehensive green metrics for code analysis
    
    SCI Formula: SCI = ((E × I) + M) / R
    
    Where:
    - E = Energy consumed (kWh)
    - I = Carbon intensity (gCO2eq/kWh)
    - M = Embodied carbon (gCO2eq)
    - R = Lines of Code (LOC) - the functional unit
    
    Returns dict with SCI metrics
    """
    
    # Total operational emissions
    operational_emissions = energy_consumed_kwh * emissions_rate_grams_per_kwh
    total_emissions = operational_emissions + embodied_carbon
    
    # Metric 1: SCI per LOC of code smells
    if total_lines_of_code > 0:
        sci_per_line = total_emissions / total_lines_of_code
    else:
        sci_per_line = 0
    
    return {
        "total_emissions_gCO2eq": total_emissions,
        "total_loc_code_smells": total_lines_of_code,
        "sci_gCO2eq_per_line": sci_per_line,
    }


def determine_green_status(current_sci_per_exec, previous_sci_per_exec):
    """
    Compare current SCI per LOC with previous to determine status
    Lower SCI = better (less carbon intensive)
    """
    if previous_sci_per_exec is None:
        return "Initial"
    elif current_sci_per_exec < previous_sci_per_exec * 0.90:  # 10% improvement
        return "Greener ✅"
    elif current_sci_per_exec > previous_sci_per_exec * 1.10:  # 10% increase
        return "Hotter ⚠️"
    else:
        return "Normal"

def impact_analysis(data, avg_emission, total_loc):
    """
    Display code smell LOC vs carbon emission analysis comparing previous and current runs.
    
    Args:
        data: List of historical metric entries
        avg_emission: Current average carbon emission (kg CO2)
        total_loc: Current total lines of code smells
    """
    print(f"\n📊 Code Smell LOC vs Carbon Emission Analysis")
    if len(data) >= 2:
        previous_emission = data[-2].get("emission_kg")
        previous_loc = data[-2].get("lines_of_code", 0)
        current_loc = total_loc if total_loc else 0
        
        carbon_diff = previous_emission - avg_emission
        loc_diff = previous_loc - current_loc
        
        # Display previous and current runs
        print(f"\n   Previous Run:")
        print(f"      Carbon Emission: {previous_emission:.6e} kg CO2")
        print(f"      Code Smell LOC:  {previous_loc} LOC")
        if previous_loc > 0:
            print(f"      Carbon per LOC:  {previous_emission / previous_loc:.6e} kg CO2/LOC")
        
        print(f"\n   Current Run:")
        print(f"      Carbon Emission: {avg_emission:.6e} kg CO2")
        print(f"      Code Smell LOC:  {current_loc} LOC")
        if current_loc > 0:
            print(f"      Carbon per LOC:  {avg_emission / current_loc:.6e} kg CO2/LOC")
        else:
            print(f"      ✅ All code smells fixed! (0 LOC)")
        
        # Determine impact message
        print(f"\n   Impact Analysis:")
        
        # LOC change status
        if loc_diff > 0:
            loc_status = f"✅ Code smells reduced by {loc_diff} LOC"
        elif loc_diff < 0:
            loc_status = f"⚠️  Code smells increased by {abs(loc_diff)} LOC"
        else:
            loc_status = f"➡️  Code smell LOC unchanged ({current_loc} LOC)"
        
        # Carbon change status
        if carbon_diff > 0:
            carbon_status = f"✅ Carbon emission decreased by {carbon_diff:.6e} kg CO2"
        elif carbon_diff < 0:
            carbon_status = f"⚠️  Carbon emission increased by {abs(carbon_diff):.6e} kg CO2"
        else:
            carbon_status = f"➡️  Carbon emission unchanged"
        
        print(f"      {loc_status}")
        print(f"      {carbon_status}")
        
        # Calculate and display correlation metric
        if loc_diff != 0 and carbon_diff != 0:
            # Both changed - show correlation
            if (loc_diff > 0 and carbon_diff > 0) or (loc_diff < 0 and carbon_diff < 0):
                # Positive correlation: less LOC = less carbon, or more LOC = more carbon
                metric = abs(carbon_diff) / abs(loc_diff)
                if loc_diff > 0:
                    print(f"      📉 Carbon saved per LOC removed: {metric:.6e} kg CO2/LOC")
                    print(f"      💡 Less code smell = Less carbon emission!")
                else:
                    print(f"      📈 Carbon increase per LOC added: {metric:.6e} kg CO2/LOC")
                    print(f"      💡 More code smell = More carbon emission")
            else:
                # Negative correlation - other factors involved
                print(f"      ℹ️  Carbon change may be due to other factors")
        elif loc_diff == 0 and carbon_diff != 0:
            print(f"      ℹ️  Carbon change from other optimizations/factors")
    else:
        print(f"\n   Current Run (Initial):")
        print(f"      Carbon Emission: {avg_emission:.6e} kg CO2")
        print(f"      Code Smell LOC:  {total_loc if total_loc else 0} LOC")
        if total_loc and total_loc > 0:
            print(f"      Carbon per LOC:  {avg_emission / total_loc:.6e} kg CO2/LOC")
        print(f"      ℹ️  No previous run to compare")


def get_python_files(path):
    """Get all Python files from path (file or directory)"""
    path = Path(path)
    
    if path.is_file():
        if path.suffix == '.py':
            return [path]
        else:
            print(f"❌ Error: '{path}' is not a Python file!")
            sys.exit(1)
    elif path.is_dir():
        # Find all .py files recursively, excluding common directories
        exclude_dirs = {'venv', '.venv', 'env', '__pycache__', '.git', 'node_modules', '.pytest_cache', '.tox'}
        python_files = []
        
        for py_file in path.rglob('*.py'):
            # Check if any parent directory is in exclude list
            if not any(parent.name in exclude_dirs for parent in py_file.parents):
                python_files.append(py_file)
        
        return sorted(python_files)
    else:
        print(f"❌ Error: Path '{path}' not found!")
        sys.exit(1)

def find_main_file(path):
    """
    Try to automatically find the main entry point file in a project.
    Returns the most likely main file, or an error message string, or None.
    """
    path = Path(path)
    
    # If it's a file, check if it has a main function or if __name__ == "__main__"
    if path.is_file():
        if has_main_entry(path):
            return path
        if has_main_function_only(path):
            return f"error has main function only {path}"
        return None
    
    # If it's a directory, search for files with main entry points
    if path.is_dir():
        # Collect all candidates with main entry points
        candidates = []
        main_only_candidates = []
        
        for py_file in path.rglob('*.py'):
            # Skip excluded directories
            exclude_dirs = {'venv', '.venv', 'env', '__pycache__', '.git', 'node_modules', '.pytest_cache', '.tox'}
            if any(parent.name in exclude_dirs for parent in py_file.parents):
                continue
            
            if has_main_entry(py_file):
                candidates.append(py_file)
            elif has_main_function_only(py_file):
                main_only_candidates.append(py_file)
        
        # Handle different cases
        if len(candidates) == 0 and len(main_only_candidates) > 0:
            # Found files with def main() but no entry point
            if len(main_only_candidates) == 1:
                return f"error has main function only {main_only_candidates[0]}"
            else:
                return f"error has main function only multiple {' '.join(str(f) for f in main_only_candidates)}"
        
        if len(candidates) == 0:
            return "error no entry point found"
        
        if len(candidates) > 1:
            print(f"🔍 Found {len(candidates)} main entry candidates:")
            for candidate in candidates:
                try:
                    display_path = candidate.relative_to(Path.cwd())
                except ValueError:
                    display_path = candidate
                print(f"    {display_path}")
            print()
            return "error too many entry point found please specify"
        
        if candidates:
            return candidates[0]
    
    return None

def has_main_entry(file_path):
    """
    Check if a Python file has a proper main entry point:
    - if __name__ == "__main__": block
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the file
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            # Check for if __name__ == "__main__":
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Compare):
                    if isinstance(node.test.left, ast.Name) and node.test.left.id == '__name__':
                        if any(isinstance(comp, ast.Constant) and comp.value == "__main__" 
                               for comp in node.test.comparators):
                            return True
        
        return False
    except:
        return False

def has_main_function_only(file_path):
    """
    Check if a Python file has def main() but no proper entry point.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the file
        tree = ast.parse(content)
        
        has_name_main = False
        has_main_func = False
        
        for node in ast.walk(tree):
            # Check for if __name__ == "__main__":
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Compare):
                    if isinstance(node.test.left, ast.Name) and node.test.left.id == '__name__':
                        if any(isinstance(comp, ast.Constant) and comp.value == "__main__" 
                               for comp in node.test.comparators):
                            has_name_main = True
            
            # Check for def main():
            if isinstance(node, ast.FunctionDef) and node.name == 'main':
                has_main_func = True
        
        return has_main_func and not has_name_main
    except:
        return False

def setup_rules(args):
    """Setup analysis rules based on arguments"""
    rules = []
    
    if not args.no_god_class:
        rules.append(GodClassRule(
            max_methods=args.max_methods,
            max_cc=args.max_cc,
            max_loc=args.max_loc
        ))
    
    if not args.no_dup_check:
        rules.append(DuplicatedCodeRule(
            similarity_threshold=args.dup_similarity,
            min_statements=args.dup_min_statements,
            check_within_functions=args.dup_check_within,
            check_between_functions=args.dup_check_between
        ))
    
    if not args.no_long_method:
        rules.append(LongMethodRule(
            max_loc=args.method_max_loc,
            max_cc=args.max_cyclomatic
        ))
    
    if not args.no_dead_code:
        rules.append(DeadCodeRule())

    if not args.no_mutable_default:
        rules.append(MutableDefaultArgumentsRule())

    if not rules:
        print("⚠️  Warning: No rules enabled!")
        sys.exit(0)
    
    return rules

def count_total_loc_code_smells(all_results):
    """Count total lines of code involved in code smells from analysis results"""
    total_loc = 0
    
    for issues in all_results.values():
        for issue in issues:
            if issue.get('rule') == 'MututableDefaultArguments':
                total_loc += 1
                continue  # Skip mutable default arguments for LOC count because they are single line issues
            lineno = issue.get('lineno')
            end_lineno = issue.get('end_lineno', lineno)
            if lineno and end_lineno:
                total_loc += (end_lineno - lineno + 1)
            # print(f"Debug: Issue {issue.get('rule')} loc of code smells: {end_lineno - lineno + 1}")
    
    return total_loc

def analyze_code_smells(path, args):
    """Analyze code smells in file or project"""
    python_files = get_python_files(path)
    
    if not python_files:
        print(f"⚠️  No Python files found in '{path}'")
        sys.exit(0)
    
    print(f"🔍 Analyzing {len(python_files)} Python file(s)...\n")
    
    rules = setup_rules(args)
    
    # For projects, use analyze_project to handle DeadCodeRule properly
    if Path(path).is_dir():
        all_issues = analyze_project(path, rules)
        # Group issues by file
        all_results = {}
        for issue in all_issues:
            file_path = issue.get('file')
            if file_path:
                file_key = Path(file_path)
                if file_key not in all_results:
                    all_results[file_key] = []
                all_results[file_key].append(issue)
        total_issues = len(all_issues)
    else:
        # Single file analysis
        all_results = {}
        all_issues = analyze_file(str(python_files[0]), rules, project_root=path)
        if all_issues:
            all_results[python_files[0]] = all_issues
        total_issues = len(all_issues)

    total_loc = count_total_loc_code_smells(all_results)
    
    display_results(all_results, total_issues, python_files, args)
    
    return all_results, total_loc

def display_results(all_results, total_issues, all_files, args):
    """Display analysis results"""
    if not all_results:
        print(f"✅ No issues found in {len(all_files)} file(s)!")
        return
    
    print("=" * BREAK_LINE_NO)
    print(f"⚠️  Found {total_issues} issue(s) in {len(all_results)} file(s):")
    print("=" * BREAK_LINE_NO)
    
    # Sort files by number of issues (descending)
    sorted_files = sorted(all_results.items(), key=lambda x: len(x[1]), reverse=True)
    
    for file_path, issues in sorted_files:
        # Show relative path if possible
        try:
            display_path = file_path.relative_to(Path.cwd())
        except (ValueError, TypeError):
            # If file_path is a string, convert to Path first
            try:
                display_path = Path(file_path).relative_to(Path.cwd())
            except ValueError:
                display_path = Path(file_path)
        
        print(f"\n📄 {display_path} ({len(issues)} issue(s))")
        print("-" * BREAK_LINE_NO)
        
        # Group issues by rule
        by_rule = {}
        for issue in issues:
            rule = issue['rule']
            if rule not in by_rule:
                by_rule[rule] = []
            by_rule[rule].append(issue)
        
        # Display issues grouped by rule
        for rule_name, rule_issues in sorted(by_rule.items()):
            print(f"\n  {rule_name} ({len(rule_issues)} issue(s)):")
            for issue in rule_issues:
                print(f"    Line {issue['lineno']}: {issue['message']}")

    # Summary by rule type
    print("\n" + "=" * BREAK_LINE_NO)
    print("📊 Summary by Rule:")
    print("-" * BREAK_LINE_NO)
    
    rule_summary = {}
    for issues in all_results.values():
        for issue in issues:
            rule = issue['rule']
            rule_summary[rule] = rule_summary.get(rule, 0) + 1
    
    for rule_name, count in sorted(rule_summary.items(), key=lambda x: x[1], reverse=True):
        print(f"  {rule_name}: {count} issue(s)")
    
    print("=" * BREAK_LINE_NO + "\n")


def carbon_track(path, args, total_loc=0):
    """Track carbon emissions for running the target application"""
    if not CODECARBON_AVAILABLE or args.no_carbon:
        return
    
    # Determine which file to run for carbon tracking
    target_file = None
    
    if args.carbon_run:
        # User specified a file to run
        target_file = Path(args.carbon_run)
        if not target_file.exists():
            print(f"⚠️  Warning: Specified file '{args.carbon_run}' not found. Skipping carbon tracking.")
            return
        if not target_file.suffix == '.py':
            print(f"⚠️  Warning: Specified file '{args.carbon_run}' is not a Python file. Skipping carbon tracking.")
            return
    else:
        # Try to auto-detect main file
        target_file = find_main_file(path)
        
        # Check for error messages returned from find_main_file
        if isinstance(target_file, str):
            if target_file.startswith("error has main function only"):
                # Extract file path from error message
                if target_file.startswith("error has main function only multiple"):
                    files_part = target_file.replace("error has main function only multiple ", "")
                    print("⚠️  Found files with def main() but no entry point:")
                    for f in files_part.split():
                        print(f"    {f}")
                    print("   Files must contain: if __name__ == \"__main__\":")
                else:
                    file_path = target_file.replace("error has main function only ", "")
                    print(f"⚠️  Warning: {file_path} has def main() but no entry point.")
                    print("   The file must contain: if __name__ == \"__main__\":")
                print("   Use --carbon-run <file.py> to specify a file with proper entry point, or")
                print("   use --no-carbon to disable carbon tracking.\n")
            elif target_file == "error no entry point found":
                print("⚠️  No main entry point found for carbon tracking.")
                print("   Use --carbon-run <file.py> to specify the file to run, or")
                print("   use --no-carbon to disable carbon tracking.\n")
            elif target_file == "error too many entry point found please specify":
                print("⚠️  Multiple main entry point candidates found. Please specify which one to run.")
                print("   Use --carbon-run <file.py> to specify the file to run, or")
                print("   use --no-carbon to disable carbon tracking.\n")
            return
        
        if not target_file:
            print("⚠️  No main entry point found for carbon tracking.")
            print("   Use --carbon-run <file.py> to specify the file to run, or")
            print("   use --no-carbon to disable carbon tracking.\n")
            return
    
    print(f"\n🌱 Tracking carbon emissions for: {target_file}")
    print("   Running 5 iterations for average calculations...")
    print("-" * BREAK_LINE_NO)
    
    # Run the target file with carbon tracking 5 times
    all_runs = []
    
    try:
        import logging
        logging.getLogger("codecarbon").setLevel(logging.CRITICAL)
        
        for run_num in range(1, 6):
            print(f"\n▶️  Run {run_num}/5...")
            tracker = None
            emissions_data = None
            
            try:
                tracker = EmissionsTracker(
                    log_level="critical",
                    save_to_file=False,
                    save_to_api=False,
                    allow_multiple_runs=True,
                    project_name=f"carbon_track_{target_file.stem}"
                )
                tracker.start()
                
                # Run the target file as a subprocess
                result = subprocess.run(
                    [sys.executable, str(target_file)],
                    capture_output=True,
                    text=True,
                    timeout=30  # 30 second timeout
                )
                
                duration = tracker.stop()
                emissions_data = tracker.final_emissions_data
                
                if emissions_data:
                    all_runs.append({
                        'duration': duration,
                        'emission': emissions_data.emissions,
                        'energy_consumed': emissions_data.energy_consumed,
                        'cpu_power': emissions_data.cpu_power,
                        'ram_power': emissions_data.ram_power,
                        'cpu_energy': emissions_data.cpu_energy,
                        'ram_energy': emissions_data.ram_energy,
                        'emissions_rate': emissions_data.emissions_rate,
                        'region': emissions_data.region,
                        'country_name': emissions_data.country_name,
                    })
                    print(f"  ✓ Run {run_num} completed")
            
            except subprocess.TimeoutExpired:
                print(f"  ⚠️  Run {run_num} timed out")
                continue
            except Exception as e:
                print(f"  ⚠️  Run {run_num} failed: {e}")
                continue
        
        # Show first run's program output
        if result.stdout:
            print("\n📋 Program output (from first run):")
            print(result.stdout)
        else:
            print("\n⚠️  No output captured. The entry point was executed but may not have produced any output.")
        
        if result.stderr:
            print("\n⚠️  Program errors/warnings:")
            print(result.stderr)
        
        if result.returncode != 0:
            print(f"\n⚠️  Program exited with code {result.returncode}")

    except Exception as e:
        print(f"⚠️  Error during carbon tracking: {e}")
        return
    
    # Calculate averages from all runs
    if all_runs:
        # avg_duration = sum(r['duration'] for r in all_runs) / len(all_runs)
        avg_emission = sum(r['emission'] for r in all_runs) / len(all_runs)
        avg_energy = sum(r['energy_consumed'] for r in all_runs) / len(all_runs)
        # avg_cpu_power = sum(r['cpu_power'] for r in all_runs) / len(all_runs)
        # avg_ram_power = sum(r['ram_power'] for r in all_runs) / len(all_runs)
        # avg_cpu_energy = sum(r['cpu_energy'] for r in all_runs) / len(all_runs)
        # avg_ram_energy = sum(r['ram_energy'] for r in all_runs) / len(all_runs)
        avg_emissions_rate = sum(r['emissions_rate'] for r in all_runs) / len(all_runs)
        region = all_runs[0]['region']
        country_name = all_runs[0]['country_name']

        # Convert emissions_rate from kg CO2/kWs to gCO2eq/kWh
        emissions_rate_grams = avg_emissions_rate * SEC_HOUR * KG_GRAMS
        
        # Calculate green metrics using SCI formula with LOC as functional unit
        green_metrics = calculate_green_metrics(
            energy_consumed_kwh=avg_energy,
            emissions_rate_grams_per_kwh=emissions_rate_grams,
            total_lines_of_code=total_loc,
            embodied_carbon=0
        )

        # Calculate COSMIC Function Points from the target file
        cosmic_cfp = calculate_cosmic_cfp(target_file)
        
        # SCI Calculation: (E_kWh × I_kg_CO2_per_kWh × 1000_g_per_kg) / R_CFP
        # Result: g CO2 per COSMIC Function Point
        if cosmic_cfp > 0:
            sci_per_cfp = (avg_energy * avg_emissions_rate * 1000) / cosmic_cfp
        else:
            sci_per_cfp = 0

        # Load history for comparison
        file_path = "history.json"
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = [data]
                except json.JSONDecodeError:
                    data = []
        else:
            data = []

        # Determine status
        if len(data) == 0:
            status = "Initial"
            id_num = 1
            previous_sci_per_loc = None
        else:
            id_num = data[-1]["id"] + 1
            previous_sci_per_loc = data[-1].get("sci_gCO2eq_per_line")
            status = determine_green_status(
                green_metrics["sci_gCO2eq_per_line"],
                previous_sci_per_loc
            )
        
        # Calculate improvement percentage
        if previous_sci_per_loc and previous_sci_per_loc > 0:
            improvement = ((previous_sci_per_loc - green_metrics["sci_gCO2eq_per_line"]) 
                          / previous_sci_per_loc) * 100
        else:
            improvement = None

        # Create metric entry
        metric = {
            "id": id_num,
            "date_time": str(datetime.now()),
            "target_file": str(target_file),
            "duration_seconds": duration,
            "emission_kg": avg_emission,
            "energy_consumed_kWh": avg_energy,
            "region": region,
            "country_name": country_name,
            "emissions_rate_gCO2eq_per_kWh": emissions_rate_grams,
            "total_emissions_gCO2eq": green_metrics["total_emissions_gCO2eq"],
            "lines_of_code": green_metrics["total_loc_code_smells"],
            "sci_gCO2eq_per_line": green_metrics["sci_gCO2eq_per_line"],
            "status": status,
            "cfp": cosmic_cfp,
            "sci_per_cfp": sci_per_cfp,
            "improvement_percent": improvement
        }
        
        data.append(metric)
        json_str = json.dumps(data, indent=4)
        with open(file_path, "w") as f:
            f.write(json_str)
        
        # Display results
        print("\n" + "=" * BREAK_LINE_NO)
        print("🌍 GREEN CODE CARBON EMISSIONS REPORT 🌍")
        print("=" * BREAK_LINE_NO)
        print(f"\n📋 Execution Details:")
        print(f"  Target file: {target_file}")
        print(f"  Duration: {duration:.2f} seconds")
        print(f"\n⚡ Energy & Emissions:")
        print(f"  Total energy consumed: {avg_energy:.6f} kWh")
        print(f"  Carbon emissions: {avg_emission:.6e} kg CO2")
        print(f"  Emissions rate: {emissions_rate_grams:.2f} gCO2eq/kWh")
        print(f"  Region: {region}")
        print(f"  Country: {country_name}")
        print(f"\n📊 Code Metrics:")
        print(f"  COSMIC Function Points: {cosmic_cfp} CFP")
        print(f"  Total lines of code: {green_metrics['total_loc_code_smells']} LOC")
        print(f"\n🌱 SCI Metrics (Software Carbon Intensity):")
        print(f"  ├─ Per line of code: {green_metrics['sci_gCO2eq_per_line']:.8f} gCO2eq/LOC")
        print(f"  │  ℹ️  Lower is greener! Shorter code = lower carbon footprint")
        print(f"  ├─ Per cosmic function point: {sci_per_cfp:.8f} gCO2eq/cfp")
        print(f"  │  ℹ️  Lower is greener! less data movement = less carbon footprint")
        print(f"  └─")
        
        # print(f"\n📈 Status: {status}")
        # if improvement is not None:
        #     print(f"   Previous: {previous_sci_per_loc:6e}")
        #     print(f"   Now: {green_metrics["sci_gCO2eq_per_line"]:6e}")
        #     if improvement > 0:
        #         print(f"   Decrease Carbon emission around: {abs(improvement):.2f}%")
        #     else:
        #         print(f"   Increase Carbon emission around: {abs(improvement):.2f}%")

        impact_analysis(data, avg_emission, total_loc)
        
        print("=" * BREAK_LINE_NO)


def main():
    parser = argparse.ArgumentParser(
        description='Check Python file or project for green code smells.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze single file
  %(prog)s myfile.py
  
  # Analyze entire project
  %(prog)s ./my_project
  %(prog)s .
  
  # With carbon tracking (auto-detect main file)
  %(prog)s . 
  
  # Specify file to run for carbon tracking
  %(prog)s . --carbon-run main.py
  %(prog)s . --carbon-run src/app.py
  
  # With custom options
  %(prog)s ./src --no-log-check
  %(prog)s . --max-methods 5
  
  # Duplicated code detection options
  %(prog)s . --dup-similarity 0.80
  %(prog)s . --dup-min-statements 5
  %(prog)s . --dup-check-within-only    # Check only within functions
  %(prog)s . --dup-check-between-only   # Check only between functions
  
  %(prog)s . --method-max-loc 30 --max-cyclomatic 3
  %(prog)s . --no-carbon  # Disable carbon tracking
        """
    )
    
    parser.add_argument('path', help='Path to Python file or project directory to check')
    
    # Excessive log rule
    parser.add_argument('--no-log-check', action='store_true', 
                       help='Disable excessive logging detection')
    
    # God class rule
    parser.add_argument('--no-god-class', action='store_true', 
                       help='Disable God Class detection')
    parser.add_argument('--max-methods', type=int, default=10, 
                       help='Max methods for God Class (default: 10)')
    parser.add_argument('--max-cc', type=int, default=35, 
                       help='Max cyclomatic complexity for God Class (default: 35)')
    parser.add_argument('--max-loc', type=int, default=100, 
                       help='Max lines of code for God Class (default: 100)')
    
    # Duplicated code rule
    parser.add_argument('--no-dup-check', action='store_true', 
                       help='Disable duplicated code detection')
    parser.add_argument('--dup-similarity', type=float, default=0.85, 
                       help='Similarity threshold for duplicated code (0.0-1.0, default: 0.85)')
    parser.add_argument('--dup-min-statements', type=int, default=3,
                       help='Minimum statements in code block to check for duplication (default: 3)')
    parser.add_argument('--dup-check-within-only', action='store_true',
                       help='Check duplicated code only within functions (not between functions)')
    parser.add_argument('--dup-check-between-only', action='store_true',
                       help='Check duplicated code only between functions (not within functions)')
    
    # Long method rule
    parser.add_argument('--no-long-method', action='store_true', 
                       help='Disable Long Method detection')
    parser.add_argument('--method-max-loc', type=int, default=25, 
                       help='Max lines of code for method (default: 25)')
    parser.add_argument('--max-cyclomatic', type=int, default=10, 
                       help='Max cyclomatic complexity for method (default: 10)')
    
    # Dead code rule
    parser.add_argument('--no-dead-code', action='store_true', 
                       help='Disable Dead Code detection')
    
    #mutable default arguments rule
    parser.add_argument('--no-mutable-default', action='store_true',
                       help='Disable Mutable Default Arguments detection')
    
    # Carbon tracking
    parser.add_argument('--no-carbon', action='store_true', 
                       help='Disable carbon emissions tracking')
    parser.add_argument('--carbon-run', type=str, metavar='FILE',
                       help='Specify Python file to run for carbon tracking (e.g., main.py, app.py)')
    
    args = parser.parse_args()
    
    # If no path provided, show help
    if args.path is None:
        parser.print_help()
        sys.exit(0)
    
    # If path is "run", use current directory
    if args.path == "run":
        args.path = "."
    
    # Handle duplicated code check options
    if args.dup_check_within_only and args.dup_check_between_only:
        print("❌ Error: Cannot use both --dup-check-within-only and --dup-check-between-only")
        sys.exit(1)
    
    if args.dup_check_within_only:
        args.dup_check_within = True
        args.dup_check_between = False
    elif args.dup_check_between_only:
        args.dup_check_within = False
        args.dup_check_between = True
    else:
        args.dup_check_within = True
        args.dup_check_between = True
    
    # Run analysis
    all_result, total_loc = analyze_code_smells(args.path, args)
    carbon_track(args.path, args, total_loc)

    print("\n✨ Analysis complete.\n")

if __name__ == "__main__":
    main()