"""Project-wide paths and plotting settings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DATA = ROOT / "data" / "raw" / "superstore.csv"
CLEAN_DATA = ROOT / "data" / "processed" / "superstore_clean.csv"
FIG_DIR = ROOT / "reports" / "figures"
TABLE_DIR = ROOT / "reports" / "tables"

for _d in (CLEAN_DATA.parent, FIG_DIR, TABLE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Discount bands used throughout the analysis
DISCOUNT_BINS = [-0.001, 0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 1.0]
DISCOUNT_LABELS = ["0%", "1-10%", "11-20%", "21-30%", "31-40%", "41-50%", ">50%"]

# Colours
GOOD = "#2E7D32"
BAD = "#C62828"
NEUTRAL = "#546E7A"
ACCENT = "#1565C0"
