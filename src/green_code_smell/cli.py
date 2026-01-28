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
    from green_code_smell.rules.log_excessive import LogExcessiveRule
    from green_code_smell.rules.god_class import GodClassRule
    from green_code_smell.rules.duplicated_code import DuplicatedCodeRule
    from green_code_smell.rules.long_method import LongMethodRule
    from green_code_smell.rules.dead_code import DeadCodeRule
    from green_code_smell.rules.mutable_default_arguments import MutableDefaultArgumentsRule
    from green_code_smell.core import analyze_project, analyze_file
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
    from src.green_code_smell.core import analyze_project, analyze_file

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
    """Analyze code smells in file or project. Returns tuple of (results_dict, total_count, smells_by_rule)"""
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
    
    # Count smells by rule type
    smells_by_rule = {}
    for issues in all_results.values():
        for issue in issues:
            rule_name = issue['rule']
            smells_by_rule[rule_name] = smells_by_rule.get(rule_name, 0) + 1
    
    display_results(all_results, total_issues, python_files, args)
    
    return all_results, total_issues, smells_by_rule

def get_rule_energy_weights():
    """
    Return estimated energy/carbon weights for each rule type (kWh).
    These are absolute energy estimates for what each code smell type typically consumes.
    
    Estimation logic (in kWh per execution):
    - God Class: 0.000005 kWh - Large class with many method lookups and instance variable access
    - Long Method: 0.000004 kWh - Complex branching logic and loop iterations
    - Duplicated Code: 0.000003 kWh - Redundant execution paths
    - Excessive Logging: 0.000003 kWh - I/O operations (disk/network writes)
    - Dead Code: 0.000001 kWh - Just compiled, minimal or no execution
    - Mutable Default Arguments: 0.0000005 kWh - Object creation on function call
    """
    return {
        "GodClass": 0.000005,
        "LongMethod": 0.000004,
        "DuplicatedCode": 0.000003,
        "ExcessiveLogging": 0.000003,
        "DeadCode": 0.000001,
        "MutableDefaultArguments": 0.0000005
    }

def get_rule_intensity_weights(avg_emissions_rate):
    """
    Return estimated carbon intensity (gCO2eq/kWh) for each rule type.
    Different code smells use different energy sources (CPU vs I/O) which have different carbon intensities.
    
    Estimation logic:
    - Excessive Logging: Highest intensity (1.1x) - Heavy I/O operations on disk/network (typically higher carbon)
    - God Class: High intensity (1.0x) - CPU-intensive operations (baseline)
    - Long Method: High intensity (1.0x) - CPU-intensive with branches (baseline)
    - Duplicated Code: Medium intensity (0.95x) - Mixed execution paths (slightly lower)
    - Dead Code: Low intensity (0.8x) - Just loaded, minimal execution (very low)
    - Mutable Default Arguments: Very low intensity (0.7x) - Minimal runtime overhead (very low)
    """
    base_intensity = avg_emissions_rate * 1000  # Convert to gCO2eq/kWh
    
    return {
        "ExcessiveLogging": base_intensity * 1.1,
        "GodClass": base_intensity * 1.0,
        "LongMethod": base_intensity * 1.0,
        "DuplicatedCode": base_intensity * 0.95,
        "DeadCode": base_intensity * 0.8,
        "MutableDefaultArguments": base_intensity * 0.7
    }

