"""The 20 cheat-sheet finance formulas (docs/finance-formulas.md), hand-checked values."""

from __future__ import annotations

from decimal import Decimal

import pytest

from warehouse.services import finance_formulas as ff

Q = Decimal("0.000001")


def q(x: Decimal | None) -> Decimal:
    assert x is not None
    return x.quantize(Q)


def test_present_value():
    # 1000 / 1.1^2 = 1000 / 1.21 = 826.446281
    assert q(ff.present_value(1000, "0.10", 2)) == Decimal("826.446281")


def test_future_value():
    # 1000 * 1.05^2 = 1102.5
    assert ff.future_value(1000, "0.05", 2) == Decimal("1102.5")


def test_net_present_value():
    # -1000 + 500/1.1 + 600/1.21 = -1000 + 454.545455 + 495.867769 = -49.586777
    assert q(ff.net_present_value("0.10", [-1000, 500, 600])) == Decimal("-49.586777")


def test_wacc():
    # E=600, D=400 -> V=1000; 0.6*0.10 + 0.4*0.05*(1-0.25) = 0.06 + 0.015 = 0.075
    assert ff.wacc(600, 400, "0.10", "0.05", "0.25") == Decimal("0.075")
    assert ff.wacc(0, 0, "0.1", "0.05", "0.2") is None


def test_capm():
    # 0.03 + 1.2 * (0.08 - 0.03) = 0.09
    assert ff.capm_expected_return("0.03", "1.2", "0.08") == Decimal("0.090")


@pytest.mark.parametrize(
    ("fn", "args", "expected"),
    [
        (ff.earnings_per_share, (1000, 250), "4"),
        (ff.price_to_earnings, (40, 4), "10"),
        (ff.debt_to_equity, (500, 1000), "0.5"),
        (ff.return_on_equity, (150, 1000), "0.15"),
        (ff.return_on_assets, (150, 3000), "0.05"),
        (ff.return_on_investment, (1200, 1000), "0.2"),
        (ff.current_ratio, (300, 150), "2"),
        (ff.quick_ratio, (300, 60, 150), "1.6"),
        (ff.payback_period, (10000, 2500), "4"),
        (ff.dividend_yield, (2, 50), "0.04"),
        (ff.interest_coverage, (500, 50), "10"),
        (ff.sharpe_ratio, ("0.12", "0.02", "0.2"), "0.5"),
    ],
)
def test_ratios(fn, args, expected):
    assert fn(*args) == Decimal(expected)


@pytest.mark.parametrize(
    ("fn", "args"),
    [
        (ff.present_value, (100, -1, 1)),
        (ff.earnings_per_share, (1, 0)),
        (ff.price_to_earnings, (40, 0)),
        (ff.debt_to_equity, (1, 0)),
        (ff.return_on_equity, (1, 0)),
        (ff.return_on_assets, (1, 0)),
        (ff.return_on_investment, (1, 0)),
        (ff.current_ratio, (1, 0)),
        (ff.quick_ratio, (1, 0, 0)),
        (ff.payback_period, (1, 0)),
        (ff.dividend_yield, (1, 0)),
        (ff.interest_coverage, (1, 0)),
        (ff.sharpe_ratio, (1, 0, 0)),
    ],
)
def test_zero_denominator_is_none(fn, args):
    assert fn(*args) is None


def test_ebitda():
    # 100 + 20 + 30 + 40 + 10 = 200
    assert ff.ebitda(100, 20, 30, 40, 10) == Decimal("200")


def test_enterprise_value():
    # 1000 + 300 + 50 - 100 = 1250
    assert ff.enterprise_value(1000, 300, 50, 100) == Decimal("1250")


def test_beta():
    # Ri = 2 * Rm exactly -> Cov(Ri, Rm) = 2 Var(Rm) -> beta = 2
    assert ff.beta(["0.02", "0.04", "0.06"], ["0.01", "0.02", "0.03"]) == Decimal("2")
    assert ff.beta([1], [1]) is None
    assert ff.beta([1, 2], [1, 2, 3]) is None
    assert ff.beta([1, 2], [5, 5]) is None  # zero market variance
