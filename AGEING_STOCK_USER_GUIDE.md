# Ageing Stock - Illustrated User Guide

Simple instructions for Initiative ERP. Based on project source reviewed on 12 September 2026. Example quantities are for learning, not live inventory.

## 1. Open your stock report

Ageing stock means stock grouped by how long it has been held, using the age quantities in your uploaded workbook. This report helps you see what is available, how old it is, and where it is located.

### Get ready

- Keep your username or email and password ready.
- Connect your phone or computer to the internet.
- If you handle uploads, keep the complete current stock workbook ready.

### Sign in and open the page

1. Open your browser and visit **https://erp.initiative.co.in**.
2. Enter **Username / Email** and **Password**.
3. Tap **Sign in**.
4. On Home, open the navigation menu if it is hidden.
5. Choose **Ageing Stock**.
6. Wait for **Ageing Stock Analysis** to load.

**You should see:** category cards and stock tables if data is available. If no data has been uploaded, ask your administrator to upload the workbook.

Direct page: `https://erp.initiative.co.in/ageing-stock`.

**Tap** means touch once on a phone. **Click** means select with your mouse. Both do the same job in this guide.

If you forgot your password, use **Forgot password?** on the sign-in page. If you do not have an account, ask your administrator.

## 2. Prepare the workbook

This part is for the person responsible for stock uploads. If data is already available and you only need to view it, go to page 5.

### Ask for a complete stock export

1. Ask the stock or accounts team for the latest complete stock ageing workbook.
2. Use an Excel **.xlsx** workbook. The file picker also lists .xls, but the current reader may reject older .xls files; save a genuine .xlsx copy in Excel if needed.
3. Check that it contains an **All Data** sheet.
4. Check the branch sheets for **ALM, HZT, ASH, GNG, VKN, and MWH**.
5. Check item details, units, closing quantities, and the six ageing groups.
6. Keep the original file so you can check the report against it later.

### Make the sheets agree

Use consistent item names across All Data and branch sheets. Include each branch's ageing quantities, not only its total stock quantity. The report compares overall ageing quantities with branch quantities.

### Understand what is included

- The current import includes items measured in **Nos.**; other units and blank units are skipped.
- Items matched on **PWH or Vault** sheets are excluded entirely, including their matching All Data entries.
- Items whose age quantities do not agree with their combined branch quantities can be hidden from the report.

**Before uploading:** every successful new import replaces the whole previous Ageing Stock dataset. Use a complete workbook, even if you want to inspect just one branch afterward. Your filter choices do not limit the replacement.

## 3. Upload and check the result

Upload and main data-clearing actions are available to Admin accounts and the inherited Owner/HR access in the current source. If the upload panel is missing, ask your administrator.

### Upload the file

1. Find **Upload stock ageing workbook**.
2. Tap the file selector and choose your workbook.
3. Check the filename before continuing.
4. Tap **Upload & Process**.
5. Wait while the button says **Processing...**.
6. Read the message below the buttons.

**You should see:** a message such as **Loaded 120 items from sheets: ALM, HZT, ASH, GNG, VKN, MWH.** The number will depend on your file.

### Read every part of the message

| Message | What to do |
| --- | --- |
| Loaded items | Check that the count is reasonable for the workbook. It is an item count, not a unit total. |
| Missing sheets | Ask the uploader to check missing or unreadable branch sheets before relying on location totals. |
| Items need manual category review | Ask the responsible person to review item classification. Look for REVIEW in the report. |
| Last upload | Check the filename, uploader, time, and item count shown below the upload controls. |

The report reflects the latest uploaded workbook. It does not automatically become a fresh stock snapshot just because you open it on a new day.

You do not need to press the main **Clear** button before a normal replacement upload.

## 4. Choose categories, brands, and items

Filters help you narrow a large stock list. Change one filter at a time and wait for the page to update.

### Choose one or more main categories

1. Tap **All Categories**.
2. Keep the categories you want checked and untick the others.
3. Tap outside the menu to close it.

The choices are **HA, HE, COMPUTER, MOBILE, DIGITAL CAMERA, and ACCESSORIES**. At least one category stays selected. **Select all** brings them all back.

