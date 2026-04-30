import green_code_smell
import pygreensense


def test_public_api_exports_analysis_helpers_and_rules():
    assert pygreensense.analyze_file is green_code_smell.analyze_file
    assert pygreensense.analyze_project is green_code_smell.analyze_project
    assert pygreensense.GodClassRule is green_code_smell.GodClassRule
    assert pygreensense.MutableDefaultArgumentsRule is green_code_smell.MutableDefaultArgumentsRule
    assert isinstance(pygreensense.__version__, str)
