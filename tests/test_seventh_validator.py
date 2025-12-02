from seventh_validator import SeventhValidator
from typing import Dict, Any

def test_seventh_validator_pass_and_fail():
    v = SeventhValidator()
    good: Dict[str, Any] = {
        'motivation': 'Improve reliability and transparency via refactoring and better tests',
        'expected_benefits': 'Reliability increase',
        'identified_risks': ['regression', 'edge cases'],
        'admitted_uncertainties': ['long-term maintainability'],
        'rollback_plan': 'Restore previous deployment',
        'confidence_level': 0.6
    }
    out_good = v.validate(good)
    assert out_good.passed is True
    assert out_good.severity == 'info'

    bad: Dict[str, Any] = {
        'motivation': 'Short',
        'expected_benefits': '',
        'identified_risks': [],
        'admitted_uncertainties': [],
        'rollback_plan': '',
        'confidence_level': 1.5
    }
    out_bad = v.validate(bad)
    assert out_bad.passed is False
    assert out_bad.severity in ['warning', 'critical']