### Choose a brand

1. Tap **All Brands**.
2. Type in **Search brand...** if the list is long.
3. Select the brand you want.
4. Choose **All Brands** again when you want all brands.

### Choose a product type or search a model

1. Tap **All Item Categories** to choose a more specific product type from the available list.
2. Use **Search item category...** to find a type quickly.
3. Use **Search item details or model no...** to find a product by its description or model number.
4. Pause briefly after typing so the results can update.
5. Delete the search text and restore **All Item Categories** to widen the results.

**Remember:** the filters work together. A correct model can appear missing when a different brand or category is still selected.

## 5. Choose branches and stock age

### Choose the branch columns

1. Tap **Branch**.
2. Tick the branches you want to inspect: **ALM, HZT, ASH, GNG, VKN, MWH**.
3. Untick the other branches and close the menu.
4. Read the selected branch columns and **Present At**.

Use the individual branch column for that branch's quantity. **Closing Qty** is based on the selected ageing groups and can include stock at other branches. Hiding a branch column does not make Closing Qty a branch-only total.

### Choose the stock age

1. Tap **Date Duration**.
2. Keep the age groups you want checked.
3. Untick the groups you do not need.
4. Close the menu and wait for the table to update.

| Age group | Meaning in the uploaded stock report |
| --- | --- |
| 0-60 Days | Stock in the first 60-day group |
| 61-90 Days | Stock in the 61 to 90-day group |
| 91-150 Days | Stock in the 91 to 150-day group |
| 151-180 Days | Stock in the 151 to 180-day group |
| 181-365 Days | Stock in the 181 to 365-day group |
| >= 366 Days | Stock aged 366 days or more |

**Date Duration selects age groups, not calendar dates.** There is no start-date/end-date picker here.

To show only the oldest stock, keep **>= 366 Days** checked and untick the other five. At least one age group and one branch must remain selected.

## 6. Understand the numbers and tables

### Read the summary cards

1. Look at **Grand Total** for the current displayed item count.
2. Read the smaller **units** figure below it for the stock quantity.
3. Look at the colored category cards to compare categories.
4. Tap a category card to select that category. Tap Grand Total to restore all main categories; other filters still apply.

### Read one item row

| Column | Simple meaning |
| --- | --- |
| Item Details | Product description |
| Unit | The stock unit, such as Nos. |
| Closing Qty | Sum of the currently selected age-group quantities for the item |
| Age columns | Quantity in each selected age group |
| ALM, HZT, and other branches | That branch's quantity; duration detail depends on the uploaded branch ageing data |
| Present At | Selected branches with a positive quantity for the selected ages |

**Example:** one model has 3 units aged 0-60 days and 2 units aged 366 days or more. With all age groups selected, Closing Qty is **5**. With only the oldest group selected, it is **2**. This is **1 item** with multiple units.

A dash **-** represents zero in numeric cells. In **Present At**, it means no selected location is listed.

Tap a colored category heading to open or close its tables. **Collapse all** hides the detail sections; **Expand all** opens them again. On a phone, swipe sideways inside a wide table to see more columns.

## 7. Find stock that needs attention

Try this example when you want to review the oldest stock at a branch. It is a review exercise, not an instruction to sell or transfer stock automatically.

### Example: oldest stock at ALM

1. Restore all main categories and **All Brands**.
2. Choose **All Item Categories** and empty the model search box.
3. Open **Branch** and select ALM. Untick the other branches.
4. Open **Date Duration** and keep only **>= 366 Days** checked.
5. Look for rows with a positive quantity in the **ALM** column.
6. Read the item description and check the original workbook or stock records.
7. Discuss any follow-up with the stock manager.

The on-screen branch control primarily controls the columns shown. Do not assume every row with a positive Closing Qty has stock at your selected branch. Read the branch quantity itself.

### If you see REVIEW or an unexpected result

- Ask the responsible person to check the item's category and brand assignment.
- Check the source item name and model number.
- Compare All Data ageing totals with branch ageing totals.
- If an old upload lacks branch ageing detail, ask for a fresh complete workbook upload.

