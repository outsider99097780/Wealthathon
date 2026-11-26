# Competition Constraints

## 1. Rule Source

- Source: AmplifyME Asset Management Training Simulation
- Version: 1.0
- Status: Provisional
- Official competition rules override the current training rules.

## 2. Investment Mandate

- Strategy: Global Macro, Multi-Asset, Long Only.
- Client Profile: Balanced portfolio combining capital appreciation and fixed income.
- Initial Capital: USD 20,000,000.
- Investment Horizon: 12 simulated months.
- Number of Quarters: 4.
- Duration per Quarter: 15 minutes.

## 3. Hard Constraints

| Parameter | Value |
|---|---|
| Minimum Investment Ratio at Quarter Start | 0.90 |
| Maximum Exposure per Financial Product | USD 5,000,000 |
| Maximum Loss per Trade | USD 500,000 |
| Maximum Benchmark Weight Deviation | 0.10 |
| Short Selling | Not Allowed |
| Leverage | Not Specified |
| Transaction Costs | Not Specified |

### Implementation Rules

- All financial product positions must be non-negative.
- At least 90% of current portfolio NAV must be invested at the beginning of each quarter.
- Exposure to any individual financial product must not exceed USD 5,000,000.
- Maximum loss per trade must not exceed USD 500,000.
- Portfolio weights must comply with benchmark deviation limits.
- Benchmark weights shall be retrieved from `data/benchmark.csv`.

### Provisional Interpretations

- Interpret benchmark deviation as an absolute deviation of 10 percentage points until confirmed.
- Confirm whether benchmark deviation applies to individual products or asset classes.
- Confirm the platform's exact stop-loss calculation method.
- Assume no leverage for training calculations unless otherwise specified.
- Do not treat unspecified transaction costs as confirmed zero costs.

## 4. Performance Objectives

### ROI — Return on Investment

- Maximize portfolio return.
- Identify market trends.
- Evaluate the impact of breaking macroeconomic news.
- Generate returns above the fixed benchmark.

### PR — Portfolio Rebalancing

- Monitor changes in portfolio weights caused by price movements.
- Recalculate current portfolio NAV and positions.
- Rebalance the portfolio in response to market developments and investment constraints.

### RM — Risk Management

- Remain within stop-loss limits.
- Improve the portfolio Sharpe Ratio.
- Maintain appropriate diversification.
- Monitor individual and aggregate risk exposures.

### RA — Risk Appetite

- Maintain appropriate investment exposure.
- Express conviction in investment decisions through position sizing.
- Balance risk-taking with the client's balanced investment mandate.

## 5. Evaluation Framework

- Performance is evaluated relative to the underlying fixed benchmark.
- Evaluation dimensions: ROI, PR, RM and RA.
- Exact scoring weights: Not Specified.
- Do not assume equal scoring weights without justification.

## 6. Constraint Validation

Before generating any portfolio recommendation:

1. Read the latest competition constraints.
2. Calculate current portfolio NAV and positions.
3. Validate the minimum investment ratio when applicable.
4. Validate individual product exposure.
5. Validate benchmark weight deviations.
6. Check stop-loss compliance and projected loss exposure.
7. Confirm compliance with the long-only mandate.
8. Report any violations or unresolved rules.

Do not present a portfolio that violates confirmed constraints as compliant.

## 7. Rule Updates

- All skills and workflows must reference this file.
- Competition-specific parameters must not be hard-coded elsewhere.
- Update this file only with explicit user authorization.
- Record the constraint version in each quarterly result.
