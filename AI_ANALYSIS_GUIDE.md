# AI Analysis dashboard

Open **Home > AI Analysis** (`/analytics`). This module now offers HA, HE, Mobile,
Computer, Accessories and Payouts, plus date, store and item/brand/voucher search.

## Upload and GST

1. Choose the Excel/CSV export.
2. Set **Source amounts**:
   - **Before GST - add 18%** is the default for pre-GST sales and costs.
   - **Already includes 18% GST** normalizes the source before saving, so the
     dashboard does not add the tax twice.
3. Click **Analyze**. Review values are **before GST**.
4. Assign uncertain rows to a category or mark them **Exclude / unrelated**.
5. Click **Looks correct - proceed to dashboard**.

Stored amounts remain before GST. Dashboard and item/export amounts include the
fixed 18% uplift on both sales and costs (including Payouts in this analytical
view). Profit is recalculated from sales minus cost. Margin uses sales as the
denominator; this is not the cost-based PL percentage on Daily Profitability.

Example: before-GST sales 1,000 and cost 800 become sales 1,180, cost 944, profit
236 and margin on sales 20%. An inclusive input of 1,180 and 944 gives the same
result when its source option is set correctly.

Existing saved uploads are assumed to contain pre-GST amounts. If an old upload
already contained GST, re-upload the complete source with the inclusive option.
An upload replaces the previous snapshot; it does not append history. Replacement
is transactional so a failed insert preserves the previous snapshot.

## Included data and review

- Summary rows and blank/unknown item descriptions are excluded from totals.
- Unclassified products remain in **Needs category review**. They are retained,
  rather than being silently assigned to Accessories.
- Accessories and payout keywords are recognized; explicit supported source
  categories and review assignments are respected.
- Negative sales/returns and loss-making sales remain included.
- **Rows to inspect or export** lets you select included, review, excluded or all
  stored rows. This selector does not change dashboard KPI inclusion.
- **View Items** displays 100 rows per page. Previous/Next reaches every result.
- **Download filtered CSV** exports every matching row, with separate before-GST,
  GST and inclusive amounts and a review reason where applicable.

New uploads accept optional `Store`/`Branch`/`Outlet`/`Location`, `Brand`, and
`Vch No`/`Invoice No` fields. Historical rows without a store display **Unknown**;
their location is not guessed. Date parsing still skips rows without readable
dates, so the review count is the number of parsed rows, not every source line.

## Charts and statistics

- Daily sales and a trailing seven-calendar-day average (missing days count zero).
- Sales/profit scatter plot: first 1,000 filtered rows in date order, with the
  sample limit shown; tables/CSV remain complete.
- Store sales/profit comparison, alongside existing category, brand, monthly,
  yearly and item reports.
- Median sale, population standard deviation, loss-row count and unusual-sale
  count using median absolute deviation. Outliers are indicators, not exclusions.
- Pie/donut/polar areas show absolute profit/loss magnitude and label losses;
  the bar chart preserves signed profit.

Calculations are deterministic Python (`Decimal`, `statistics` and aggregation).
Interactive charts use locally bundled Chart.js 4.5.1, with its MIT license under
`static/vendor`. No external AI service or scientific-library installation is
required for this feature.

## Validation and deployment

Regression tests: `python -m unittest discover -s tests -p test_analytics.py`.
The tests choose a temporary SQLite database before importing the application.
They require the app dependencies plus `httpx` for FastAPI's test client.

The additive startup migration creates nullable `store` and `vch_no` columns in
`analytics_sales_rows`. Restart/redeploy the updated app to apply it. This change
was validated against a disposable database and synthetic browser data; it has
not been deployed or reconciled against a production workbook.