The table has no general stock-quantity editing form. Correct the workbook and upload the complete corrected version through an authorized operator.

## 8. Download Excel, PDF, or an image

### Choose the format you need

| Menu option | Use it for |
| --- | --- |
| Excel Workbook | An editable .xlsx spreadsheet for further checking |
| PDF Document | A .pdf file for reading, sharing, or printing |
| Image | A .jpg snapshot of the report |

### Download directly to your computer

1. Check the category, brand, item category, and search text.
2. Check **Branch** and **Date Duration**.
3. Tap **Download Report**.
4. Choose **PDF Document** to download a PDF, or choose another format.
5. Wait while the button says **Preparing...**.
6. If your browser asks where to save, choose a folder and save the file.
7. Otherwise, find it in your browser's downloads or the computer's Downloads folder.
8. Open the file and check the items and quantities before sharing it.

Your filter selections are sent with the download. Category and brand appear as section headings in the exported report.

**Check branch-only exports:** the export also filters items by selected branch stock, while the on-screen branch selector mainly changes visible columns. Compare individual branch quantities; do not assume Closing Qty is the selected branch total or that the visible row count must match.

If a large Image export arrives as a **.zip**, open the ZIP to find separate category JPG images. This is expected for a report too large for one image.

## 9. Correct data and reset filters

### Replace an incorrect workbook

1. Find the mistake in the source workbook.
2. Ask the responsible person to correct it.
3. Prepare the complete workbook with All Data and the required branch sheets.
4. Keep a copy of the previous workbook if it is needed for reference.
5. Use **Upload & Process** to import the corrected workbook.
6. Read the upload warnings and check the corrected item again.

**The new upload replaces every previous Ageing Stock item and its upload record.** It does not add a separate historical snapshot.

### Know which Clear button you are using

| Button location | What Clear does |
| --- | --- |
| Inside the category menu | Leaves the first category, HA, selected |
| Inside the Branch menu | Leaves the first branch, ALM, selected |
| Inside Date Duration | Leaves the first group, 0-60 Days, selected |
| Beside Upload & Process | Opens confirmation to delete the entire Ageing Stock dataset |

To restore the full view, use **Select all** in the category, Branch, and Date Duration menus. Restore **All Brands**, **All Item Categories**, and empty the search box.

If you accidentally open **Clear all Ageing Stock Analysis data?**, tap **Cancel**. Confirming **Clear** removes all uploaded items and upload records; the screen has no undo action. Your filters do not limit deletion.

## 10. Get help and finish your day

| Problem | What to try |
| --- | --- |
| No stock data uploaded | Ask the administrator to upload the complete workbook. |
| No matching items | Widen categories, brand, search, and age groups before assuming stock is missing. |
| Choose a file first | Select the workbook, then tap Upload & Process. |
| Could not read the Excel file | Open it in Excel and save a genuine .xlsx copy. Check that it is not empty or damaged. |
| Missing sheets | Check branch sheet names, content, and readable stock rows. |
| Items absent or totals lower than source | Check Nos. units, PWH/Vault exclusions, and agreement between ageing and branch quantities. |
| Download failed | Check the connection, retry, and read the message shown. |
| Access denied or upload controls missing | Ask the administrator to check your role. |
| Returned to sign-in | Sign in again and reopen Ageing Stock. |

When asking for help, provide the filename, filter selections, item/model, and exact error message. Do not include your password.

### Daily checklist

- [ ] Open Ageing Stock and confirm the correct upload is available.
- [ ] Check missing-sheet and category-review messages, if shown.
- [ ] Choose categories, brand, branch columns, and stock ages.
- [ ] Compare item counts with unit quantities.
- [ ] Check the branch quantity for items needing attention.
- [ ] Download and open the report you need.
- [ ] Tap **Workspace** to return Home, or **Log out** when finished.

**Log out** signs you out directly on this page.

Documentation basis: `static/ageing_stock.html`, `static/login.html`, `main.py`, and `auth.py`. This guide describes the source reviewed on 12 September 2026; the live deployment may differ. Illustrations are teaching examples, not live screenshots or inventory reports.