def calculate_energy_per_rule(total_energy, total_emissions, smells_by_rule, avg_emissions_rate):
    """
    Estimate energy and emissions for each rule type, constrained by total measured energy.
    Uses the total measured energy as a base and estimates what portion comes from code smells.
    
    Allocation: Allocates 70% of total energy to code smells, reserves 30% for non-smell code.
    Distribution: Distributes allocated energy across smell types based on their weight and count.
    
    Returns:
        dict: {rule_name: {'count': int, 'energy_kwh': float, 'emissions_kg_co2': float, 
                          'weight': float, 'intensity_gco2_per_kwh': float, 'sci_per_rule': float}}
    """
    weights = get_rule_energy_weights()  # Relative weight per smell type
    intensities = get_rule_intensity_weights(avg_emissions_rate)
    results = {}
    
    # Estimate what portion of total energy comes from code smells
    # Allocation factor: code smells typically account for ~70% of inefficiency
    # Remaining 30% is non-smell code (framework, dependencies, etc.)
    smell_energy_allocation = 0.70
    energy_allocated_to_smells = total_energy * smell_energy_allocation
    
    # Calculate total weight across all smell types (weight * count)
    total_weight = 0
    for rule_name, count in smells_by_rule.items():
        weight = weights.get(rule_name, 0.000001)
        total_weight += weight * count
    
    if total_weight == 0:
        total_weight = 1
    
    # Distribute allocated energy proportionally across smell types
    for rule_name, count in smells_by_rule.items():
        weight = weights.get(rule_name, 0.000001)
        intensity = intensities.get(rule_name, avg_emissions_rate * 1000)
        
        # Calculate this rule's proportion of total weight
        rule_weight = weight * count
        proportion = rule_weight / total_weight
        
        # Allocate proportional share of smell energy
        energy_for_rule = proportion * energy_allocated_to_smells
        emissions_for_rule = energy_for_rule * (intensity / 1000)
        
        results[rule_name] = {
            'count': count,
            'weight': weight,
            'intensity_gco2_per_kwh': intensity,
            'energy_kwh': energy_for_rule,
            'emissions_kg_co2': emissions_for_rule,
            'energy_per_smell_kwh': weight,
            'emissions_per_smell_kg_co2': weight * (intensity / 1000),
            'sci_per_rule': (weight * intensity),
        }
    
    return results

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
        except (ValueError, TypeError):
            # If file_path is a string, convert to Path first
            try:
                display_path = Path(file_path).relative_to(Path.cwd())
            except ValueError:
                display_path = Path(file_path)
        
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

