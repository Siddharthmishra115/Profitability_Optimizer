"""
Data cleaning & feature engineering for the Global Superstore dataset.

Every step is logged so the cleaning decisions are auditable (see
`reports/tables/cleaning_log.csv`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CLEAN_DATA, DISCOUNT_BINS, DISCOUNT_LABELS, RAW_DATA, TABLE_DIR

COLUMN_MAP = {
    "Row.ID": "row_id",
    "Order.ID": "order_id",
    "Order.Date": "order_date",
    "Ship.Date": "ship_date",
    "Ship.Mode": "ship_mode",
    "Customer.ID": "customer_id",
    "Customer.Name": "customer_name",
    "Segment": "segment",
    "City": "city",
    "State": "state",
    "Country": "country",
    "Region": "region",
    "Market": "market",
    "Market2": "market_group",
    "Product.ID": "product_id",
    "Category": "category",
    "Sub.Category": "sub_category",
    "Product.Name": "product_name",
    "Sales": "sales",
    "Quantity": "quantity",
    "Discount": "discount",
    "Profit": "profit",
    "Shipping.Cost": "shipping_cost",
    "Order.Priority": "order_priority",
    "Year": "year",
    "weeknum": "week_num",
}


class CleaningLog:
    """Collects a human-readable record of every cleaning decision."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, step: str, detail: str, rows_affected: int = 0) -> None:
        self.rows.append({"step": step, "detail": detail, "rows_affected": int(rows_affected)})

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def load_raw(path=RAW_DATA) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8")


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (clean_df, cleaning_log_df)."""
    log = CleaningLog()
    df = raw.copy()
    log.add("load", f"Raw file: {df.shape[0]:,} rows x {df.shape[1]} columns")

    # 1. Drop non-informative columns ------------------------------------
    const_cols = [c for c in df.columns if df[c].nunique() == 1]
    df = df.drop(columns=const_cols)
    log.add("drop_constant_columns", f"Dropped constant column(s): {const_cols}")

    # 2. Standardise column names -----------------------------------------
    df = df.rename(columns=COLUMN_MAP)
    log.add("rename_columns", "Renamed columns to snake_case")

    # 3. Trim whitespace in text columns -----------------------------------
    text_cols = df.select_dtypes(include=["object", "string"]).columns
    changed = 0
    for c in text_cols:
        stripped = df[c].astype(str).str.strip()
        changed += int((stripped != df[c].astype(str)).sum())
        df[c] = stripped
    log.add("strip_whitespace", "Trimmed leading/trailing spaces in text columns", changed)

    # 4. Types -------------------------------------------------------------
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["ship_date"] = pd.to_datetime(df["ship_date"], errors="coerce")
    bad_dates = int(df[["order_date", "ship_date"]].isna().any(axis=1).sum())
    log.add("parse_dates", "Parsed order_date / ship_date to datetime", bad_dates)

    # 5. Missing values & duplicates --------------------------------------
    log.add("missing_values", "Null cells found across dataset", int(df.isna().sum().sum()))
    dup_full = int(df.duplicated().sum())
    dup_id = int(df["row_id"].duplicated().sum())
    df = df.drop_duplicates()
    log.add("duplicates", f"Exact duplicate rows removed; duplicate row_id = {dup_id}", dup_full)

    # 6. Business-rule validation -----------------------------------------
    ship_before_order = df["ship_date"] < df["order_date"]
    log.add("validate_ship_date", "Rows where ship_date < order_date", int(ship_before_order.sum()))
    df = df[~ship_before_order]

    year_mismatch = int((df["order_date"].dt.year != df["year"]).sum())
    log.add("validate_year", "Rows where Year column disagrees with order_date", year_mismatch)

    out_of_range = ~df["discount"].between(0, 1)
    log.add("validate_discount_range", "Rows with discount outside [0, 1]", int(out_of_range.sum()))
    df = df[~out_of_range]

    zero_sales = df["sales"] <= 0
    log.add(
        "remove_zero_sales",
        "Removed rows with sales <= 0 (margin undefined; profit impact negligible)",
        int(zero_sales.sum()),
    )
    df = df[~zero_sales]

    # 7. Standardise discount precision -----------------------------------
    # LATAM contains values like 0.002 / 0.202 / 0.402 / 0.602 – a precision
    # artefact next to the standard 0 / 0.2 / 0.4 / 0.6 tiers.
    raw_disc = df["discount"].copy()
    df["discount"] = df["discount"].round(2)
    log.add(
        "round_discount",
        "Rounded discount to 2 dp (0.002 -> 0.00, 0.202 -> 0.20 ...); LATAM precision artefact",
        int((raw_disc != df["discount"]).sum()),
    )

    # 8. Known data caveats (documented, not changed) ----------------------
    multi_name = int(df.groupby("product_id")["product_name"].nunique().gt(1).sum())
    log.add(
        "caveat_product_id",
        "product_id values mapped to >1 product_name -> using product_id + product_name as product key",
        multi_name,
    )
    log.add(
        "caveat_customer_id",
        f"customer_id is market-specific: {df['customer_id'].nunique():,} IDs vs "
        f"{df['customer_name'].nunique():,} names. Customer analysis uses customer_id (customer account per market).",
    )
    log.add("caveat_sales_rounding", "Sales is stored as whole currency units in the source; left as-is")

    # 9. Feature engineering ----------------------------------------------
    df["product_key"] = df["product_id"] + " | " + df["product_name"]
    df["order_month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    df["month"] = df["order_date"].dt.month
    df["month_name"] = df["order_date"].dt.strftime("%b")
    df["quarter"] = df["order_date"].dt.quarter
    df["ship_days"] = (df["ship_date"] - df["order_date"]).dt.days

    df["profit_margin"] = df["profit"] / df["sales"]
    df["is_loss"] = df["profit"] < 0
    df["shipping_cost_pct"] = df["shipping_cost"] / df["sales"]
    # Price before discount and the revenue given away through discounting
    df["gross_sales"] = df["sales"] / (1 - df["discount"])
    df["discount_amount"] = df["gross_sales"] - df["sales"]
    df["unit_price"] = df["sales"] / df["quantity"]
    df["discount_band"] = pd.cut(
        df["discount"], bins=DISCOUNT_BINS, labels=DISCOUNT_LABELS, ordered=True
    )
    df["is_expedited"] = df["ship_mode"].isin(["First Class", "Same Day"])
    df["is_urgent_priority"] = df["order_priority"].isin(["Critical", "High"])
    log.add("feature_engineering", "Added margin, discount band, gross sales, shipping %, ship days, flags")

    df = df.sort_values("order_date").reset_index(drop=True)
    log.add("final", f"Clean file: {df.shape[0]:,} rows x {df.shape[1]} columns")
    return df, log.to_frame()


def run(save: bool = True) -> pd.DataFrame:
    df, log = clean(load_raw())
    if save:
        df.to_csv(CLEAN_DATA, index=False)
        log.to_csv(TABLE_DIR / "cleaning_log.csv", index=False)
    return df


def load_clean() -> pd.DataFrame:
    """Load the processed file (build it first if missing)."""
    if not CLEAN_DATA.exists():
        return run()
    df = pd.read_csv(CLEAN_DATA, parse_dates=["order_date", "ship_date", "order_month"])
    df["discount_band"] = pd.Categorical(df["discount_band"], categories=DISCOUNT_LABELS, ordered=True)
    return df


if __name__ == "__main__":
    out = run()
    print(pd.read_csv(TABLE_DIR / "cleaning_log.csv").to_string(index=False))
