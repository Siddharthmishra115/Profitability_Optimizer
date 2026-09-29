"""
Analysis functions for the profitability optimisation study.

Each function takes the clean transaction-level DataFrame and returns a tidy
summary table, so results can be reused in the notebook, the pipeline script
and the README without re-implementing any logic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _summarise(df: pd.DataFrame, by, observed: bool = True) -> pd.DataFrame:
    """Standard profitability summary for any grouping."""
    g = df.groupby(by, observed=observed).agg(
        sales=("sales", "sum"),
        profit=("profit", "sum"),
        gross_sales=("gross_sales", "sum"),
        discount_amount=("discount_amount", "sum"),
        shipping_cost=("shipping_cost", "sum"),
        quantity=("quantity", "sum"),
        lines=("sales", "size"),
        orders=("order_id", "nunique"),
        avg_discount=("discount", "mean"),
        loss_line_rate=("is_loss", "mean"),
    )
    g["profit_margin"] = g["profit"] / g["sales"]
    g["discount_rate"] = g["discount_amount"] / g["gross_sales"]  # revenue-weighted
    g["shipping_cost_pct"] = g["shipping_cost"] / g["sales"]
    g["sales_share"] = g["sales"] / g["sales"].sum()
    g["profit_share"] = g["profit"] / g["profit"].sum()
    return g


# ----------------------------------------------------------------------------
# 1. Business overview
# ----------------------------------------------------------------------------
def kpi_summary(df: pd.DataFrame) -> pd.Series:
    loss = df.loc[df["is_loss"], "profit"].sum()
    return pd.Series(
        {
            "total_sales": df["sales"].sum(),
            "total_profit": df["profit"].sum(),
            "profit_margin": df["profit"].sum() / df["sales"].sum(),
            "orders": df["order_id"].nunique(),
            "order_lines": len(df),
            "customers": df["customer_id"].nunique(),
            "products": df["product_key"].nunique(),
            "countries": df["country"].nunique(),
            "loss_making_lines_pct": df["is_loss"].mean(),
            "profit_from_profitable_lines": df.loc[~df["is_loss"], "profit"].sum(),
            "profit_destroyed_by_loss_lines": loss,
            "discount_given_away": df["discount_amount"].sum(),
            "shipping_cost_pct_of_sales": df["shipping_cost"].sum() / df["sales"].sum(),
        }
    )


def yearly_trend(df: pd.DataFrame) -> pd.DataFrame:
    y = _summarise(df, "year")
    y["sales_growth"] = y["sales"].pct_change()
    y["profit_growth"] = y["profit"].pct_change()
    return y[["sales", "profit", "profit_margin", "sales_growth", "profit_growth", "avg_discount", "orders"]]


def profit_bridge(df: pd.DataFrame) -> pd.DataFrame:
    """Profit earned on profitable lines, minus losses by discount band = net profit."""
    rows = [("Profit from profitable lines", df.loc[~df["is_loss"], "profit"].sum())]
    losses = df[df["is_loss"]].groupby("discount_band", observed=True)["profit"].sum()
    for band, val in losses.items():
        if abs(val) >= 1:
            rows.append((f"Losses @ {band} discount", val))
    rows.append(("Net profit", df["profit"].sum()))
    return pd.DataFrame(rows, columns=["step", "value"])


# ----------------------------------------------------------------------------
# 2. Discount diagnostics
# ----------------------------------------------------------------------------
def discount_band_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = _summarise(df, "discount_band")
    g["avg_quantity_per_line"] = df.groupby("discount_band", observed=True)["quantity"].mean()
    return g[
        ["lines", "sales", "sales_share", "profit", "profit_margin", "loss_line_rate", "avg_quantity_per_line"]
    ]


def breakeven_discount(df: pd.DataFrame) -> pd.DataFrame:
    """
    Maximum economically viable discount per sub-category.

    If a product sells at list price with margin m0, its cost is (1 - m0) of
    list price. At discount d, margin = 1 - (1 - m0) / (1 - d), which hits zero
    exactly when d = m0. So the *break-even discount equals the undiscounted
    margin*, which we estimate from full-price (0 % discount) lines.
    """
    full_price = df[df["discount"] == 0]
    m0 = full_price.groupby("sub_category").apply(
        lambda g: g["profit"].sum() / g["sales"].sum(), include_groups=False
    )
    out = _summarise(df, ["category", "sub_category"]).reset_index()
    out["breakeven_discount"] = out["sub_category"].map(m0)

    above = df["discount"] > df["sub_category"].map(m0)
    agg = (
        df.assign(above=above)
        .groupby("sub_category")
        .apply(
            lambda g: pd.Series(
                {
                    "sales_above_breakeven_pct": g.loc[g["above"], "sales"].sum() / g["sales"].sum(),
                    "profit_above_breakeven": g.loc[g["above"], "profit"].sum(),
                }
            ),
            include_groups=False,
        )
    )
    out = out.merge(agg, left_on="sub_category", right_index=True)
    cols = [
        "category", "sub_category", "sales", "profit", "profit_margin", "avg_discount",
        "breakeven_discount", "sales_above_breakeven_pct", "profit_above_breakeven",
    ]
    return out[cols].sort_values("profit_above_breakeven")


def above_breakeven_flag(df: pd.DataFrame) -> pd.Series:
    """Boolean flag: line discounted beyond its sub-category break-even."""
    be = breakeven_discount(df).set_index("sub_category")["breakeven_discount"]
    return df["discount"] > df["sub_category"].map(be)


def discount_cap_scenarios(
    df: pd.DataFrame,
    caps: dict[str, pd.Series | float] | None = None,
    volume_loss: tuple[float, ...] = (0.0, 0.25, 0.5, 1.0),
) -> pd.DataFrame:
    """
    What-if: cap discounts, re-price affected lines from list price, and assume
    a share of affected volume is lost because customers walk away.

    new_profit_line = (1 - v) * (profit + (new_sales - sales))
    Unit cost is held constant, so the uplift equals the extra revenue kept.
    v = 1.0 is the extreme case of losing every affected line entirely.
    """
    if caps is None:
        be = breakeven_discount(df).set_index("sub_category")["breakeven_discount"]
        caps = {
            "Flat cap 20%": 0.20,
            "Flat cap 30%": 0.30,
            "Sub-category guardrail (break-even - 5pp)": (df["sub_category"].map(be) - 0.05).clip(lower=0),
        }
    base = df["profit"].sum()
    rows = []
    for name, cap in caps.items():
        cap_series = cap if isinstance(cap, pd.Series) else pd.Series(cap, index=df.index)
        affected = df["discount"] > cap_series
        new_sales = df["gross_sales"] * (1 - np.minimum(df["discount"], cap_series))
        new_line_profit = df["profit"] + (new_sales - df["sales"])
        for v in volume_loss:
            scen_profit = df.loc[~affected, "profit"].sum() + ((1 - v) * new_line_profit[affected]).sum()
            scen_sales = df.loc[~affected, "sales"].sum() + ((1 - v) * new_sales[affected]).sum()
            rows.append(
                {
                    "policy": name,
                    "volume_lost_on_affected_lines": v,
                    "lines_affected_pct": affected.mean(),
                    "sales": scen_sales,
                    "profit": scen_profit,
                    "profit_margin": scen_profit / scen_sales,
                    "profit_uplift": scen_profit - base,
                    "profit_uplift_pct": scen_profit / base - 1,
                }
            )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# 3. Product & category
# ----------------------------------------------------------------------------
def category_summary(df: pd.DataFrame) -> pd.DataFrame:
    return _summarise(df, "category")[["sales", "sales_share", "profit", "profit_share", "profit_margin", "avg_discount"]]


def subcategory_summary(df: pd.DataFrame) -> pd.DataFrame:
    return _summarise(df, ["category", "sub_category"])[
        ["sales", "profit", "profit_margin", "avg_discount", "loss_line_rate"]
    ].sort_values("profit_margin")


def tables_deep_dive(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    t = df[df["sub_category"] == "Tables"]
    return {
        "by_market": _summarise(t, "market")[["sales", "profit", "profit_margin", "avg_discount", "loss_line_rate"]]
        .sort_values("profit"),
        "by_band": _summarise(t, "discount_band")[["lines", "sales", "profit", "profit_margin"]],
        "full_price_margin": pd.Series(
            {"full_price_margin": t.loc[t["discount"] == 0, "profit"].sum() / t.loc[t["discount"] == 0, "sales"].sum()}
        ).to_frame("value"),
    }


def product_portfolio(df: pd.DataFrame, min_sales: float = 0) -> pd.DataFrame:
    """Classify every product into an action quadrant."""
    p = _summarise(df, "product_key")[["sales", "profit", "profit_margin", "avg_discount", "orders"]]
    p = p[p["sales"] >= min_sales].copy()
    p["category"] = df.groupby("product_key")["category"].first()
    p["sub_category"] = df.groupby("product_key")["sub_category"].first()
    sales_cut = p["sales"].median()
    company_margin = df["profit"].sum() / df["sales"].sum()

    def classify(r):
        high_sales = r["sales"] >= sales_cut
        if r["profit"] < 0:
            return "Reprice / fix (high sales, loss)" if high_sales else "Review for discontinuation"
        if r["profit_margin"] >= company_margin:
            return "Stars - grow & promote" if high_sales else "Niche winners - expand reach"
        return "Maintain - margin below company avg"

    p["portfolio_action"] = p.apply(classify, axis=1)
    return p.sort_values("profit")


def portfolio_summary(portfolio: pd.DataFrame) -> pd.DataFrame:
    s = portfolio.groupby("portfolio_action").agg(
        products=("sales", "size"), sales=("sales", "sum"), profit=("profit", "sum"), avg_discount=("avg_discount", "mean")
    )
    s["sales_share"] = s["sales"] / s["sales"].sum()
    s["profit_margin"] = s["profit"] / s["sales"]
    return s.sort_values("profit", ascending=False)


# ----------------------------------------------------------------------------
# 4. Geography
# ----------------------------------------------------------------------------
def market_summary(df: pd.DataFrame) -> pd.DataFrame:
    return _summarise(df, "market")[
        ["sales", "profit", "profit_margin", "avg_discount", "shipping_cost_pct", "loss_line_rate"]
    ].sort_values("profit_margin")


def region_summary(df: pd.DataFrame) -> pd.DataFrame:
    return _summarise(df, "region")[
        ["sales", "profit", "profit_margin", "avg_discount", "shipping_cost_pct", "loss_line_rate"]
    ].sort_values("profit_margin")


def country_losses(df: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    c = _summarise(df, ["market", "country"])[["sales", "profit", "profit_margin", "avg_discount"]]
    c["discount_levels_used"] = df.groupby(["market", "country"])["discount"].apply(
        lambda s: ", ".join(f"{x:.0%}" for x in sorted(s.unique()))
    )
    return c[c["profit"] < 0].sort_values("profit").head(top)


def us_state_losses(df: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    s = _summarise(df[df["country"] == "United States"], "state")[["sales", "profit", "profit_margin", "avg_discount"]]
    return s[s["profit"] < 0].sort_values("profit").head(top)


def leakage_hotspots(df: pd.DataFrame, min_sales: float = 20_000) -> pd.DataFrame:
    """Market x Segment x Sub-category combinations that lose money at scale."""
    h = _summarise(df, ["market", "segment", "sub_category"])[
        ["sales", "profit", "profit_margin", "avg_discount", "lines"]
    ]
    return h[(h["sales"] >= min_sales) & (h["profit"] < 0)].sort_values("profit")


def margin_matrix(df: pd.DataFrame, rows: str = "sub_category", cols: str = "market") -> pd.DataFrame:
    g = df.groupby([rows, cols]).agg(sales=("sales", "sum"), profit=("profit", "sum"))
    return (g["profit"] / g["sales"]).unstack(cols)


# ----------------------------------------------------------------------------
# 5. Customers
# ----------------------------------------------------------------------------
def customer_profitability(df: pd.DataFrame) -> pd.DataFrame:
    c = _summarise(df, ["customer_id"])[
        ["sales", "profit", "profit_margin", "avg_discount", "orders", "lines", "shipping_cost_pct"]
    ]
    c["segment"] = df.groupby("customer_id")["segment"].first()
    c["market"] = df.groupby("customer_id")["market"].first()
    above = above_breakeven_flag(df)
    c["share_lines_above_breakeven"] = above.groupby(df["customer_id"]).mean()

    pos = c.loc[c["profit"] > 0, "profit"]
    q = pos.quantile([0.5]).iloc[0]
    c["profit_tier"] = np.select(
        [c["profit"] < 0, c["profit"] < q],
        ["Loss-making", "Low profit"],
        default="High profit",
    )
    return c.sort_values("profit", ascending=False)


def customer_tier_summary(cust: pd.DataFrame) -> pd.DataFrame:
    t = cust.groupby("profit_tier").agg(
        customers=("sales", "size"),
        sales=("sales", "sum"),
        profit=("profit", "sum"),
        avg_discount=("avg_discount", "mean"),
        avg_orders=("orders", "mean"),
        share_lines_above_breakeven=("share_lines_above_breakeven", "mean"),
    )
    t["customer_share"] = t["customers"] / t["customers"].sum()
    t["sales_share"] = t["sales"] / t["sales"].sum()
    t["profit_margin"] = t["profit"] / t["sales"]
    return t.loc[["High profit", "Low profit", "Loss-making"]]


def whale_curve(cust: pd.DataFrame) -> pd.DataFrame:
    w = cust.sort_values("profit", ascending=False).reset_index()
    w["cum_customers_pct"] = (np.arange(len(w)) + 1) / len(w)
    w["cum_profit_pct"] = w["profit"].cumsum() / w["profit"].sum()
    return w[["customer_id", "profit", "cum_customers_pct", "cum_profit_pct"]]


# ----------------------------------------------------------------------------
# 6. Shipping
# ----------------------------------------------------------------------------
def shipping_summary(df: pd.DataFrame) -> pd.DataFrame:
    s = _summarise(df, "ship_mode")[["lines", "sales", "shipping_cost", "shipping_cost_pct", "profit_margin"]]
    s["avg_ship_days"] = df.groupby("ship_mode")["ship_days"].mean()
    return s.sort_values("shipping_cost_pct")


def priority_mode_mix(df: pd.DataFrame) -> pd.DataFrame:
    order = ["Critical", "High", "Medium", "Low"]
    modes = ["Same Day", "First Class", "Second Class", "Standard Class"]
    return pd.crosstab(df["order_priority"], df["ship_mode"], normalize="index").reindex(index=order, columns=modes)


def expedited_mismatch(df: pd.DataFrame) -> pd.Series:
    """Medium/Low priority lines shipped First Class or Same Day."""
    std_rate = df.loc[df["ship_mode"] == "Standard Class", "shipping_cost"].sum() / df.loc[
        df["ship_mode"] == "Standard Class", "sales"
    ].sum()
    mm = df[df["order_priority"].isin(["Medium", "Low"]) & df["is_expedited"]]
    return pd.Series(
        {
            "lines": len(mm),
            "share_of_medium_low_lines": len(mm) / df["order_priority"].isin(["Medium", "Low"]).sum(),
            "sales": mm["sales"].sum(),
            "shipping_cost": mm["shipping_cost"].sum(),
            "shipping_cost_pct": mm["shipping_cost"].sum() / mm["sales"].sum(),
            "standard_class_rate": std_rate,
            "est_saving_if_standard": mm["shipping_cost"].sum() - mm["sales"].sum() * std_rate,
        }
    )


# ----------------------------------------------------------------------------
# 7. Seasonality
# ----------------------------------------------------------------------------
def monthly_seasonality(df: pd.DataFrame) -> pd.DataFrame:
    m = _summarise(df, ["month", "month_name"]).reset_index().set_index("month")
    m["seasonality_index"] = m["sales"] / m["sales"].mean()
    return m[["month_name", "sales", "profit", "profit_margin", "avg_discount", "seasonality_index"]]


def monthly_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    return _summarise(df, "order_month")[["sales", "profit", "profit_margin"]]