def carbon_track(path, args, code_smell_count=0, smells_by_rule=None):
    """Calculate estimated energy and emissions for each code smell type (no application execution).
    
    Args:
        path: Path to analyze
        args: Command line arguments
        code_smell_count: Total number of code smells found in analysis
        smells_by_rule: Dict of {rule_name: count} for per-rule energy estimation
    """
    # Skip carbon tracking if no code smells found
    if code_smell_count == 0:
        print("\n✅ No code smells found! Skipping carbon emissions estimation.")
        print("   (Energy/emissions estimation only applies when code smells are detected.)\n")
        return
    
    if smells_by_rule is None:
        smells_by_rule = {}
    
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
    print("-" * 80)
    
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
        avg_duration = sum(r['duration'] for r in all_runs) / len(all_runs)
        avg_emission = sum(r['emission'] for r in all_runs) / len(all_runs)
        avg_energy = sum(r['energy_consumed'] for r in all_runs) / len(all_runs)
        avg_cpu_power = sum(r['cpu_power'] for r in all_runs) / len(all_runs)
        avg_ram_power = sum(r['ram_power'] for r in all_runs) / len(all_runs)
        avg_cpu_energy = sum(r['cpu_energy'] for r in all_runs) / len(all_runs)
        avg_ram_energy = sum(r['ram_energy'] for r in all_runs) / len(all_runs)
        avg_emissions_rate = sum(r['emissions_rate'] for r in all_runs) / len(all_runs)
        region = all_runs[0]['region']
        country_name = all_runs[0]['country_name']
        
        # Calculate per-rule energy and emissions breakdown using estimated values
        energy_breakdown_by_rule = calculate_energy_per_rule(avg_energy, avg_emission, smells_by_rule, avg_emissions_rate)
        
        # Calculate total ESTIMATED energy and emissions (independent estimates)
        # E and I are estimated based on code smell characteristics, not measured totals
        total_estimated_energy = sum(data['energy_kwh'] for data in energy_breakdown_by_rule.values())
        total_estimated_emissions = sum(data['emissions_kg_co2'] for data in energy_breakdown_by_rule.values())
        
        # Calculate estimated I from the independent estimates
        # I = total estimated emissions / total estimated energy
        if total_estimated_energy > 0:
            estimated_intensity_gco2 = (total_estimated_emissions / total_estimated_energy) * 1000
        else:
            estimated_intensity_gco2 = avg_emissions_rate * 1000
        
        # Calculate global SCI using ESTIMATED E and ESTIMATED I
        # SCI = (E_estimated * I_estimated) / R
        # Note: These are independent estimates, NOT proportional to measured totals
        global_sci = (total_estimated_energy * estimated_intensity_gco2) / code_smell_count if code_smell_count > 0 else 0
        
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
            id = 1
        else:
            id = data[-1]["id"] + 1
            if global_sci < data[-1]["SCI"]:
                status = "Greener"
            elif global_sci == data[-1]["SCI"]:
                status = "Normal"
            else:
                status = "Hotter"
        
        metric = {
            "id": id,
            "date_time": str(datetime.now()),
            "total_code_smells": code_smell_count,
            "measured_energy_total_kwh": avg_energy,
            "estimated_energy_from_smells_kwh": total_estimated_energy,
            "estimated_emission_from_smells_kg_co2": total_estimated_emissions,
            "measured_emission_total_kg_co2": avg_emission,
            "region": region,
            "country_name": country_name,
            "measured_emission_rate_kg_co2_per_kwh": avg_emissions_rate,
            "estimated_intensity_gco2_per_kwh": estimated_intensity_gco2,
            "SCI_formula": "(E_estimated*I_estimated)/R where E/I are estimated from measured totals, R=code_smells",
            "SCI": global_sci,
            "status": status,
            "breakdown_by_rule": {
                rule_name: {
                    "smell_count": data["count"],
                    "weight": data["weight"],
                    "intensity_gco2_per_kwh": data["intensity_gco2_per_kwh"],
                    "estimated_energy_kwh": data["energy_kwh"],
                    "estimated_emissions_kg_co2": data["emissions_kg_co2"],
                    "energy_per_smell_kwh": data["energy_per_smell_kwh"],
                    "emissions_per_smell_kg_co2": data["emissions_per_smell_kg_co2"],
                    "sci_per_smell": data["sci_per_rule"]
                }
                for rule_name, data in energy_breakdown_by_rule.items()
            }
        }
        
        data.append(metric)
        json_str = json.dumps(data, indent=4)
        with open(file_path, "w") as f:
            f.write(json_str)
        
        # Display averaged results
        print("\n" + "=" * 80)
        print(f"🌍 Carbon Emissions Report (Average of {len(all_runs)} runs):")
        print("-" * 80)
        print(f"Target file: {target_file}")
        print(f"Code smells found: {code_smell_count}")
        print(f"\nMeasured (Total Application):")
        print(f"  Total energy consumed: {avg_energy:.6f} kWh")
        print(f"  Total carbon emissions: {avg_emission:.6e} kg CO2")
        print(f"  Measured emissions rate: {avg_emissions_rate:.6f} kg CO2/kWh")
        print(f"\nEstimated (From Code Smells Only):")
        print(f"  Energy from smells: {total_estimated_energy:.6f} kWh")
        print(f"  Emissions from smells: {total_estimated_emissions:.6e} kg CO2")
        print(f"  Intensity from smells: {estimated_intensity_gco2:.6f} gCO2eq/kWh")
        print(f"\nRegion: {region}")
        print(f"Country: {country_name}")
        
        # Display per-rule breakdown
        if energy_breakdown_by_rule:
            print(f"\n📋 Energy/Emissions Estimation by Rule Type:")
            print("-" * 80)
            for rule_name, data in sorted(energy_breakdown_by_rule.items(), 
                                         key=lambda x: x[1]['energy_kwh'], 
                                         reverse=True):
                print(f"\n  {rule_name}:")
                print(f"    Count: {data['count']} smell(s)")
                print(f"    Energy per smell: {data['energy_per_smell_kwh']:.9f} kWh (estimated)")
                print(f"    Total estimated energy (E): {data['energy_kwh']:.9f} kWh")
                print(f"    Intensity (I): {data['intensity_gco2_per_kwh']:.6f} gCO2eq/kWh (estimated)")
                print(f"    Total estimated emissions: {data['emissions_kg_co2']:.6e} kg CO2")
                print(f"    Emissions per smell: {data['emissions_per_smell_kg_co2']:.6e} kg CO2")
                print(f"    SCI per smell: {data['sci_per_rule']:.10f}")
        
        print(f"\n📊 SCI Calculation: (E_estimated × I_estimated) / R")
        print(f"   E (Estimated Energy from Smells): {total_estimated_energy:.9f} kWh")
        print(f"   I (Estimated Intensity from Smells): {estimated_intensity_gco2:.6f} gCO2eq/kWh")
        print(f"   R (Code Smells): {code_smell_count}")
        print(f"   SCI Score: {global_sci:.10f}")
        print(f"   Status: {status}")
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
    all_results, total_code_smells, smells_by_rule = analyze_code_smells(args.path, args)
    carbon_track(args.path, args, code_smell_count=total_code_smells, smells_by_rule=smells_by_rule)

    print("\n✨ Analysis complete.\n")

if __name__ == "__main__":
    main()