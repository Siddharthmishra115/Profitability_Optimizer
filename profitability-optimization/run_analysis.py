"""
End-to-end pipeline: clean -> analyse -> export tables -> export figures.

Usage:
    python run_analysis.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src import analysis as A  # noqa: E402
from src import visuals as V  # noqa: E402
from src.config import TABLE_DIR  # noqa: E402
from src.data_cleaning import run as clean_data  # noqa: E402


def main():
    print("1/4  Cleaning data ...")
    df = clean_data(save=True)

    print("2/4  Running analysis ...")
    kpis = A.kpi_summary(df)
    company_margin = kpis["profit_margin"]
    yearly = A.yearly_trend(df)
    bridge = A.profit_bridge(df)
    bands = A.discount_band_summary(df)
    breakeven = A.breakeven_discount(df)
    scenarios = A.discount_cap_scenarios(df)
    categories = A.category_summary(df)
    subcats = A.subcategory_summary(df)
    markets = A.market_summary(df)
    regions = A.region_summary(df)
    countries = A.country_losses(df)
    states = A.us_state_losses(df)
    hotspots = A.leakage_hotspots(df)
    matrix = A.margin_matrix(df)
    customers = A.customer_profitability(df)
    tiers = A.customer_tier_summary(customers)
    whale = A.whale_curve(customers)
    portfolio = A.product_portfolio(df)
    portfolio_sum = A.portfolio_summary(portfolio)
    shipping = A.shipping_summary(df)
    mix = A.priority_mode_mix(df)
    mismatch = A.expedited_mismatch(df)
    seasonality = A.monthly_seasonality(df)

    print("3/4  Exporting tables ...")
    tables = {
        "kpi_summary": kpis.to_frame("value"),
        "yearly_trend": yearly,
        "profit_bridge": bridge,
        "discount_band_summary": bands,
        "breakeven_discount_by_subcategory": breakeven,
        "discount_cap_scenarios": scenarios,
        "category_summary": categories,
        "subcategory_summary": subcats,
        "market_summary": markets,
        "region_summary": regions,
        "loss_making_countries": countries,
        "loss_making_us_states": states,
        "leakage_hotspots_market_segment_subcat": hotspots,
        "customer_tier_summary": tiers,
        "customer_profitability": customers,
        "product_portfolio_summary": portfolio_sum,
        "product_portfolio_actions": portfolio,
        "shipping_summary": shipping,
        "expedited_shipping_mismatch": mismatch.to_frame("value"),
        "monthly_seasonality": seasonality,
    }
    for name, t in tables.items():
        t.to_csv(TABLE_DIR / f"{name}.csv")

    print("4/4  Exporting figures ...")
    V.plot_yearly_trend(yearly)
    V.plot_profit_bridge(bridge)
    V.plot_discount_bands(bands)
    V.plot_breakeven(breakeven)
    V.plot_subcategory_matrix(subcats, company_margin)
    V.plot_region(regions, company_margin)
    V.plot_margin_heatmap(matrix)
    V.plot_country_losses(countries)
    V.plot_whale_curve(whale)
    V.plot_customer_tiers(tiers)
    V.plot_portfolio(portfolio)
    V.plot_shipping(shipping, mix)
    V.plot_seasonality(seasonality)
    V.plot_scenarios(scenarios, kpis["total_profit"])
    plt.close("all")

    print("\nHeadline KPIs")
    print(f"  Sales            : ${kpis['total_sales']:,.0f}")
    print(f"  Profit           : ${kpis['total_profit']:,.0f}  ({company_margin:.1%} margin)")
    print(f"  Profit destroyed : ${-kpis['profit_destroyed_by_loss_lines']:,.0f} by loss-making lines")
    print("\nDone. See reports/figures and reports/tables.")


if __name__ == "__main__":
    main()
