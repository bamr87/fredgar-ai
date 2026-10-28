"""The 20 core finance formulas, as pure ``Decimal`` functions.

Transcribed from the "Ultimate Finance Cheat Sheet — Formulas & Definitions" image
(credited to Saksham Goel) shared by @CompoundingW on X:
https://x.com/CompoundingW/status/2114932373280460836 . See ``docs/finance-formulas.md``.

Every function is pure (no DB, no network) and returns ``None`` instead of raising on
a zero denominator, so callers can treat "not computable" uniformly. Rates are
decimals (``0.08`` means 8%). Eight of these also run per filing period over XBRL
facts as ``DerivedMetric`` rows (see ``derived_kpis`` in
``data/reference/financial_model.json``); the rest need market prices, cash-flow
projections or return series that the warehouse does not store, so they are exposed
here for callers that bring their own inputs.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

Number = Decimal | int | float | str


def _d(x: Number) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def _div(num: Number, den: Number) -> Decimal | None:
    d = _d(den)
    if d == 0:
        return None
    return _d(num) / d


# --- Valuation -----------------------------------------------------------------


def present_value(future_value: Number, rate: Number, periods: int) -> Decimal | None:
    """1. PV = FV / (1 + r)^n."""
    return _div(future_value, (1 + _d(rate)) ** periods)


def future_value(present: Number, rate: Number, periods: int) -> Decimal:
    """2. FV = PV × (1 + r)^n."""
    return _d(present) * (1 + _d(rate)) ** periods


def net_present_value(rate: Number, cash_flows: Sequence[Number]) -> Decimal | None:
    """3. NPV = Σ_{t=0}^{n} CF_t / (1 + r)^t.

    ``cash_flows[0]`` is t=0 (usually the negative initial outlay, undiscounted).
    """
    total = Decimal(0)
    base = 1 + _d(rate)
    if base == 0:
        return None
    for t, cf in enumerate(cash_flows):
        total += _d(cf) / base**t
    return total


def wacc(
    equity_value: Number,
    debt_value: Number,
    cost_of_equity: Number,
    cost_of_debt: Number,
    tax_rate: Number,
) -> Decimal | None:
    """4. WACC = (E/V)·Re + (D/V)·Rd·(1 − Tc), with V = E + D."""
    e, d = _d(equity_value), _d(debt_value)
    v = e + d
    if v == 0:
        return None
    return (e / v) * _d(cost_of_equity) + (d / v) * _d(cost_of_debt) * (1 - _d(tax_rate))


def capm_expected_return(risk_free: Number, beta_value: Number, market_return: Number) -> Decimal:
    """5. Re = Rf + β(Rm − Rf)."""
    rf = _d(risk_free)
    return rf + _d(beta_value) * (_d(market_return) - rf)


# --- Profitability / per-share ---------------------------------------------------


def earnings_per_share(net_income: Number, shares_outstanding: Number) -> Decimal | None:
    """6. EPS = Net Income / Shares Outstanding."""
    return _div(net_income, shares_outstanding)


def price_to_earnings(market_price: Number, eps: Number) -> Decimal | None:
    """7. P/E = Market Price / EPS."""
    return _div(market_price, eps)


def debt_to_equity(total_debt: Number, shareholders_equity: Number) -> Decimal | None:
    """8. D/E = Total Debt / Shareholders' Equity."""
    return _div(total_debt, shareholders_equity)


def return_on_equity(net_income: Number, shareholders_equity: Number) -> Decimal | None:
    """9. ROE = Net Income / Shareholders' Equity."""
    return _div(net_income, shareholders_equity)


def return_on_assets(net_income: Number, total_assets: Number) -> Decimal | None:
    """10. ROA = Net Income / Total Assets."""
    return _div(net_income, total_assets)


def return_on_investment(gain_from_investment: Number, cost: Number) -> Decimal | None:
    """11. ROI = (Gain from Investment − Cost) / Cost."""
    return _div(_d(gain_from_investment) - _d(cost), cost)


# --- Financial health ------------------------------------------------------------


def current_ratio(current_assets: Number, current_liabilities: Number) -> Decimal | None:
    """12. Current Ratio = Current Assets / Current Liabilities."""
    return _div(current_assets, current_liabilities)


def quick_ratio(
    current_assets: Number, inventory: Number, current_liabilities: Number
) -> Decimal | None:
    """13. Quick Ratio = (Current Assets − Inventory) / Current Liabilities."""
    return _div(_d(current_assets) - _d(inventory), current_liabilities)


def ebitda(
    net_income: Number,
    interest: Number,
    taxes: Number,
    depreciation: Number,
    amortization: Number = 0,
) -> Decimal:
    """14. EBITDA = Net Income + Interest + Taxes + Depreciation + Amortization."""
    return _d(net_income) + _d(interest) + _d(taxes) + _d(depreciation) + _d(amortization)


def payback_period(initial_investment: Number, annual_cash_inflow: Number) -> Decimal | None:
    """15. Payback Period = Initial Investment / Annual Cash Inflow (in years)."""
    return _div(initial_investment, annual_cash_inflow)


def dividend_yield(annual_dividend_per_share: Number, price_per_share: Number) -> Decimal | None:
    """16. Dividend Yield = Annual Dividend per Share / Market Price per Share."""
    return _div(annual_dividend_per_share, price_per_share)


def enterprise_value(
    market_cap: Number,
    total_debt: Number,
    preferred_stock: Number,
    cash_and_equivalents: Number,
) -> Decimal:
    """17. EV = Market Cap + Total Debt + Preferred Stock − Cash & Equivalents."""
    return _d(market_cap) + _d(total_debt) + _d(preferred_stock) - _d(cash_and_equivalents)


def interest_coverage(ebit: Number, interest_expense: Number) -> Decimal | None:
    """18. Interest Coverage = EBIT / Interest Expense."""
    return _div(ebit, interest_expense)


def sharpe_ratio(portfolio_return: Number, risk_free: Number, std_dev: Number) -> Decimal | None:
    """19. Sharpe Ratio = (Rp − Rf) / σp."""
    return _div(_d(portfolio_return) - _d(risk_free), std_dev)


def beta(asset_returns: Sequence[Number], market_returns: Sequence[Number]) -> Decimal | None:
    """20. β = Cov(Ri, Rm) / Var(Rm).

    Sample covariance and variance (n − 1); the divisor cancels, so population
    statistics give the same β. Needs two equal-length series of at least 2 points.
    """
    if len(asset_returns) != len(market_returns) or len(market_returns) < 2:
        return None
    ri = [_d(x) for x in asset_returns]
    rm = [_d(x) for x in market_returns]
    n = Decimal(len(rm))
    zero = Decimal(0)
    mi, mm = sum(ri, zero) / n, sum(rm, zero) / n
    cov = sum(((a - mi) * (b - mm) for a, b in zip(ri, rm, strict=True)), zero) / (n - 1)
    var = sum(((b - mm) ** 2 for b in rm), zero) / (n - 1)
    return _div(cov, var)
