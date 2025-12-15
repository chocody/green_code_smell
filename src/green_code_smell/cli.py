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
except ImportError:
    # If running directly, use relative imports
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.green_code_smell.core import analyze_file
    from src.green_code_smell.rules.log_excessive import LogExcessiveRule
    from src.green_code_smell.rules.god_class import GodClassRule
    from src.green_code_smell.rules.duplicated_code import DuplicatedCodeRule
    from src.green_code_smell.rules.long_method import LongMethodRule

# Import CodeCarbon
try:
    from codecarbon import EmissionsTracker
    CODECARBON_AVAILABLE = True
except ImportError:
    CODECARBON_AVAILABLE = False
    print("⚠️  Warning: codecarbon not installed. Carbon tracking disabled.")
    print("   Install with: pip install codecarbon\n")

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
  %(prog)s myfile.py --max-loc 30 --max-cyclomatic 3
  %(prog)s myfile.py --no-carbon  # Disable carbon tracking
        """
    )
    
    parser.add_argument('file', help='Path to Python file to check')
    
    #excessive log rule
    parser.add_argument('--no-log-check', action='store_true', 
                       help='Disable excessive logging detection')
    
    #god class rule
    parser.add_argument('--no-god-class', action='store_true', 
                       help='Disable God Class detection')
    parser.add_argument('--max-methods', type=int, default=10, 
                       help='Max methods for God Class (default: 10)')
    parser.add_argument('--max-attributes', type=int, default=10, 
                       help='Max attributes for God Class (default: 10)')
    parser.add_argument('--max-lines', type=int, default=200, 
                       help='Max lines for God Class (default: 200)')
    
    #duplicadted code rule
    parser.add_argument('--no-dup-check', action='store_true', 
                       help='Disable duplicated code detection')
    parser.add_argument('--dup-min-lines', type=int, default=5, 
                       help='Min lines for duplicated code (default: 5)')
    parser.add_argument('--dup-min-occurrences', type=int, default=2, 
                       help='Min occurrences for duplicated code (default: 2)')
    
    #long method rule
    parser.add_argument('--no-long-method', action='store_true', 
                       help='Disable Long Method detection')
    parser.add_argument('--max-loc', type=int, default=25, 
                       help='Max lines of code for method (default: 25)')
    parser.add_argument('--max-cyclomatic', type=int, default=10, 
                       help='Max cyclomatic complexity (default: 10)')
    parser.add_argument('--max-loop', type=int, default=2, 
                       help='Max loop (default: 2)')
    
    #carbon tracking
    parser.add_argument('--no-carbon', action='store_true', 
                       help='Disable carbon emissions tracking')
    
    args = parser.parse_args()
    
    #check if file exist
    if not Path(args.file).exists():
        print(f"❌ Error: File '{args.file}' not found!")
        sys.exit(1)
    
    #setup rule
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
    
    if not args.no_long_method:
        rules.append(LongMethodRule(
            max_loc=args.max_loc,
            max_cyclomatic=args.max_cyclomatic
        ))
    
    if not rules:
        print("⚠️  Warning: No rules enabled!")
        sys.exit(0)
    
    # Initialize carbon tracker
    tracker = None
    if CODECARBON_AVAILABLE and not args.no_carbon:
        try:
            tracker = EmissionsTracker()
            tracker.start()
        except Exception as e:
            print(f"⚠️  Warning: Could not start carbon tracking: {e}\n")
            tracker = None
    
    try:
        print(f"🔍 Analyzing {args.file}...\n")
        issues = analyze_file(args.file, rules)
        
        # Stop carbon tracker
        emissions = None
        if tracker:
            try:
                emissions = tracker.stop()
            except Exception as e:
                print(f"⚠️  Warning: Could not stop carbon tracking: {e}")
        
        if not issues:
            print(f"✅ No issues found in {args.file}!")
        else:
            print(f"⚠️  Found {len(issues)} issue(s) in {args.file}:")
            print("=" * 80)
            
            #group by rule
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
        
        # Display carbon emissions with more precision
        if emissions is not None:
            print(f"\n🌱 Carbon Emissions:")
            # Convert to more readable units
            mg_co2 = emissions * 1_000_000  # kg to mg
            ug_co2 = emissions * 1_000_000_000  # kg to µg
            
            if emissions >= 0.001:  # >= 1g
                print(f"   {emissions * 1000:.4f} g CO2")
            elif emissions >= 0.000001:  # >= 1mg
                print(f"   {mg_co2:.4f} mg CO2")
            else:  # < 1mg
                print(f"   {ug_co2:.4f} µg CO2")
            
            # Also show in scientific notation for very small values
            print(f"   ({emissions:.6e} kg CO2)")
        
    except Exception as e:
        # Make sure to stop tracker even on error
        if tracker:
            try:
                tracker.stop()
            except:
                pass
        
        print(f"❌ Error analyzing file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()