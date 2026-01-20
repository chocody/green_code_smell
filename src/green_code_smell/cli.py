import sys
import argparse
from pathlib import Path
import csv
from datetime import datetime
import subprocess
import ast
import json
import os

# Try to import from installed package first, then relative
try:
    from green_code_smell.core import analyze_file
    from green_code_smell.rules.log_excessive import LogExcessiveRule
    from green_code_smell.rules.god_class import GodClassRule
    from green_code_smell.rules.duplicated_code import DuplicatedCodeRule
    from green_code_smell.rules.long_method import LongMethodRule
    from green_code_smell.rules.dead_code import DeadCodeRule
    from green_code_smell.rules.mutable_default_arguments import MutableDefaultArgumentsRule
except ImportError:
    # If running directly, use relative imports
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.green_code_smell.core import analyze_file
    from src.green_code_smell.rules.log_excessive import LogExcessiveRule
    from src.green_code_smell.rules.god_class import GodClassRule
    from src.green_code_smell.rules.duplicated_code import DuplicatedCodeRule
    from src.green_code_smell.rules.long_method import LongMethodRule
    from src.green_code_smell.rules.dead_code import DeadCodeRule
    from src.green_code_smell.rules.mutable_default_arguments import MutableDefaultArgumentsRule

# Import CodeCarbon
try:
    from codecarbon import EmissionsTracker
    CODECARBON_AVAILABLE = True
except ImportError:
    CODECARBON_AVAILABLE = False
    print("⚠️  Warning: codecarbon not installed. Carbon tracking disabled.")
    print("   Install with: pip install codecarbon\n")

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
        return None
    
    # If it's a directory, search for files with main entry points
    if path.is_dir():
        # Collect all candidates with main entry points
        candidates = []
        for py_file in path.rglob('*.py'):
            # Skip excluded directories
            exclude_dirs = {'venv', '.venv', 'env', '__pycache__', '.git', 'node_modules', '.pytest_cache', '.tox'}
            if any(parent.name in exclude_dirs for parent in py_file.parents):
                continue
            
            if has_main_entry(py_file):
                candidates.append(py_file)
        
        # Handle different cases
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
    Check if a Python file has a main entry point:
    - if __name__ == "__main__": block
    - def main() function
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
        
        return has_name_main or has_main_func
    except:
        return False

def setup_rules(args):
    """Setup analysis rules based on arguments"""
    rules = []
    
    if not args.no_log_check:
        rules.append(LogExcessiveRule())
    
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

def analyze_code_smells(path, args):
    """Analyze code smells in file or project"""
    python_files = get_python_files(path)
    
    if not python_files:
        print(f"⚠️  No Python files found in '{path}'")
        sys.exit(0)
    
    print(f"🔍 Analyzing {len(python_files)} Python file(s)...\n")
    
    rules = setup_rules(args)
    
    # Analyze all files
    all_results = {}
    total_issues = 0
    
    for py_file in python_files:
        try:
            issues = analyze_file(str(py_file), rules)
            if issues:
                all_results[py_file] = issues
                total_issues += len(issues)
        except Exception as e:
            print(f"⚠️  Warning: Could not analyze {py_file}: {e}")
    
    display_results(all_results, total_issues, python_files, args)
    
    return all_results

def display_results(all_results, total_issues, all_files, args):
    """Display analysis results"""
    if not all_results:
        print(f"✅ No issues found in {len(all_files)} file(s)!")
        return
    
    print("=" * 80)
    print(f"⚠️  Found {total_issues} issue(s) in {len(all_results)} file(s):")
    print("=" * 80)
    
    # Sort files by number of issues (descending)
    sorted_files = sorted(all_results.items(), key=lambda x: len(x[1]), reverse=True)
    
    for file_path, issues in sorted_files:
        # Show relative path if possible
        try:
            display_path = file_path.relative_to(Path.cwd())
        except ValueError:
            display_path = file_path
        
        print(f"\n📄 {display_path} ({len(issues)} issue(s))")
        print("-" * 80)
        
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
    print("\n" + "=" * 80)
    print("📊 Summary by Rule:")
    print("-" * 80)
    
    rule_summary = {}
    for issues in all_results.values():
        for issue in issues:
            rule = issue['rule']
            rule_summary[rule] = rule_summary.get(rule, 0) + 1
    
    for rule_name, count in sorted(rule_summary.items(), key=lambda x: x[1], reverse=True):
        print(f"  {rule_name}: {count} issue(s)")
    
    print("=" * 80 + "\n")

