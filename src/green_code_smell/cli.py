import sys
import argparse
from pathlib import Path

# Try to import from installed package first, then relative
try:
    from green_code_smell.core import analyze_file
    from green_code_smell.rules.log_excessive import LogExcessiveRule
    from green_code_smell.rules.god_class import GodClassRule
    from green_code_smell.rules.duplicated_code import DuplicatedCodeRule
except ImportError:
    # If running directly, use relative imports
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.green_code_smell.core import analyze_file
    from src.green_code_smell.rules.log_excessive import LogExcessiveRule
    from src.green_code_smell.rules.god_class import GodClassRule
    from src.green_code_smell.rules.duplicated_code import DuplicatedCodeRule

def main():
    parser = argparse.ArgumentParser(
        description='Check Python file for green code smells.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s myfile.py
  %(prog)s myfile.py --no-log-check
  %(prog)s myfile.py --max-methods 5
  %(prog)s myfile.py --dup-min-lines 3
        """
    )
    
    parser.add_argument('file', help='Path to Python file to check')
    
    # Logging rules
    parser.add_argument('--no-log-check', action='store_true', 
                       help='Disable excessive logging detection')
    
    # God Class rules
    parser.add_argument('--no-god-class', action='store_true', 
                       help='Disable God Class detection')
    parser.add_argument('--max-methods', type=int, default=10, 
                       help='Max methods for God Class (default: 10)')
    parser.add_argument('--max-attributes', type=int, default=10, 
                       help='Max attributes for God Class (default: 10)')
    parser.add_argument('--max-lines', type=int, default=200, 
                       help='Max lines for God Class (default: 200)')
    
    # Duplicated Code rules
    parser.add_argument('--no-dup-check', action='store_true', 
                       help='Disable duplicated code detection')
    parser.add_argument('--dup-min-lines', type=int, default=5, 
                       help='Min lines for duplicated code (default: 5)')
    parser.add_argument('--dup-min-occurrences', type=int, default=2, 
                       help='Min occurrences for duplicated code (default: 2)')
    
    args = parser.parse_args()
    
    # Check if file exists
    if not Path(args.file).exists():
        print(f"❌ Error: File '{args.file}' not found!")
        sys.exit(1)
    
    # Setup rules
    rules = []
    
    if not args.no_log_check:
        rules.append(LogExcessiveRule())
    
    if not args.no_god_class:
        rules.append(GodClassRule(
            max_methods=args.max_methods,
            max_attributes=args.max_attributes,
            max_lines=args.max_lines
        ))
    
    if not args.no_dup_check:
        rules.append(DuplicatedCodeRule(
            min_lines=args.dup_min_lines,
            min_occurrences=args.dup_min_occurrences
        ))
    
    if not rules:
        print("⚠️  Warning: No rules enabled!")
        sys.exit(0)
    
    # Analyze file
    try:
        print(f"🔍 Analyzing {args.file}...\n")
        issues = analyze_file(args.file, rules)
        
        if not issues:
            print(f"✅ No issues found in {args.file}!")
        else:
            print(f"⚠️  Found {len(issues)} issue(s) in {args.file}:")
            print("=" * 80)
            
            # Group by rule
            by_rule = {}
            for issue in issues:
                rule = issue['rule']
                if rule not in by_rule:
                    by_rule[rule] = []
                by_rule[rule].append(issue)
            
            for rule_name, rule_issues in by_rule.items():
                print(f"\n{rule_name} ({len(rule_issues)} issue(s)):")
                print("-" * 80)
                for issue in rule_issues:
                    print(f"  Line {issue['lineno']}: {issue['message']}")
            
            print("\n" + "=" * 80)
            
    except Exception as e:
        print(f"❌ Error analyzing file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()