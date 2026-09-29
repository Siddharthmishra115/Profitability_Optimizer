"""
Chart functions. Every chart title states the insight ("action title"),
not just the metric, so each figure can be dropped straight into a deck.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns

from .config import ACCENT, BAD, FIG_DIR, GOOD, NEUTRAL

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update(
    {
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "axes.titleweight": "bold",
        "axes.titlesize": 13,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

pct = mtick.PercentFormatter(1.0, decimals=0)


def _money(x, _=None):
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e6:
        return f"{sign}${x/1e6:.1f}M"
    if x >= 1e3:
        return f"{sign}${x/1e3:.0f}K"
    return f"{sign}${x:.0f}"


money = mtick.FuncFormatter(_money)


def _save(fig, name: str, save: bool):
    if save:
        fig.savefig(FIG_DIR / f"{name}.png")
    return fig


def _subtitle(ax, text):
    ax.text(0, 1.02, text, transform=ax.transAxes, fontsize=9.5, color=NEUTRAL, va="bottom")


# ----------------------------------------------------------------------------
def plot_yearly_trend(yearly: pd.DataFrame, save=True):
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = yearly.index.astype(str)
    ax.bar(x, yearly["sales"], color="#B0BEC5", label="Sales")
    ax.bar(x, yearly["profit"], color=ACCENT, width=0.5, label="Profit")
    ax.yaxis.set_major_formatter(money)
    ax2 = ax.twinx()
    ax2.plot(x, yearly["profit_margin"], color=BAD, marker="o", lw=2.5, label="Profit margin")
    ax2.set_ylim(0, 0.2)
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=1))
    ax2.grid(False)
    ax.grid(axis="x", visible=False)
    for xi, m in zip(x, yearly["profit_margin"]):
        ax2.annotate(f"{m:.1%}", (xi, m), textcoords="offset points", xytext=(0, 8), ha="center", color=BAD)
    ax.set_title("Sales nearly doubled (2011-14) but margin stayed flat at ~11-12%", pad=22)
    _subtitle(ax, "Scale is not creating operating leverage - each extra $ of sales earns the same ~12 cents")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", frameon=False)
    return _save(fig, "01_yearly_trend", save)


def plot_profit_bridge(bridge: pd.DataFrame, save=True):
    b = bridge[bridge["value"].abs() >= 1000].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(11, 5))
    running = 0
    for i, r in b.iterrows():
        if i == 0 or r["step"] == "Net profit":
            bottom, height, color = 0, r["value"], ACCENT if i == 0 else GOOD
            running = r["value"] if i == 0 else running
        else:
            bottom, height, color = running + r["value"], -r["value"], BAD
            running += r["value"]
        ax.bar(i, height, bottom=bottom, color=color, width=0.65)
        ax.text(i, bottom + height + 25_000, _money(r["value"]), ha="center", fontsize=9, fontweight="bold")
    ax.set_xticks(range(len(b)))
    labels = [s.replace("Losses @ ", "Losses\n").replace(" discount", "\ndiscount").replace("Profit from ", "Profit from\n")
              for s in b["step"]]
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.yaxis.set_major_formatter(money)
    lost = -b.loc[b["step"].str.startswith("Losses"), "value"].sum()
    ax.set_title(f"Loss-making order lines wipe out {_money(lost)} ({lost / b['value'].iloc[0]:.0%}) of profit earned", pad=22)
    deep = -b.loc[b["step"].str.contains(r"31-40%|41-50%|>50%", regex=True), "value"].sum()
    _subtitle(ax, f"Profit bridge: {deep / lost:.0%} of the leakage comes from lines discounted above 30%")
    return _save(fig, "02_profit_bridge", save)


def plot_discount_bands(band: pd.DataFrame, save=True):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    b = band.reset_index()
    colors = [GOOD if m > 0 else BAD for m in b["profit_margin"]]
    axes[0].bar(b["discount_band"].astype(str), b["profit_margin"], color=colors)
    axes[0].axhline(0, color="black", lw=0.8)
    axes[0].yaxis.set_major_formatter(pct)
    for i, m in enumerate(b["profit_margin"]):
        axes[0].text(i, m + (0.03 if m > 0 else -0.08), f"{m:.0%}", ha="center", fontsize=9)
    axes[0].set_title("Margin turns negative once discount exceeds 20%")
    axes[0].set_xlabel("Discount band")
    axes[0].set_ylabel("Profit margin")

    axes[1].bar(b["discount_band"].astype(str), b["avg_quantity_per_line"], color="#90A4AE")
    axes[1].set_ylim(0, 5)
    for i, q in enumerate(b["avg_quantity_per_line"]):
        axes[1].text(i, q + 0.1, f"{q:.1f}", ha="center", fontsize=9)
    axes[1].set_title("...and deeper discounts do NOT sell more units per order")
    axes[1].set_xlabel("Discount band")
    axes[1].set_ylabel("Avg units per order line")
    fig.tight_layout()
    return _save(fig, "03_discount_band_margin_volume", save)


def plot_breakeven(be: pd.DataFrame, save=True):
    d = be.sort_values("breakeven_discount").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 6.5))
    y = np.arange(len(d))
    ax.hlines(y, d["breakeven_discount"], d["avg_discount"], color="#CFD8DC", lw=3)
    ax.scatter(d["breakeven_discount"], y, color=GOOD, s=70, label="Break-even discount (= full-price margin)", zorder=3)
    ax.scatter(d["avg_discount"], y, color=ACCENT, s=70, label="Average discount given", zorder=3)
    for i, r in d.iterrows():
        ax.text(max(r["breakeven_discount"], r["avg_discount"]) + 0.01, i,
                f"{r['sales_above_breakeven_pct']:.0%} of sales above break-even", va="center", fontsize=8.5,
                color=BAD if r["sales_above_breakeven_pct"] > 0.2 else NEUTRAL)
    ax.set_yticks(y)
    ax.set_yticklabels(d["sub_category"])
    ax.xaxis.set_major_formatter(pct)
    ax.set_xlim(0, 0.6)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=2, frameon=False, fontsize=9)
    ax.set_title("Every sub-category has a hard discount ceiling of ~21-32%", pad=22)
    _subtitle(ax, "Any discount above the green dot sells at a loss; Tables sells 44% of revenue beyond it")
    return _save(fig, "04_breakeven_discount_by_subcategory", save)


def plot_subcategory_matrix(sub: pd.DataFrame, company_margin: float, save=True):
    d = sub.reset_index()
    fig, ax = plt.subplots(figsize=(10, 6))
    palette = {"Furniture": "#8D6E63", "Office Supplies": "#26A69A", "Technology": "#5C6BC0"}
    for cat, g in d.groupby("category"):
        ax.scatter(g["sales"], g["profit_margin"], s=g["avg_discount"] * 2500, alpha=0.7,
                   color=palette[cat], label=cat, edgecolor="white")
    for _, r in d.iterrows():
        ax.annotate(r["sub_category"], (r["sales"], r["profit_margin"]), fontsize=8.5,
                    xytext=(6, 4), textcoords="offset points")
    ax.axhline(company_margin, ls="--", color=NEUTRAL, lw=1)
    ax.axhline(0, color=BAD, lw=1)
    ax.text(ax.get_xlim()[1] * 0.45, company_margin - 0.012, f"Company margin {company_margin:.1%}",
            ha="left", color=NEUTRAL, fontsize=9)
    ax.xaxis.set_major_formatter(money)
    ax.yaxis.set_major_formatter(pct)
    ax.set_xlabel("Sales")
    ax.set_ylabel("Profit margin")
    ax.legend(frameon=False, loc="lower right", markerscale=0.4)
    ax.set_title("Tables is the only loss-making sub-category; Furniture drags the mix", pad=22)
    _subtitle(ax, "Bubble size = average discount")
    return _save(fig, "05_subcategory_sales_vs_margin", save)


def plot_region(region: pd.DataFrame, company_margin: float, save=True):
    d = region.sort_values("profit_margin")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    colors = [BAD if m < company_margin * 0.75 else (GOOD if m > company_margin else "#90A4AE") for m in d["profit_margin"]]
    ax.barh(d.index, d["profit_margin"], color=colors)
    ax.axvline(company_margin, ls="--", color=NEUTRAL)
    for i, (m, disc) in enumerate(zip(d["profit_margin"], d["avg_discount"])):
        ax.text(m + 0.004, i, f"{m:.1%}  | avg discount {disc:.0%}", va="center", fontsize=8.5)
    ax.xaxis.set_major_formatter(pct)
    ax.set_xlim(0, 0.38)
    ax.set_title("Regional margin mirrors discount depth, not sales size", pad=22)
    _subtitle(ax, "Southeast Asia (27% avg discount) keeps 2 cents per $ of sales; North Asia (5%) keeps 20 cents")
    return _save(fig, "06_region_margin_vs_discount", save)


def plot_margin_heatmap(matrix: pd.DataFrame, save=True):
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.heatmap(matrix, annot=True, fmt=".0%", cmap="RdYlGn", center=0, vmin=-0.25, vmax=0.35,
                linewidths=0.5, cbar_kws={"format": pct, "label": "Profit margin"}, ax=ax, annot_kws={"size": 8})
    ax.set_xlabel("Market")
    ax.set_ylabel("")
    ax.set_title("Tables loses money in 4 of 7 markets - a product problem, not a regional one", pad=22)
    _subtitle(ax, "Profit margin by sub-category x market")
    return _save(fig, "07_margin_heatmap_subcategory_market", save)


def plot_country_losses(countries: pd.DataFrame, save=True):
    d = countries.reset_index().head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(d["country"] + " (" + d["market"] + ")", d["profit"], color=BAD)
    for i, r in enumerate(d.itertuples()):
        ax.text(r.profit - 1500, i, f"{_money(r.profit)} | avg disc {r.avg_discount:.0%}", va="center", ha="right",
                fontsize=8.5, color=NEUTRAL)
    ax.set_xlim(d["profit"].min() * 1.45, 0)
    ax.xaxis.set_major_formatter(money)
    ax.set_title("Every top loss-making country runs 35-70% average discounts", pad=22)
    _subtitle(ax, "Turkey (flat 60%) and Nigeria (flat 70%) alone lose ~$180K - a pricing policy, not promotions")
    return _save(fig, "08_top_loss_countries", save)


def plot_whale_curve(whale: pd.DataFrame, save=True):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(whale["cum_customers_pct"], whale["cum_profit_pct"], color=ACCENT, lw=2.5)
    peak_i = whale["cum_profit_pct"].idxmax()
    px, py = whale.loc[peak_i, "cum_customers_pct"], whale.loc[peak_i, "cum_profit_pct"]
    ax.scatter([px], [py], color=BAD, zorder=3)
    ax.annotate(f"{px:.0%} of customers generate\n{py:.0%} of total profit", (px, py), xytext=(-60, -90),
                textcoords="offset points", fontsize=9, arrowprops=dict(arrowstyle="->", color=NEUTRAL))
    ax.axhline(1, ls="--", color=NEUTRAL)
    ax.fill_between(whale["cum_customers_pct"], 1, whale["cum_profit_pct"],
                    where=whale["cum_customers_pct"] >= px, color=BAD, alpha=0.15)
    ax.xaxis.set_major_formatter(pct)
    ax.yaxis.set_major_formatter(pct)
    ax.set_xlabel("Cumulative % of customers (ranked by profit)")
    ax.set_ylabel("Cumulative % of profit")
    ax.set_title(f"Profit whale curve: the bottom {1 - px:.0%} of customers erase {py - 1:.0%} of profit", pad=22)
    _subtitle(ax, "Customer = market-level customer account")
    return _save(fig, "09_customer_whale_curve", save)


def plot_customer_tiers(tiers: pd.DataFrame, save=True):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    colors = [GOOD, "#90A4AE", BAD]
    metrics = [
        ("avg_discount", "Average discount", pct),
        ("share_lines_above_breakeven", "Share of lines above break-even discount", pct),
        ("profit_margin", "Profit margin", pct),
    ]
    for ax, (col, title, fmt) in zip(axes, metrics):
        ax.bar(tiers.index, tiers[col], color=colors)
        ax.yaxis.set_major_formatter(fmt)
        ax.set_title(title, fontsize=11)
        ax.axhline(0, color="black", lw=0.8)
        for i, v in enumerate(tiers[col]):
            ax.text(i, v / 2, f"{v:.0%}", ha="center", va="center", fontsize=10, color="white", fontweight="bold")
        ax.tick_params(axis="x", labelsize=9)
    fig.suptitle("Loss-making customers get 3x the discount and half their lines are priced below cost",
                 fontweight="bold", y=1.03)
    fig.tight_layout()
    return _save(fig, "10_customer_tiers", save)


def plot_portfolio(portfolio: pd.DataFrame, save=True):
    colors = {
        "Stars - grow & promote": GOOD,
        "Niche winners - expand reach": "#81C784",
        "Maintain - margin below company avg": "#B0BEC5",
        "Reprice / fix (high sales, loss)": "#EF6C00",
        "Review for discontinuation": BAD,
    }
    fig, ax = plt.subplots(figsize=(10, 6))
    for k, g in portfolio.groupby("portfolio_action"):
        ax.scatter(g["sales"], g["profit"], s=10, alpha=0.5, color=colors[k], label=f"{k} ({len(g):,})")
    ax.set_xscale("log")
    ax.set_yscale("symlog", linthresh=100)
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(portfolio["sales"].median(), color=NEUTRAL, ls="--", lw=1)
    ax.set_xlabel("Product sales (log scale)")
    ax.set_ylabel("Product profit (symlog scale)")
    ax.legend(frameon=False, fontsize=8.5, loc="lower left", markerscale=2)
    ax.set_title("1,432 high-selling products lose $474K - repricing beats cutting", pad=22)
    _subtitle(ax, "Product portfolio quadrants (dashed line = median product sales)")
    return _save(fig, "11_product_portfolio", save)


def plot_shipping(ship: pd.DataFrame, mix: pd.DataFrame, save=True):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={"width_ratios": [1, 1.2]})
    d = ship.sort_values("shipping_cost_pct")
    axes[0].bar(d.index, d["shipping_cost_pct"], color=["#90A4AE", "#FFB74D", "#EF6C00", BAD])
    for i, v in enumerate(d["shipping_cost_pct"]):
        axes[0].text(i, v + 0.004, f"{v:.1%}", ha="center", fontsize=9)
    axes[0].yaxis.set_major_formatter(pct)
    axes[0].set_title("Shipping cost as % of sales", fontsize=11)
    axes[0].tick_params(axis="x", labelsize=9)
    sns.heatmap(mix, annot=True, fmt=".0%", cmap="Blues", cbar=False, ax=axes[1], linewidths=0.5)
    axes[1].set_title("Ship-mode mix by order priority", fontsize=11)
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Order priority")
    fig.suptitle("Expedited modes cost 2x Standard; ~10% of Medium-priority lines still ship express",
                 fontweight="bold", y=1.03)
    fig.tight_layout()
    return _save(fig, "12_shipping_cost", save)


def plot_seasonality(month: pd.DataFrame, save=True):
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(month["month_name"], month["sales"], color=[ACCENT if s > 1.1 else "#B0BEC5" for s in month["seasonality_index"]])
    ax.yaxis.set_major_formatter(money)
    ax2 = ax.twinx()
    ax2.plot(month["month_name"], month["profit_margin"], color=BAD, marker="o", lw=2)
    ax2.set_ylim(0, 0.2)
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax2.grid(False)
    ax.grid(axis="x", visible=False)
    ax.set_title("Demand peaks Jun, Aug-Dec, but peak months don't deliver higher margin", pad=22)
    _subtitle(ax, "Bars = total sales 2011-14 (blue = >10% above monthly average); line = profit margin")
    return _save(fig, "13_seasonality", save)


def plot_scenarios(scen: pd.DataFrame, base_profit: float, save=True):
    d = scen.copy()
    d["volume_lost"] = (d["volume_lost_on_affected_lines"] * 100).astype(int).astype(str) + "% of affected volume lost"
    fig, ax = plt.subplots(figsize=(11, 5))
    sns.barplot(data=d, x="policy", y="profit", hue="volume_lost", palette="Blues_r", ax=ax)
    ax.axhline(base_profit, color=BAD, ls="--", lw=1.5, label=f"Current profit ({_money(base_profit)})")
    for cont in ax.containers:
        ax.bar_label(cont, labels=[f"+{(h.get_height() / base_profit - 1):.0%}" for h in cont], fontsize=8, padding=2)
    ax.yaxis.set_major_formatter(money)
    ax.set_ylim(0, d["profit"].max() * 1.12)
    ax.set_xlabel("")
    ax.set_ylabel("Scenario profit")
    ax.legend(frameon=False, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3)
    lo, hi = d["profit_uplift_pct"].min(), d["profit_uplift_pct"].max()
    ax.set_title(f"Discount guardrails lift profit {lo:.0%}-{hi:.0%} in every scenario - even if affected sales are lost",
                 pad=22)
    _subtitle(ax, "What-if: discounts capped, affected lines re-priced from list; unit cost held constant")
    return _save(fig, "14_discount_cap_scenarios", save)
