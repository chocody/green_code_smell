import ast
from pathlib import Path

from green_code_smell.core import analyze_file, analyze_project
from green_code_smell.rules.dead_code import DeadCodeRule
from green_code_smell.rules.duplicated_code import DuplicatedCodeRule
from green_code_smell.rules.god_class import GodClassRule
from green_code_smell.rules.long_method import LongMethodRule
from green_code_smell.rules.mutable_default_arguments import MutableDefaultArgumentsRule


def _parse(code: str):
    return ast.parse(code)


def test_long_method_and_mutable_default_detect_issues():
    code = """
def f(a=[]):
    if a:
        return len(a)
    for _ in range(2):
        pass
    while False:
        break
    return 1
"""
    tree = _parse(code)
    long_rule = LongMethodRule(max_loc=3, max_cc=2)
    mutable_rule = MutableDefaultArgumentsRule()
    assert long_rule.check(tree)
    assert mutable_rule.check(tree)


def test_god_class_detects_class_with_many_methods():
    methods = "\n".join([f"    def m{i}(self):\n        return {i}" for i in range(5)])
    code = f"class Big:\n{methods}\n"
    issues = GodClassRule(max_methods=3, max_cc=100, max_loc=200).check(_parse(code))
    assert len(issues) == 1
    assert "God Class" in issues[0]["message"]


def test_duplicated_code_detects_similar_functions():
    code = """
def a(x):
    y = x + 1
    z = y * 2
    return z

def b(v):
    t = v + 1
    r = t * 2
    return r
"""
    rule = DuplicatedCodeRule(similarity_threshold=0.8, min_statements=3)
    issues = rule.check(_parse(code))
    assert issues
    assert issues[0]["rule"] == "DuplicatedCode"


def test_dead_code_single_file_detects_unreachable_and_unused():
    code = """
def used():
    return 1

def dead():
    return 2
    x = 9

value = used()
"""
    issues = DeadCodeRule().check(_parse(code))
    messages = [i["message"] for i in issues]
    assert any("Unreachable code" in m for m in messages)
    assert any("Unused function 'dead'" in m for m in messages)


def test_analyze_file_sets_dead_code_single_file_attributes(tmp_path: Path):
    target = tmp_path / "mod.py"
    target.write_text("def run():\n    return 1\n", encoding="utf-8")
    rule = DeadCodeRule()
    results = analyze_file(str(target), [rule])
    assert isinstance(results, list)
    assert rule.single_file_mode is True
    assert rule.target_file == str(target.resolve())
    assert rule.project_root == str(target.parent)


def test_analyze_file_non_deadcode_path(tmp_path: Path):
    target = tmp_path / "m.py"
    target.write_text("def p(a=[]):\n    return a\n", encoding="utf-8")
    results = analyze_file(str(target), [MutableDefaultArgumentsRule()])
    assert results and results[0]["rule"] == "MutableDefaultArguments"


def test_analyze_project_collects_issues_for_non_deadcode(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("def x(a=[]):\n    return a\n", encoding="utf-8")
    (pkg / "b.py").write_text("def y():\n    return 1\n", encoding="utf-8")
    issues = analyze_project(pkg, [MutableDefaultArgumentsRule()])
    assert issues
    assert all("file" in issue for issue in issues)


def test_analyze_project_deadcode_branch(tmp_path: Path):
    pkg = tmp_path / "dead"
    pkg.mkdir()
    (pkg / "ok.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    issues = analyze_project(pkg, [DeadCodeRule()])
    assert isinstance(issues, list)


def test_dead_code_check_project_detects_cross_file_usage_and_unreachable(tmp_path: Path):
    pkg = tmp_path / "proj"
    pkg.mkdir()
    (pkg / "a.py").write_text(
        "def exported():\n    return 1\n\n"
        "def unused():\n    return 2\n\n"
        "def f():\n    return 1\n    z = 2\n",
        encoding="utf-8",
    )
    (pkg / "b.py").write_text("from a import exported\nx = exported()\n", encoding="utf-8")
    rule = DeadCodeRule(project_root=str(pkg))
    issues = rule.check_project()
    msgs = [i["message"] for i in issues]
    assert any("Unused function 'unused'" in m for m in msgs)
    assert any("Unreachable code" in m for m in msgs)
    assert not any("Unused function 'exported'" in m for m in msgs)


def test_duplicated_code_within_function_and_class_level():
    code = """
class A:
    x = 1
    y = 2
    z = 3

class B:
    x = 1
    y = 2
    z = 3

def same():
    a = 1
    b = 2
    c = a + b
    a = 1
    b = 2
    c = a + b
    return c
"""
    rule = DuplicatedCodeRule(
        similarity_threshold=0.8,
        min_statements=3,
        check_within_functions=True,
        check_between_functions=True,
    )
    issues = rule.check(_parse(code))
    assert issues
    assert any("class-level code" in i["message"] or "Duplicated code block" in i["message"] for i in issues)
