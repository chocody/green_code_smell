import sys
import argparse
from pathlib import Path

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

def carbon_track(path, args):
    """Track carbon emissions for the analysis"""
    python_files = get_python_files(path)
    
    if not python_files:
        return
    
    # Initialize carbon tracker
    avg_emissions = []
    rules = setup_rules(args)
    
    for i in range(5):  # Run 5 times for averaging
        tracker = None
        if CODECARBON_AVAILABLE and not args.no_carbon:
            try:
                tracker = EmissionsTracker(
                    log_level="error",
                    save_to_file=False,
                    save_to_api=False,
                )
                tracker.start()
            except Exception as e:
                print(f"⚠️  Warning: Could not start carbon tracking: {e}\n")
                tracker = None
                break
        
        # Perform analysis
        try:
            for py_file in python_files:
                try:
                    analyze_file(str(py_file), rules)
                except:
                    pass  # Ignore errors during carbon tracking
        except:
            pass
        
        # Stop tracker and record emissions
        try:
            emissions = None
            if tracker:
                try:
                    emissions = tracker.stop()
                except Exception as e:
                    print(f"⚠️  Warning: Could not stop carbon tracking: {e}")
                    break
            avg_emissions.append(emissions)
        except Exception as e:
            if tracker:
                tracker.stop()
            break
    
    # Calculate and display average emissions
    if avg_emissions and any(e is not None for e in avg_emissions):
        formatted_emissions = [f"{e:.6e}" for e in avg_emissions if e is not None]
        print("\n" + "=" * 80)
        print("🌱 Carbon Emissions Tracking:")
        print("-" * 80)
        print(f"Files analyzed: {len(python_files)}")
        print(f"Runs completed: {len([e for e in avg_emissions if e is not None])}")
        print("Carbon track history each loop:", formatted_emissions)
        
        valid_emissions = [e for e in avg_emissions if e is not None]
        if valid_emissions:
            avg = sum(valid_emissions) / len(valid_emissions)
            print(f"Average carbon emissions: {avg:.6e} kg CO2")
        print("=" * 80)

def main():
    parser = argparse.ArgumentParser(
        description='Check Python file or project for green code smells.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run analysis on current project (from root)
  %(prog)s run
  
  # Analyze single file
  %(prog)s myfile.py
  
  # Analyze entire project
  %(prog)s ./my_project
  %(prog)s .
  
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
  %(prog)s run --no-carbon  # Run with carbon tracking disabled
        """
    )
    
    parser.add_argument('path', nargs='?', default=None,
                       help='Path to Python file or project directory to check (or "run" to analyze current directory)')
    
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
