# Profitability Optimization — Global Superstore

> **Where is the profit leaking, and what should management change?**
> An end-to-end Python analysis of 51K order lines across 147 countries (2011–2014).

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![pandas](https://img.shields.io/badge/pandas-2.x-150458) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Business Problem

The company has achieved strong revenue growth, but profitability is uneven across products, markets, customers and
discount levels. Management needs to identify the major sources of profit leakage and determine which combinations of
pricing, products, customers, regions and shipping methods add to or reduce overall profitability.

## Executive Summary

| KPI | Value |
|---|---|
| Sales | **$12.64M** |
| Profit | **$1.47M** (11.6% margin) |
| Profit earned by profitable lines | $2.39M |
| Profit destroyed by loss-making lines | **–$0.92M (39%)** |
| Order lines discounted beyond break-even | **22%**, and 90% of them lose money |
| Profit upside from discount guardrails | **+$0.77M to +$1.05M (+53% to +72%)** |

**Root cause:** Profit leakage is driven by **discounting beyond each product's break-even point**. Discount depth
explains the loss-making sub-category, the weak regions, the loss-making countries and the loss-making customers.
Shipping and product mix are secondary.

---

## Key Findings

### 1. Growth is not creating operating leverage
Sales grew ~90% from 2011 to 2014, but margin stayed at 11–12%.

![Yearly trend](reports/figures/01_yearly_trend.png)

### 2. Loss-making lines erase 39% of the profit earned
88% of the leakage comes from lines discounted above 30%.

![Profit bridge](reports/figures/02_profit_bridge.png)

### 3. Discounts above 20% destroy margin and do not buy volume
Units per order line stay flat at ~3.4–3.8 whatever the discount.

![Discount bands](reports/figures/03_discount_band_margin_volume.png)

### 4. The break-even discount rule
If full-price margin is *m₀*, margin at discount *d* is `1 − (1 − m₀)/(1 − d)`, which reaches zero at **d = m₀**.
Each sub-category therefore has a hard discount ceiling of about 21–32%. Tables sells 44% of its revenue beyond that ceiling.

![Break-even discount](reports/figures/04_breakeven_discount_by_subcategory.png)

### 5. Tables is a discount problem, not a cost problem
Tables earns 23% at full price but –8.5% overall. It loses money in APAC, EU, US and LATAM.

![Sub-category matrix](reports/figures/05_subcategory_sales_vs_margin.png)
![Heatmap](reports/figures/07_margin_heatmap_subcategory_market.png)

### 6. Regional margin mirrors discount depth
- Southeast Asia averages a 27% discount and earns a 2.0% margin.
- North Asia averages 5% and earns 19.5%.
- Turkey (flat 60%) and Nigeria (flat 70%) apply the same discount to every line and lose ~$180K combined.

![Regions](reports/figures/06_region_margin_vs_discount.png)
![Countries](reports/figures/08_top_loss_countries.png)

### 7. 22% of customer accounts are loss-making
Loss-making accounts get a 30% average discount, compared with 9% for high-profit accounts. They are repeat buyers
averaging 4.9 orders, so repricing is the fix, not churn.

![Whale curve](reports/figures/09_customer_whale_curve.png)
![Customer tiers](reports/figures/10_customer_tiers.png)

### 8. 1,432 high-selling products lose $474K
These products have real demand, so repricing should come before delisting.

![Portfolio](reports/figures/11_product_portfolio.png)

### 9. Shipping is a secondary lever
- Expedited modes cost 17% of sales, against 8% for Standard Class.
- About 10% of Medium- and Low-priority lines still ship express, which is roughly $25K of avoidable cost.
- Shipping cost is similar across markets, so it does not explain the regional margin gaps.

![Shipping](reports/figures/12_shipping_cost.png)

### 10. Seasonality
June and August–December carry ~66% of sales with no margin gain. Guardrails matter most during peak promotions.

![Seasonality](reports/figures/13_seasonality.png)

### 11. What-if: discount guardrails
Affected lines are re-priced from list price with unit cost held constant. Results are stress-tested for 0–100% loss
of the affected volume.

![Scenarios](reports/figures/14_discount_cap_scenarios.png)

---

## Recommendations

| # | Action | Evidence | Impact |
|---|---|---|---|
| 1 | Sub-category discount guardrails (break-even – 5pp) with an approval workflow for exceptions | 22% of lines above break-even, –$813K | **+$0.77M to +$1.05M** |
| 2 | Audit the flat country price lists in Turkey and Nigeria, then Netherlands, Honduras and Pakistan | ~$180K lost in two countries | Removes the largest country losses |
| 3 | Remove Tables from deep promotions and cap its discount at ~18% | 23% full-price margin vs –8.5% realised | Turns –$64K into profit |
| 4 | Reprice the 1,432 high-sales, loss-making products before any delisting | $3.0M sales, –$474K | Protects revenue |
| 5 | Move loss-making customer accounts to standard price lists | 30% vs 9% average discount | Recovers part of –$375K |
| 6 | Default Medium- and Low-priority orders to Standard Class | 3,048 mismatched lines | ~$25K saving |
| 7 | Add margin and discount-depth KPIs to sales and regional scorecards | Flat margin despite +90% sales | Stops growth being bought with margin |

---

## Data Cleaning

The full log is in [`reports/tables/cleaning_log.csv`](reports/tables/cleaning_log.csv).

- Dropped the constant column `记录数` (record count).
- Renamed columns to snake_case and parsed dates.
- Validated nulls, duplicates, ship date against order date, discount range and year consistency. All passed.
- Removed one zero-sales line, because its margin is undefined.
- Rounded LATAM discount artefacts (0.002, 0.202, 0.402, 0.602) to the standard tiers.
- Keyed products on ID + name, because 457 product IDs map to more than one name.
- Treated `customer_id` as market-specific (4,873 IDs vs 795 names), so a customer is analysed as a customer account per market.
- Engineered margin, discount band, list price, discount amount, shipping %, ship days and loss flags.

## Project Structure

```
├── data/
│   ├── raw/superstore.csv            # source data
│   └── processed/                    # generated clean file (git-ignored)
├── notebooks/
│   └── profitability_analysis.ipynb  # full narrative analysis (executed)
├── reports/
│   ├── figures/                      # 14 charts (PNG)
│   └── tables/                       # 20+ summary tables (CSV)
├── src/
│   ├── config.py                     # paths, bands, colours
│   ├── data_cleaning.py              # audit, cleaning, feature engineering
│   ├── analysis.py                   # all analytical functions
│   └── visuals.py                    # chart functions
├── run_analysis.py                   # one-command pipeline
├── requirements.txt
└── README.md
```

## How to Run

```bash
git clone https://github.com/<your-username>/profitability-optimization.git
cd profitability-optimization
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run_analysis.py                 # rebuilds clean data, tables and figures
jupyter notebook notebooks/profitability_analysis.ipynb
```

## Assumptions & Limitations

- Unit cost is inferred as `sales − profit` and held constant in the scenarios.
- There is no price-elasticity or competitor data, so the scenarios bracket outcomes with volume-loss assumptions rather than predicting them.
- The dataset does not document whether `Profit` is net of `Shipping.Cost`. Shipping is therefore analysed as a separate cost-to-serve KPI.
- Sales values in the source are rounded to whole currency units.

## Tools

Python · pandas · NumPy · Matplotlib · Seaborn · Jupyter
