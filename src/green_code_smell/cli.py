import sys
import argparse
from pathlib import Path
from datetime import datetime
import subprocess
import ast
import json
import os

from green_code_smell.constants import BREAK_LINE_NO, KG_GRAMS, SEC_HOUR
from green_code_smell.core import analyze_file, analyze_project
from green_code_smell.rules.dead_code import DeadCodeRule
from green_code_smell.rules.duplicated_code import DuplicatedCodeRule
from green_code_smell.rules.god_class import GodClassRule
from green_code_smell.rules.long_method import LongMethodRule
from green_code_smell.rules.mutable_default_arguments import MutableDefaultArgumentsRule

try:
    from codecarbon import EmissionsTracker
except ImportError:
    EmissionsTracker = None
    CODECARBON_AVAILABLE = False
else:
    CODECARBON_AVAILABLE = True

def calculate_cosmic_cfp(file_path):
    """
    Calculate COSMIC Function Points (CFP) from Python source code.
    Compliant with ISO/IEC 19761:2011 (COSMIC v4.0.2).

    Data movements are identified purely from AST structure — no keyword
    matching, no ML, no manual counting from a software spec.

    Structural derivation rules (per functional process = one function def):
    ─────────────────────────────────────────────────────────────────────────
    E  Entry   — Each unique parameter accepted by the function represents one
                 piece of data crossing the boundary inward.
                 Source: func.args (positional, keyword, *args, **kwargs)

    X  Exit    — Each point where the function sends data back across the
                 boundary: explicit return with a value, yield / yield-from,
                 and raise (exception as an outbound data movement).
                 Source: ast.Return(value≠None), ast.Yield, ast.YieldFrom,
                         ast.Raise(exc≠None)

    R  Read    — Each place the function reads a data attribute or subscript
                 FROM an object (i.e. pulls data out of a persistent group).
                 Counted once per unique (object, attribute/key) pair to avoid
                 double-counting repeated reads of the same field.
                 Source: ast.Attribute (Load ctx) and ast.Subscript (Load ctx)
                         where the receiver is not the function itself.

    W  Write   — Each place the function stores data INTO an object or
                 collection: attribute assignment and subscript assignment.
                 Counted once per unique (object, attribute/key) write target.
                 Source: assignment targets that are ast.Attribute or
                         ast.Subscript nodes (Store ctx).

    CFP for each process = E + X + R + W
    Total CFP            = sum over all functional processes (functions).
    ─────────────────────────────────────────────────────────────────────────
    """
    def _count_movements(func_node):
        movements = {'E': 0, 'X': 0, 'R': 0, 'W': 0}

        # ── E: Entry — parameters ─────────────────────────────────────────────
        args = func_node.args
        movements['E'] = (
            len(args.args)
            + len(args.posonlyargs)
            + len(args.kwonlyargs)
            + (1 if args.vararg else 0)
            + (1 if args.kwarg else 0)
        )

        # ── Collect direct statements only (exclude nested function bodies) ───
        def collect_stmts(stmts):
            """Yield statement nodes, but do NOT descend into nested func defs."""
            for stmt in stmts:
                yield stmt
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for child in ast.iter_child_nodes(stmt):
                    if isinstance(child, ast.stmt):
                        yield from collect_stmts([child])

        direct_stmts = list(collect_stmts(
            func_node.body if hasattr(func_node, 'body') else []
        ))

        # ── X: Exit — outbound data movements ────────────────────────────────
        for node in direct_stmts:
            if isinstance(node, ast.Return) and node.value is not None:
                movements['X'] += 1
            elif isinstance(node, (ast.Yield, ast.YieldFrom)):
                movements['X'] += 1
            elif isinstance(node, ast.Raise) and node.exc is not None:
                movements['X'] += 1

        # ── R: Read ──────────────────────────────────────────────────────────
        reads_seen = set()

        def _collect_reads_from_expr(expr):
            if expr is None:
                return
            if isinstance(expr, ast.Attribute) and isinstance(expr.ctx, ast.Load):
                key = (ast.dump(expr.value), expr.attr)
                if key not in reads_seen:
                    reads_seen.add(key)
                    movements['R'] += 1
                return
            if isinstance(expr, ast.Subscript) and isinstance(expr.ctx, ast.Load):
                key = (ast.dump(expr.value), ast.dump(expr.slice))
                if key not in reads_seen:
                    reads_seen.add(key)
                    movements['R'] += 1
                return
            for child in ast.iter_child_nodes(expr):
                if isinstance(child, ast.expr):
                    _collect_reads_from_expr(child)

        for node in direct_stmts:
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                rhs = node.value if hasattr(node, 'value') else None
                if rhs:
                    _collect_reads_from_expr(rhs)
            elif isinstance(node, ast.Return) and node.value is not None:
                _collect_reads_from_expr(node.value)
            elif isinstance(node, ast.Yield) and node.value is not None:
                _collect_reads_from_expr(node.value)
            elif isinstance(node, ast.Expr):
                if isinstance(node.value, ast.Call):
                    for arg in node.value.args:
                        _collect_reads_from_expr(arg)
                    for kw in node.value.keywords:
                        _collect_reads_from_expr(kw.value)

        # ── W: Write ─────────────────────────────────────────────────────────
        writes_seen = set()
        for node in direct_stmts:
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AugAssign):
                    targets = [node.target]
                elif isinstance(node, ast.AnnAssign) and node.target:
                    targets = [node.target]

                for target in targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.ctx, ast.Store):
                        key = (ast.dump(target.value), target.attr)
                        if key not in writes_seen:
                            writes_seen.add(key)
                            movements['W'] += 1
                    elif isinstance(target, ast.Subscript) and isinstance(target.ctx, ast.Store):
                        key = (ast.dump(target.value), ast.dump(target.slice))
                        if key not in writes_seen:
                            writes_seen.add(key)
                            movements['W'] += 1

        return movements

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)
        total_cfp = 0

        functions = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        if not functions:
            functions = [tree]

        for func_node in functions:
            movements = _count_movements(func_node)
            process_cfp = sum(movements.values())
            total_cfp += process_cfp

        return max(total_cfp, 1)

    except Exception as e:
        print(f"⚠️  Warning: Could not calculate COSMIC CFP for {file_path}: {e}")
        return 1


