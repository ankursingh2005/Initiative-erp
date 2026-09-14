# AI Analysis for business decisions

Open **Home > AI Analysis** (`/analytics`). Upload the complete Excel/CSV sales
export, review category assignments, then proceed to the dashboard. Uploads
replace the previous snapshot transactionally; they do not append history.

## What to review first

1. **Data quality:** unresolved categories are outside dashboard totals. The
   warning shows their sales value before GST. Re-upload and assign them during
   review before treating the figures as whole-business results.
2. **Business decision overview:** gross profit, margin on sales, markup on cost,
   identified bills, average positive bill and returns/credits.
3. **Outlet and category profitability:** all combinations, ranked by gross
   profit. Click an outlet button to filter to that outlet and category.
4. **Below-cost sales:** largest 25 positive-sales lines below cost, including
   date, bill, outlet and item. The total loss and count cover every matching
   line, not just the displayed 25. Negative sales are reported separately.
5. **Actions supported by your data:** zero-cost sales, repeated-record candidates,
   below-cost selling, missing outlets and the largest profit contribution.
   These are review priorities, not guaranteed growth recommendations.

**Explore trends, brands and product rankings** expands supporting reports.
Date, category, store and item/brand/voucher search apply throughout. The filtered
CSV contains every matching row; the item view provides pagination.

## Category and outlet identification

Categories: Home Appliances (HA), Home Entertainment (HE), Mobile (MH), Computer
(IT), Digital Camera (DC), Accessories (ACC) and Payouts. Supported source
categories take precedence; product-name rules classify missing categories.
Common export abbreviations such as Ref, W/M, Samsung model/memory labels,
computer specifications and accessory descriptions are recognized. Uncertain
names stay in review. Review assignments can override automatic categories.

An explicit Store/Branch/Outlet/Location column takes precedence. Otherwise a
voucher such as ALM/1/24-25 supplies the code ALM. These are **inferred voucher
series**, not verified physical outlet names: codes such as B2B or SR may denote
channels or transaction types. Confirm their meaning; provide an explicit Outlet
column to override the inference. Unrecognized formats show Unknown. Upload
review displays outlet/series and voucher beside the product.

Previously saved rows do not change automatically. Re-upload the full file to
apply improved detection. Blank/summary descriptions are excluded; unresolved
items are retained for review. Rows without readable dates are skipped during
parsing. Review counts are parsed, staged lines, not physical worksheet rows.
Existing unique AC indoor/outdoor pairing reduces line counts while preserving
sales and cost amounts.

## Definitions and GST

- Decision overview, outlet/category table, loss investigation, actions and
  scenarios always use **before-GST** amounts.
- Gross profit = sales minus cost, before rent, salaries and operating expenses.
- Margin on sales = gross profit / sales. Markup on cost = gross profit / cost;
  the supplied bill-wise workbook uses this latter basis for its Profit %.
  Aggregate rates divide matching totals, not average individual percentages.
- Bill identity = outlet + date + voucher. Missing vouchers are excluded from
  bill metrics. Category bill counts overlap and must not be added together.
- Average positive bill uses bills with positive net sales in the current
  selection. Product lines are labeled separately from bills.
- Returns/credits are identified by negative sales values. A positive credit
  amount without an explicit sign cannot be identified as a return automatically.
- Repeated-record flags compare outlet, date, voucher, item, sales, cost and
  quantity. They remain included because repeated lines may be legitimate.

Select the correct **Source amounts** on upload. Exclusive amounts remain
unchanged; the inclusive option normalizes by the existing fixed 18% assumption.
The GST display toggle applies that same fixed 18% to sales and cost in supporting
reports, items and exports. It does not change the before-GST decision section.
This fixed-rate view is not a tax computation for products with differing rates.

## Margin improvement scenario

Enter a margin increase from 0 to 20 percentage points. Additional illustrated
gross profit = selected net sales before GST × increase / 100. Revenue remains
unchanged. For INR 100,000 sales, one percentage point gives INR 1,000 additional
gross profit. The control does not edit stored data or predict demand.

Bill-wise sales alone cannot establish stock ageing, lost sales, cash collection,
customer retention or net operating profit. Those analyses need inventory,
availability, receivables/customer identifiers or expense data respectively.

## Validation

- `python -m unittest discover -s tests -p test_analytics.py`: isolated temporary
  SQLite database, including upload/review/commit, filters, exports, rollback,
  classification, bill grain, returns, tax invariance and complete loss totals.
- `node tests/test_analytics_ui.cjs`: rendering, escaping, outlet/category
  drilldown, scenario validation and inline JavaScript syntax.
- The provided FY2024-25 workbook was parsed through the actual application
  pipeline: 31,936 parsed lines became 28,742 staged lines after AC pairing.
  Sales and cost totals were preserved. 26,564 staged lines were classified;
  2,178 remained for category review. These counts do not mean every automatic
  assignment has been manually verified.

Changes are local and have not been deployed. Browser visual verification was
unavailable in this session. Restart/redeploy the application to use the changes.
