"""jobs.labor_cost and tenants.default_tax_rate were left as plain Float when
they were created, before this project's Float(precision=53) convention for
money/quantity columns existed. Plain Float is a 4-byte MySQL FLOAT (~7
significant digits) and silently rounds large LKR amounts on MySQL; SQLite's
REAL is 8-byte regardless, so asking the SQLite test database can't tell the
two apart — this checks the declared column type directly instead, which
catches a regression on any engine.

labor_cost is the urgent one: the mobile job detail screen's labour-charge
editor writes real amounts to it today, live, independent of invoicing.
"""

from app.models.job import Job
from app.models.tenant import Tenant


def test_labor_cost_is_double_precision():
    column = Job.__table__.columns["labor_cost"]
    assert column.type.precision == 53, (
        "jobs.labor_cost must be Float(precision=53) — plain Float silently "
        "rounds large LKR amounts on MySQL, and the mobile app writes to "
        "this column live."
    )


def test_default_tax_rate_is_double_precision():
    column = Tenant.__table__.columns["default_tax_rate"]
    assert column.type.precision == 53
