# Finance formulas

> The 20 core valuation, profitability, liquidity and risk formulas: which run per filing period over XBRL facts as derived metrics, which are pure helpers, and what data each needs.

**Source and credit.** The formulas and their one-line definitions are transcribed from the image "The Ultimate Finance Cheat Sheet — Formulas & Definitions" (watermarked *Saksham Goel*), shared by Compounding Dividends ([@CompoundingW](https://x.com/CompoundingW)) on X on 2026-10-26: <https://x.com/CompoundingW/status/2114932373280460836>. Implementation: requirement **FR-ANL-001** in [`PRD.md`](../PRD.md) §4.6, feature **FREDGAR-009** in [`features/features.yml`](../features/features.yml).

## Where they live

- **Pure functions** — [`src/warehouse/services/finance_formulas.py`](../src/warehouse/services/finance_formulas.py), one function per formula, `Decimal` in and out, `None` instead of an exception on a zero denominator. Rates are decimals (`0.08` = 8%). Tests: [`tests/warehouse/test_finance_formulas.py`](../tests/warehouse/test_finance_formulas.py).
- **Per-period derived metrics** — eight of the formulas are also declared in `derived_kpis` in [`data/reference/financial_model.json`](../data/reference/financial_model.json), so `compute_derived_metrics` (and `manage.py sync_derived_metrics`, and the derived-metrics API) writes them as `DerivedMetric` rows from a company's XBRL `Fact`s. Tests: [`tests/warehouse/test_metrics.py`](../tests/warehouse/test_metrics.py).

## The formulas

| # | Metric | Formula | Function | Derived KPI key | Data available in the warehouse? |
| --- | --- | --- | --- | --- | --- |
| 1 | Present Value (PV) | PV = FV / (1 + r)^n | `present_value` | — | No: caller supplies FV, r, n |
| 2 | Future Value (FV) | FV = PV × (1 + r)^n | `future_value` | — | No: caller supplies inputs |
| 3 | Net Present Value (NPV) | NPV = Σ_{t=0}^{n} CF_t / (1 + r)^t | `net_present_value` | — | No: needs projected cash flows and a discount rate |
| 4 | Weighted Average Cost of Capital (WACC) | WACC = (E/V)·Re + (D/V)·Rd·(1 − Tc) | `wacc` | — | Partly: D and Tc from facts; E needs market cap, Re needs CAPM, Rd needs a debt yield |
| 5 | Capital Asset Pricing Model (CAPM) | Re = Rf + β(Rm − Rf) | `capm_expected_return` | — | Partly: Rf could come from a FRED Treasury series (e.g. `DGS10`); β and Rm need price history |
| 6 | Earnings Per Share (EPS) | EPS = Net Income / Shares Outstanding | `earnings_per_share` | `eps_basic_computed` | Yes: `NetIncomeLoss` / `WeightedAverageNumberOfSharesOutstandingBasic` |
| 7 | Price-to-Earnings (P/E) | P/E = Market Price / EPS | `price_to_earnings` | — | No: needs a share price |
| 8 | Debt-to-Equity (D/E) | D/E = Total Debt / Shareholders' Equity | `debt_to_equity` | `debt_to_equity` | Yes (approximate total debt, see below) |
| 9 | Return on Equity (ROE) | ROE = Net Income / Shareholders' Equity | `return_on_equity` | `return_on_equity` | Yes |
| 10 | Return on Assets (ROA) | ROA = Net Income / Total Assets | `return_on_assets` | `return_on_assets` | Yes |
| 11 | Return on Investment (ROI) | ROI = (Gain from Investment − Cost) / Cost | `return_on_investment` | — | No: investment-level inputs |
| 12 | Current Ratio | Current Assets / Current Liabilities | `current_ratio` | `current_ratio` | Yes |
| 13 | Quick Ratio (Acid-Test) | (Current Assets − Inventory) / Current Liabilities | `quick_ratio` | `quick_ratio` | Yes (skipped when no inventory fact) |
| 14 | EBITDA | Net Income + Interest + Taxes + Depreciation + Amortization | `ebitda` | `ebitda` | Yes: D&A is one combined XBRL tag |
| 15 | Payback Period | Initial Investment / Annual Cash Inflow | `payback_period` | — | No: project-level inputs |
| 16 | Dividend Yield | Annual Dividend per Share / Market Price per Share | `dividend_yield` | — | Partly: dividends per share are in facts; price is not |
| 17 | Enterprise Value (EV) | Market Cap + Total Debt + Preferred Stock − Cash & Equivalents | `enterprise_value` | — | Partly: debt, preferred and cash from facts; market cap needs a price |
| 18 | Interest Coverage Ratio | EBIT / Interest Expense | `interest_coverage` | `interest_coverage` | Yes: `OperatingIncomeLoss` as the EBIT proxy |
| 19 | Sharpe Ratio | (Rp − Rf) / σp | `sharpe_ratio` | — | No: needs a return series |
| 20 | Beta (β) | Cov(Ri, Rm) / Var(Rm) | `beta` | — | No: needs asset and market return series |

## Definitions (from the source)

1. **PV** — the current worth of a future cash flow discounted at a required rate of return.
2. **FV** — how much an investment today will grow to in the future after compounding.
3. **NPV** — the value created by an investment by comparing discounted cash inflows with cash outflows.
4. **WACC** — the average cost of capital from equity and debt, used as the discount rate in valuation.
5. **CAPM** — the expected return required by investors based on a stock's market risk (beta).
6. **EPS** — how much profit the company earns for each outstanding share of common stock.
7. **P/E** — how much investors are willing to pay for each rupee of the company's earnings (sic: the source says "rupee").
8. **D/E** — financial leverage, comparing total debt to shareholders' equity.
9. **ROE** — how efficiently the company generates profit from the shareholders' investments.
10. **ROA** — how effectively the company uses its assets to generate profits.
11. **ROI** — the return earned on an investment relative to the amount invested.
12. **Current Ratio** — the company's ability to meet short-term obligations using its current assets.
13. **Quick Ratio** — a stricter liquidity measure that excludes inventory from current assets.
14. **EBITDA** — operating profit from core operations before accounting and financing items.
15. **Payback Period** — the time required to recover the initial investment from cash inflows.
16. **Dividend Yield** — annual dividend income as a percentage of the stock price.
17. **EV** — the total value of the business, including debt and preferred stock, minus cash and equivalents.
18. **Interest Coverage** — how comfortably the company can pay interest on its outstanding debt.
19. **Sharpe Ratio** — risk-adjusted return, comparing excess return (over the risk-free rate) to total risk (volatility).
20. **Beta** — a stock's sensitivity to overall market movements (systematic risk).

## Caveats of the per-period metrics

- Balance-sheet denominators (equity, assets) are period-end instants, not period averages, and are paired with the duration fact (net income) that ends on the same date.
- `total_debt` prefers `DebtLongtermAndShorttermCombinedAmount`, then `LongTermDebt` (which includes current maturities), then `LongTermDebtNoncurrent`; filers that tag commercial paper or other short-term borrowings separately will show an understated D/E.
- `eps_basic_computed` is computed, not the filer's reported `EarningsPerShareBasic`; it is USD per share although the `unit` column reads `ratio` (every `/` formula does).
- Market-price inputs (P/E, dividend yield, EV, WACC equity weight, β, Sharpe) are out of scope until the warehouse stores prices (PRD §4.3, "Third-party enrichments (prices, news)").