def calculate_green_metrics(
    energy_consumed_kwh,
    emissions_rate_grams_per_kwh,
    total_lines_of_code,
    embodied_carbon=0
):
    """
    Calculate comprehensive green metrics for code analysis.
    SCI Formula: SCI = ((E × I) + M) / R
    """
    operational_emissions = energy_consumed_kwh * emissions_rate_grams_per_kwh
    total_emissions = operational_emissions + embodied_carbon
    
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
    Compare current SCI per LOC with previous to determine status.
    Lower SCI = better (less carbon intensive)
    """
    if previous_sci_per_exec is None:
        return "Initial"
    elif current_sci_per_exec < previous_sci_per_exec * 0.90:
        return "Greener ✅"
    elif current_sci_per_exec > previous_sci_per_exec * 1.10:
        return "Hotter ⚠️"
    else:
        return "Normal"


SMELL_NATURE = {
    "DeadCode":                 "compile/load overhead only, not executed at runtime",
    "DuplicatedCode":           "redundant execution, wastes CPU cycles",
    "GodClass":                 "structural complexity, increases maintenance & energy",
    "LongMethod":               "high complexity, harder to optimize by interpreter",
    "MutableDefaultArguments":  "minimal runtime impact, but a correctness risk",
}


def impact_analysis(data, avg_emission, is_different_file=False):
    """
    Display code smell removal and carbon emission analysis comparing previous and current runs.
    Uses diff-based attribution: the real measured carbon difference is distributed
    proportionally among removed smells by their LOC.
    """
    print(f"\n📊 Code Smell & Carbon Emission Analysis")

    current = data[-1]
    current_smell = current.get("smell_breakdown", {})

    if is_different_file and len(data) >= 2:
        previous = data[-2]
        print(f"\n   ⚠️  Different file detected!")
        print(f"      Previous: {previous.get('target_file')}")
        print(f"      Current:  {current.get('target_file')}")
        print(f"      Cannot compare before/after results.")
        print(f"      Treating current file as new initial baseline for future comparisons.")
        print(f"\n   Current Run (New Initial):")
        print(f"      Carbon Emission: {avg_emission:.6e} kg CO2")
        if current_smell:
            print(f"\n   Code Smells Detected:")
            for rule, info in sorted(current_smell.items()):
                print(f"      {rule}: {info['count']} issue(s)")
        else:
            print(f"      ✅ No code smells detected!")
        print(f"      ℹ️  No comparison available (different file)")
        return

    if len(data) >= 2:
        previous = data[-2]
        previous_emission = previous.get("emission_kg")
        previous_smell = previous.get("smell_breakdown", {})

        all_rules = sorted(set(list(previous_smell.keys()) + list(current_smell.keys())))

        smells_removed = False
        smells_added = False
        removed_smells_detail = {}

        if all_rules:
            print(f"\n   🔍 Code Smell Changes (Before → After):")
            for rule in all_rules:
                prev_count = previous_smell.get(rule, {}).get("count", 0)
                curr_count = current_smell.get(rule, {}).get("count", 0)
                prev_loc = previous_smell.get(rule, {}).get("loc", 0)
                curr_loc = current_smell.get(rule, {}).get("loc", 0)
                count_diff = prev_count - curr_count
                loc_diff = prev_loc - curr_loc

                if count_diff > 0:
                    print(f"      ✅ {rule}: removed {count_diff} issue(s) ({prev_count} → {curr_count})")
                    smells_removed = True
                    if loc_diff > 0:
                        removed_smells_detail[rule] = loc_diff
                elif count_diff < 0:
                    print(f"      ⚠️  {rule}: added {abs(count_diff)} issue(s) ({prev_count} → {curr_count})")
                    smells_added = True
                else:
                    if curr_count == 0:
                        continue
                    print(f"      ➡️  {rule}: unchanged ({curr_count} issue(s))")

            if not any(current_smell.values()) and not any(previous_smell.values()):
                print(f"      ✅ No code smells in either run!")
            elif not any(current_smell.values()):
                print(f"      ✅ All code smells fixed!")
        else:
            print(f"\n      ✅ No code smells in either run!")

        carbon_diff = previous_emission - avg_emission

        print(f"\n   🌍 Carbon Emission Comparison:")
        print(f"      Previous: {previous_emission:.6e} kg CO2")
        print(f"      Current:  {avg_emission:.6e} kg CO2")

        if carbon_diff > 0:
            print(f"      ✅ Carbon emission decreased by {carbon_diff:.6e} kg CO2")
        elif carbon_diff < 0:
            print(f"      ⚠️  Carbon emission increased by {abs(carbon_diff):.6e} kg CO2")
        else:
            print(f"      ➡️  Carbon emission unchanged")

        if smells_removed and removed_smells_detail:
            total_removed_loc = sum(removed_smells_detail.values())

            if carbon_diff > 0 and total_removed_loc > 0:
                print(f"\n   📉 Estimated Carbon Savings per Removed Smell:")
                print(f"      (Based on real carbon diff of {carbon_diff:.6e} kg CO2,")
                print(f"       attributed proportionally by {total_removed_loc} LOC removed)")
                print()
                for rule in sorted(removed_smells_detail.keys()):
                    loc_removed = removed_smells_detail[rule]
                    proportion = loc_removed / total_removed_loc
                    estimated_saving = carbon_diff * proportion
                    nature = SMELL_NATURE.get(rule, "")
                    pct = proportion * 100

                    print(f"      {rule}:")
                    print(f"         {loc_removed} LOC removed ({pct:.1f}% of total removed)")
                    print(f"         Est. carbon saved: {estimated_saving:.6e} kg CO2")
                    if nature:
                        print(f"         Note: {nature}")

                print(f"\n      💡 Less code smell = Less carbon emission!")

            elif carbon_diff <= 0:
                print(f"\n   📉 Removed Smell Detail:")
                for rule in sorted(removed_smells_detail.keys()):
                    loc_removed = removed_smells_detail[rule]
                    nature = SMELL_NATURE.get(rule, "")
                    print(f"      {rule}: {loc_removed} LOC removed")
                    if nature:
                        print(f"         Note: {nature}")

                print(f"\n      ⚠️  Warning: Code smells were removed but carbon emission did not decrease.")
                print(f"      This might be due to other factors (system load, background processes, etc.)")

        elif smells_added and carbon_diff < 0:
            print(f"\n      💡 More code smell = More carbon emission")
        elif not smells_removed and not smells_added and carbon_diff != 0:
            print(f"\n      ℹ️  Carbon change from other optimizations/factors")
    else:
        print(f"\n   Current Run (Initial):")
        print(f"      Carbon Emission: {avg_emission:.6e} kg CO2")
        if current_smell:
            print(f"\n   Code Smells Detected:")
            for rule, info in sorted(current_smell.items()):
                print(f"      {rule}: {info['count']} issue(s)")
        else:
            print(f"      ✅ No code smells detected!")
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
        exclude_dirs = {'venv', '.venv', 'env', '__pycache__', '.git', 'node_modules', '.pytest_cache', '.tox'}
        python_files = []
        
        for py_file in path.rglob('*.py'):
            if not any(parent.name in exclude_dirs for parent in py_file.parents):
                python_files.append(py_file)
        
        return sorted(python_files)
    else:
        print(f"❌ Error: Path '{path}' not found!")
        sys.exit(1)


def find_main_file(path):
    """Try to automatically find the main entry point file in a project."""
    path = Path(path)
    
    if path.is_file():
        if has_main_entry(path):
            return path
        if has_main_function_only(path):
            return f"error has main function only {path}"
        return None
    
    if path.is_dir():
        candidates = []
        main_only_candidates = []
        
        for py_file in path.rglob('*.py'):
            exclude_dirs = {'venv', '.venv', 'env', '__pycache__', '.git', 'node_modules', '.pytest_cache', '.tox'}
            if any(parent.name in exclude_dirs for parent in py_file.parents):
                continue
            
            if has_main_entry(py_file):
                candidates.append(py_file)
            elif has_main_function_only(py_file):
                main_only_candidates.append(py_file)
        
        if len(candidates) == 0 and len(main_only_candidates) > 0:
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
    """Check if a Python file has a proper main entry point."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
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
    """Check if a Python file has def main() but no proper entry point."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        has_name_main = False
        has_main_func = False
        
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Compare):
                    if isinstance(node.test.left, ast.Name) and node.test.left.id == '__name__':
                        if any(isinstance(comp, ast.Constant) and comp.value == "__main__" 
                               for comp in node.test.comparators):
                            has_name_main = True
            
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
                continue
            lineno = issue.get('lineno')
            end_lineno = issue.get('end_lineno', lineno)
            if lineno and end_lineno:
                total_loc += (end_lineno - lineno + 1)
    
    return total_loc


def compute_smell_breakdown(all_results):
    """Compute code smell breakdown by rule from analysis results (count + LOC)."""
    breakdown = {}
    for issues in all_results.values():
        for issue in issues:
            rule = issue.get('rule', 'Unknown')
            if rule not in breakdown:
                breakdown[rule] = {"count": 0, "loc": 0}
            breakdown[rule]["count"] += 1
            if rule == 'MutableDefaultArguments':
                breakdown[rule]["loc"] += 1
            else:
                lineno = issue.get('lineno')
                end_lineno = issue.get('end_lineno', lineno)
                if lineno and end_lineno:
                    breakdown[rule]["loc"] += (end_lineno - lineno + 1)
    return breakdown


def analyze_code_smells(path, args):
    """Analyze code smells in file or project"""
    python_files = get_python_files(path)
    
    if not python_files:
        print(f"⚠️  No Python files found in '{path}'")
        sys.exit(0)
    
    print(f"🔍 Analyzing {len(python_files)} Python file(s)...\n")
    
    rules = setup_rules(args)
    
    if Path(path).is_dir():
        all_issues = analyze_project(path, rules)
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
    
    sorted_files = sorted(all_results.items(), key=lambda x: len(x[1]), reverse=True)
    
    for file_path, issues in sorted_files:
        try:
            display_path = file_path.relative_to(Path.cwd())
        except (ValueError, TypeError):
            try:
                display_path = Path(file_path).relative_to(Path.cwd())
            except ValueError:
                display_path = Path(file_path)
        
        print(f"\n📄 {display_path} ({len(issues)} issue(s))")
        print("-" * BREAK_LINE_NO)
        
        by_rule = {}
        for issue in issues:
            rule = issue['rule']
            if rule not in by_rule:
                by_rule[rule] = []
            by_rule[rule].append(issue)
        
        for rule_name, rule_issues in sorted(by_rule.items()):
            print(f"\n  {rule_name} ({len(rule_issues)} issue(s)):")
            for issue in rule_issues:
                print(f"    Line {issue['lineno']}: {issue['message']}")

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


def run_entry_point_with_carbon(target_file, iterations=5, timeout=30):
    """
    Run the target Python file multiple times under CodeCarbon tracking.
    Returns (all_runs, last_result, last_duration).
    """
    all_runs = []
    last_result = None
    last_duration = None

    import logging
    logging.getLogger("codecarbon").setLevel(logging.CRITICAL)

    for run_num in range(1, iterations + 1):
        print(f"\n▶️  Run {run_num}/{iterations}...")

        try:
            tracker = EmissionsTracker(
                log_level="critical",
                save_to_file=False,
                save_to_api=False,
                allow_multiple_runs=True,
                project_name=f"carbon_track_{target_file.stem}"
            )
            tracker.start()

            result = subprocess.run(
                [sys.executable, str(target_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            duration = tracker.stop()
            emissions_data = tracker.final_emissions_data

            last_result = result
            last_duration = duration

            if emissions_data:
                all_runs.append({
                    "duration":       duration,
                    "emission":       emissions_data.emissions,
                    "energy_consumed": emissions_data.energy_consumed,
                    "cpu_power":      emissions_data.cpu_power,
                    "ram_power":      emissions_data.ram_power,
                    "cpu_energy":     emissions_data.cpu_energy,
                    "ram_energy":     emissions_data.ram_energy,
                    "emissions_rate": emissions_data.emissions_rate,
                    "region":         emissions_data.region,
                    "country_name":   emissions_data.country_name,
                })
                print(f"  ✓ Run {run_num} completed")

        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Run {run_num} timed out")
            continue
        except Exception as e:
            print(f"  ⚠️  Run {run_num} failed: {e}")
            continue

    return all_runs, last_result, last_duration


def compute_average_run_data(all_runs):
    """Compute average emission/energy statistics from a list of CodeCarbon runs."""
    if not all_runs:
        return None

    avg_emission       = sum(r["emission"] for r in all_runs) / len(all_runs)
    avg_energy         = sum(r["energy_consumed"] for r in all_runs) / len(all_runs)
    avg_emissions_rate = sum(r["emissions_rate"] for r in all_runs) / len(all_runs)
    region             = all_runs[0]["region"]
    country_name       = all_runs[0]["country_name"]

    return {
        "avg_emission":       avg_emission,
        "avg_energy":         avg_energy,
        "avg_emissions_rate": avg_emissions_rate,
        "region":             region,
        "country_name":       country_name,
    }


def save_metric_to_history(
    history_path,
    target_file,
    duration,
    avg_emission,
    avg_energy,
    emissions_rate_grams,
    green_metrics,
    cosmic_cfp,
    smell_breakdown=None,
):
    """Persist the computed green metrics into the history file."""
    if os.path.exists(history_path):
        with open(history_path, "r") as f:
            try:
                data = json.load(f)
                if not isinstance(data, list):
                    data = [data]
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    is_different_file = False

    if len(data) == 0:
        status = "Initial"
        id_num = 1
        previous_sci_per_loc = None
    else:
        id_num = data[-1]["id"] + 1
        previous_target = data[-1].get("target_file")

        if previous_target:
            prev_path = str(Path(previous_target).resolve())
            curr_path = str(Path(target_file).resolve())
            if prev_path != curr_path:
                is_different_file = True

        if is_different_file:
            status = "Initial"
            previous_sci_per_loc = None
        else:
            previous_sci_per_loc = data[-1].get("sci_gCO2eq_per_line")
            status = determine_green_status(
                green_metrics["sci_gCO2eq_per_line"], previous_sci_per_loc
            )

    if previous_sci_per_loc and previous_sci_per_loc > 0:
        improvement = (
            (previous_sci_per_loc - green_metrics["sci_gCO2eq_per_line"])
            / previous_sci_per_loc * 100
        )
    else:
        improvement = None

    metric = {
        "id":                            id_num,
        "date_time":                     str(datetime.now()),
        "target_file":                   str(target_file),
        "duration_seconds":              duration,
        "emission_kg":                   avg_emission,
        "energy_consumed_kWh":           avg_energy,
        "region":                        green_metrics.get("region", None),
        "country_name":                  green_metrics.get("country_name", None),
        "emissions_rate_gCO2eq_per_kWh": emissions_rate_grams,
        "total_emissions_gCO2eq":        green_metrics["total_emissions_gCO2eq"],
        "lines_of_code":                 green_metrics["total_loc_code_smells"],
        "sci_gCO2eq_per_line":           green_metrics["sci_gCO2eq_per_line"],
        "status":                        status,
        "cfp":                           cosmic_cfp,
        "sci_per_cfp":                   green_metrics.get("sci_per_cfp", None),
        "improvement_percent":           improvement,
        "smell_breakdown":               smell_breakdown,
    }

    data.append(metric)

    with open(history_path, "w") as f:
        json.dump(data, f, indent=4)

    return data, is_different_file


def display_carbon_report(
    target_file,
    duration,
    avg_emission,
    avg_energy,
    emissions_rate_grams,
    region,
    country_name,
    green_metrics,
    cosmic_cfp,
    sci_per_cfp,
):
    """Pretty-print the carbon and SCI metrics report."""
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


def _resolve_carbon_target_file(path, args):
    """Resolve which Python file to run for carbon tracking."""
    if args.carbon_run:
        target = Path(args.carbon_run)
        if not target.exists():
            print(f"⚠️  Warning: Specified file '{args.carbon_run}' not found. Skipping carbon tracking.")
            return None
        if target.suffix != '.py':
            print(f"⚠️  Warning: Specified file '{args.carbon_run}' is not a Python file. Skipping carbon tracking.")
            return None
        return target

    target = find_main_file(path)
    if isinstance(target, str):
        if target.startswith("error has main function only"):
            if target.startswith("error has main function only multiple"):
                files_part = target.replace("error has main function only multiple ", "")
                print("⚠️  Found files with def main() but no entry point:")
                for f in files_part.split():
                    print(f"    {f}")
                print("   Files must contain: if __name__ == \"__main__\":")
            else:
                file_path = target.replace("error has main function only ", "")
                print(f"⚠️  Warning: {file_path} has def main() but no entry point.")
                print("   The file must contain: if __name__ == \"__main__\":")
            print("   Use --carbon-run <file.py> to specify a file with proper entry point, or")
            print("   use --no-carbon to disable carbon tracking.\n")
        elif target == "error no entry point found":
            print("⚠️  No main entry point found for carbon tracking.")
            print("   Use --carbon-run <file.py> to specify the file to run, or")
            print("   use --no-carbon to disable carbon tracking.\n")
        elif target == "error too many entry point found please specify":
            print("⚠️  Multiple main entry point candidates found. Please specify which one to run.")
            print("   Use --carbon-run <file.py> to specify the file to run, or")
            print("   use --no-carbon to disable carbon tracking.\n")
        return None
    if not target:
        print("⚠️  No main entry point found for carbon tracking.")
        print("   Use --carbon-run <file.py> to specify the file to run, or")
        print("   use --no-carbon to disable carbon tracking.\n")
        return None
    return target


def _print_program_output(result):
    """Print stdout/stderr and return code from the last carbon run."""
    if result is None:
        return
    if result.stdout:
        print("\n📋 Program output (from last run):")
        print(result.stdout)
    else:
        print("\n⚠️  No output captured. The entry point was executed but may not have produced any output.")
    if result.stderr:
        print("\n⚠️  Program errors/warnings:")
        print(result.stderr)
    if result.returncode != 0:
        print(f"\n⚠️  Program exited with code {result.returncode}")


def _process_carbon_runs(target_file, all_runs, result, duration, total_loc, smell_breakdown=None):
    """Compute averages, green metrics, save history, and display report."""
    averages = compute_average_run_data(all_runs)
    if not averages:
        return False

    avg_emission         = averages["avg_emission"]
    avg_energy           = averages["avg_energy"]
    avg_emissions_rate   = averages["avg_emissions_rate"]
    region               = averages["region"]
    country_name         = averages["country_name"]
    emissions_rate_grams = avg_emissions_rate * SEC_HOUR * KG_GRAMS

    green_metrics = calculate_green_metrics(
        energy_consumed_kwh=avg_energy,
        emissions_rate_grams_per_kwh=emissions_rate_grams,
        total_lines_of_code=total_loc,
        embodied_carbon=0,
    )
    cosmic_cfp  = calculate_cosmic_cfp(target_file)
    sci_per_cfp = (avg_energy * avg_emissions_rate * 1000) / cosmic_cfp if cosmic_cfp > 0 else 0

    green_metrics_with_context = dict(green_metrics)
    green_metrics_with_context["region"]       = region
    green_metrics_with_context["country_name"] = country_name
    green_metrics_with_context["sci_per_cfp"]  = sci_per_cfp

    data, is_different_file = save_metric_to_history(
        "history.json",
        target_file,
        duration,
        avg_emission,
        avg_energy,
        emissions_rate_grams,
        green_metrics_with_context,
        cosmic_cfp,
        smell_breakdown,
    )
    display_carbon_report(
        target_file,
        duration,
        avg_emission,
        avg_energy,
        emissions_rate_grams,
        region,
        country_name,
        green_metrics,
        cosmic_cfp,
        sci_per_cfp,
    )
    impact_analysis(data, avg_emission, is_different_file)
    return True


# ══════════════════════════════════════════════════════════════════════════════
# Per-function carbon tracking using CodeCarbon
# ══════════════════════════════════════════════════════════════════════════════

def run_with_per_function_carbon(target_file: Path):
    """
    Run target file and track carbon per function using CodeCarbon.

    How it works:
    - sys.settrace fires on every "call" and "return" event
    - Each function call gets its own EmissionsTracker (start on call, stop on return)
    - Only tracks files inside the project directory (skips stdlib/site-packages)

    Note: parent functions include the energy of their children since
    hardware power is measured for the whole machine during that time window.
    """
    import logging
    logging.getLogger("codecarbon").setLevel(logging.CRITICAL)

    project_dir        = str(target_file.parent.resolve())
    function_emissions = {}  # { "file::func": {calls, total_co2_kg, total_energy_kwh} }
    call_stack         = []  # stack of (key, tracker)

    def trace(frame, event, arg):
        filename  = frame.f_code.co_filename
        func_name = frame.f_code.co_name

        # Only track files inside the project directory
        # Skip dunder names like <module>, <listcomp>, etc.
        if (not os.path.realpath(filename).startswith(project_dir)
                or "site-packages" in filename
                or func_name.startswith("<")):
            return trace

        key = f"{Path(filename).name}::{func_name}"

        if event == "call":
            try:
                tracker = EmissionsTracker(
                    log_level="critical",
                    save_to_file=False,
                    save_to_api=False,
                    allow_multiple_runs=True,
                )
                tracker.start()
                call_stack.append((key, tracker))
            except Exception:
                pass

        elif event == "return" and call_stack:
            # Only pop if the top of stack matches this function
            if call_stack[-1][0] == key:
                name, tracker = call_stack.pop()
                try:
                    emissions = tracker.stop()                                 # kg CO₂
                    energy    = tracker.final_emissions_data.energy_consumed   # kWh

                    if name not in function_emissions:
                        function_emissions[name] = {
                            "calls":            0,
                            "total_co2_kg":     0.0,
                            "total_energy_kwh": 0.0,
                        }

                    function_emissions[name]["calls"]            += 1
                    function_emissions[name]["total_co2_kg"]     += emissions or 0.0
                    function_emissions[name]["total_energy_kwh"] += energy    or 0.0
                except Exception:
                    pass

        return trace

    # Execute target file with tracing active
    sys.settrace(trace)
    try:
        target_globals = {
            "__file__": str(target_file),
            "__name__": "__main__",
        }
        with open(target_file, "r", encoding="utf-8") as f:
            code = compile(f.read(), str(target_file), "exec")
        exec(code, target_globals)
    except SystemExit:
        pass
    except Exception as e:
        print(f"\n⚠️  Error while running target for per-function tracking: {e}")
    finally:
        sys.settrace(None)

    # Build sorted results list
    results = []
    for key, data in function_emissions.items():
        file_part, func_part = key.rsplit("::", 1)
        calls = data["calls"]
        if calls == 0:
            continue
        results.append({
            "function":         func_part,
            "file":             file_part,
            "calls":            calls,
            "total_co2_g":      data["total_co2_kg"]     * 1000,
            "avg_co2_g":        data["total_co2_kg"]     * 1000 / calls,
            "total_energy_kwh": data["total_energy_kwh"],
            "avg_energy_kwh":   data["total_energy_kwh"] / calls,
        })

    # Sort by total CO₂ descending
    return sorted(results, key=lambda r: r["total_co2_g"], reverse=True)


def display_per_function_report(functions: list):
    """Pretty-print the per-function carbon breakdown table."""
    if not functions:
        print("\n⚠️  No function-level data collected.")
        print("   Functions may have been too fast to measure.")
        return

    print("\n" + "=" * BREAK_LINE_NO)
    print("🔬 PER-FUNCTION CARBON BREAKDOWN")
    print("=" * BREAK_LINE_NO)
    print(f"  {'#':<4} {'Function':<28} {'File':<25} {'Calls':>6} {'CO₂/call (µg)':>14} {'Total CO₂ (µg)':>15}")
    print(f"  {'-'*4} {'-'*28} {'-'*25} {'-'*6} {'-'*14} {'-'*15}")

    total_co2_g = sum(r["total_co2_g"] for r in functions)

    for rank, row in enumerate(functions, 1):
        func      = row["function"][:27]
        file_name = row["file"][:24]
        calls     = row["calls"]
        co2_call  = row["avg_co2_g"]   * 1e6   # g → µg
        co2_total = row["total_co2_g"] * 1e6   # g → µg
        pct       = (row["total_co2_g"] / total_co2_g * 100) if total_co2_g else 0

        print(f"  {rank:<4} {func:<28} {file_name:<25} {calls:>6} {co2_call:>14.4f} {co2_total:>14.4f}  ({pct:.1f}%)")

    print(f"\n  {'Total tracked CO₂:':<50} {total_co2_g * 1e6:>14.4f} µg")
    print("\n  ℹ️  Parent functions include energy from their children (expected).")
    print("=" * BREAK_LINE_NO)


def carbon_track(path, args, total_loc=0, smell_breakdown=None):
    """
    Track carbon emissions for running the target application.

    Phase 1 — Whole-run tracking (CodeCarbon, 5 iterations):
        Aggregate report, SCI metrics, history.json update.

    Phase 2 — Per-function tracking (CodeCarbon per function, 1 run):
        Per-function breakdown table.
        Skipped if --no-per-function is passed.
    """
    if args.no_carbon:
        return

    if not CODECARBON_AVAILABLE:
        print("⚠️  Warning: codecarbon is not installed. Carbon tracking disabled.")
        print("   Install with: pip install pygreensense\n")
        return

    target_file = _resolve_carbon_target_file(path, args)
    if not target_file:
        return

    # ── Phase 1: whole-run aggregate ──────────────────────────────────────
    print(f"\n🌱 Tracking carbon emissions for: {target_file}")
    print("   Running 5 iterations for average calculations...")
    print("-" * BREAK_LINE_NO)

    try:
        all_runs, result, duration = run_entry_point_with_carbon(
            target_file, iterations=5, timeout=30
        )
    except Exception as e:
        print(f"⚠️  Error during carbon tracking: {e}")
        return

    _print_program_output(result)

    if _process_carbon_runs(target_file, all_runs, result, duration, total_loc, smell_breakdown):
        print("=" * BREAK_LINE_NO)

    # ── Phase 2: per-function breakdown ───────────────────────────────────
    # if not args.no_per_function:
    #     print(f"\n🔬 Running per-function carbon analysis (1 run)...")
    #     print("-" * BREAK_LINE_NO)
    #     functions = run_with_per_function_carbon(target_file)
    #     display_per_function_report(functions)


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
  
  # Specify file to run for carbon tracking
  %(prog)s . --carbon-run main.py
  %(prog)s . --carbon-run src/app.py

  # Disable per-function breakdown (faster)
  %(prog)s . --no-per-function

  # Disable carbon tracking entirely
  %(prog)s . --no-carbon

  # With custom options
  %(prog)s . --max-methods 5
  %(prog)s . --dup-similarity 0.80
  %(prog)s . --method-max-loc 30 --max-cyclomatic 3
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
                        help='Check duplicated code only within functions')
    parser.add_argument('--dup-check-between-only', action='store_true',
                        help='Check duplicated code only between functions')

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

    # Mutable default arguments rule
    parser.add_argument('--no-mutable-default', action='store_true',
                        help='Disable Mutable Default Arguments detection')

    # Carbon tracking
    parser.add_argument('--no-carbon', action='store_true',
                        help='Disable carbon emissions tracking')
    parser.add_argument('--carbon-run', type=str, metavar='FILE',
                        help='Specify Python file to run for carbon tracking (e.g., main.py)')
    parser.add_argument('--no-per-function', action='store_true',
                        help='Disable per-function carbon breakdown (faster)')

    args = parser.parse_args()

    if args.path is None:
        parser.print_help()
        sys.exit(0)

    if args.path == "run":
        args.path = "."

    if args.dup_check_within_only and args.dup_check_between_only:
        print("❌ Error: Cannot use both --dup-check-within-only and --dup-check-between-only")
        sys.exit(1)

    if args.dup_check_within_only:
        args.dup_check_within  = True
        args.dup_check_between = False
    elif args.dup_check_between_only:
        args.dup_check_within  = False
        args.dup_check_between = True
    else:
        args.dup_check_within  = True
        args.dup_check_between = True

    all_result, total_loc = analyze_code_smells(args.path, args)
    smell_breakdown = compute_smell_breakdown(all_result)
    carbon_track(args.path, args, total_loc, smell_breakdown)

    print("\n✨ Analysis complete.\n")


if __name__ == "__main__":
    main()
