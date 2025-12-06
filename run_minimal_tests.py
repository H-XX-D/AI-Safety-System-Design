import sys
import os
import unittest

# Add root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import tests
from tests import test_log_schema

def run_tests():
    print("Running minimal tests...")
    try:
        test_log_schema.test_validate_log_event_success()
        print("test_validate_log_event_success: PASS")
    except Exception as e:
        print(f"test_validate_log_event_success: FAIL ({e})")

    try:
        test_log_schema.test_validate_log_event_missing_field()
        print("test_validate_log_event_missing_field: PASS")
    except Exception as e:
        print(f"test_validate_log_event_missing_field: FAIL ({e})")

    # Add more tests if possible
    
if __name__ == "__main__":
    run_tests()
