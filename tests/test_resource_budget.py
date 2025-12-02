import time
import pytest
from resource_guard import ResourceBudget, BudgetExceeded


def test_resource_budget_pass():
    with ResourceBudget(50):  # generous budget
        time.sleep(0.01)


def test_resource_budget_fail():
    with pytest.raises(BudgetExceeded):
        with ResourceBudget(1):  # 1 ms
            time.sleep(0.01)