def read_codecarbon_csv(csv_path='emissions.csv'):
    """Read carbon emissions data from codecarbon CSV file and store in separate lists"""
    emissions_list = []
    energy_consumed_list = []
    region_list = []
    country_name_list = []
    cpu_power_list = []
    ram_power_list = []
    cpu_energy_list = []
    ram_energy_list = []
    emissions_rate_list = []
    
    if not Path(csv_path).exists():
        return (emissions_list, energy_consumed_list, region_list, country_name_list,
                cpu_power_list, ram_power_list,
                cpu_energy_list, ram_energy_list, emissions_rate_list)
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                emissions_list.append(float(row.get('emissions', 0)))
                energy_consumed_list.append(float(row.get('energy_consumed', 0)))
                region_list.append(row.get('region', 'N/A'))
                country_name_list.append(row.get('country_name', 'N/A'))
                cpu_power_list.append(float(row.get('cpu_power', 0)))
                ram_power_list.append(float(row.get('ram_power', 0)))
                cpu_energy_list.append(float(row.get('cpu_energy', 0)))
                ram_energy_list.append(float(row.get('ram_energy', 0)))
                emissions_rate_list.append(float(row.get('emissions_rate', 0)))
    except Exception as e:
        print(f"⚠️  Warning: Could not read codecarbon CSV: {e}")
    
    return (emissions_list, energy_consumed_list, region_list, country_name_list,
            cpu_power_list, ram_power_list,
            cpu_energy_list, ram_energy_list, emissions_rate_list)

def carbon_track(path, args):
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
            if target_file == "error no entry point found":
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
    print("-" * 80)
    
    # Clear existing emissions.csv if exists
    csv_path = 'emissions.csv'
    if Path(csv_path).exists():
        try:
            Path(csv_path).unlink()
        except:
            pass
    
    # Run the target file with carbon tracking
    tracker = None
    try:
        import logging
        logging.getLogger("codecarbon").setLevel(logging.CRITICAL)
        
        tracker = EmissionsTracker(
            log_level="critical",
            save_to_file=True,
            save_to_api=False,
            output_file=csv_path,
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
        
        tracker.stop()
        
        # Show output from the run
        if result.stdout:
            print("\n📝 Program output:")
            print(result.stdout)
        else:
            print("\n⚠️  No output captured. The entry point was executed but may not have produced any output.")
            print("   This could mean:")
            print("   - The program ran silently without print statements")
            print("   - The main() function was not called")
            print("   - The entry point only performs background operations\n")
        
        if result.stderr:
            print("\n⚠️  Program errors/warnings:")
            print(result.stderr)
        
        if result.returncode != 0:
            print(f"\n⚠️  Program exited with code {result.returncode}")
        
    except subprocess.TimeoutExpired:
        if tracker:
            try:
                tracker.stop()
            except:
                pass
        print("⚠️  Program execution timed out (30s limit)")
        return
    except Exception as e:
        if tracker:
            try:
                tracker.stop()
            except:
                pass
        print(f"⚠️  Error running program: {e}")
        return
    
    # Read and display results from CSV
    (emissions_list, energy_consumed_list, region_list, country_name_list,
     cpu_power_list, ram_power_list,
     cpu_energy_list, ram_energy_list, emissions_rate_list) = read_codecarbon_csv(csv_path)
    
    if emissions_list:
        # Get single values from lists (first entry)
        emission = emissions_list[0]
        energy_consumed = energy_consumed_list[0]
        region = region_list[0]
        country_name = country_name_list[0]
        cpu_power = cpu_power_list[0]
        ram_power = ram_power_list[0]
        cpu_energy = cpu_energy_list[0]
        ram_energy = ram_energy_list[0]
        emissions_rate = emissions_rate_list[0]

        # Mock SCI
        sci = 3

        # Save log history of running lib
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

        if len(data) == 0:
            status = "Normal"
            id = 0
        else:
            id = data[-1]["id"]
            if sci < data[-1]["SCI"]:
                status = "Greener"
            elif sci == data[-1]["SCI"] + 1:
                status = "Normal"
            else:
                status = "Hotter"

        metric = {
            "id": id,
            "date_time": str(datetime.now()),
            "emission": emission,
            "enerygy_consumed": energy_consumed,
            "region": region,
            "country_name": country_name,
            "emission_rate": emissions_rate,
            "SCI": sci,
            "status": status
        }

        data.append(metric)
        json_str = json.dumps(data, indent=4)
        with open(file_path, "w") as f:
            f.write(json_str)
        
        # Display results
        print("\n" + "=" * 80)
        print("🌍 Carbon Emissions Report:")
        print("-" * 80)
        print(f"Target file: {target_file}")
        print(f"CPU power: {cpu_power:.6f} W")
        print(f"CPU energy: {cpu_energy:.6f} kWh")
        print(f"RAM power: {ram_power:.6f} W")
        print(f"RAM energy: {ram_energy:.6f} kWh")
        print(f"Total energy consumed: {energy_consumed:.6f} kWh")
        print(f"Carbon emissions: {emission:.6e} kg CO2")
        print(f"Emissions rate: {emissions_rate:.6f} kg CO2/kWh")
        print(f"Region: {region}")
        print(f"Country: {country_name}")
        print("=" * 80)

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
    analyze_code_smells(args.path, args)
    carbon_track(args.path, args)

    print("\n✨ Analysis complete.\n")

if __name__ == "__main__":
    main()