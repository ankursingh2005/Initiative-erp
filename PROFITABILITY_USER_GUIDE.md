# Daily Profitability — Easy Step-by-Step User Guide

For Initiative ERP users. No computer knowledge is needed.

This guide covers the **Daily Profitability** part of the project: opening it, uploading sales, checking results, and downloading reports. Instructions are based on the project files reviewed on 12 September 2026; the live website may have a different version.

## 1. Before you start

Keep these things ready:

- A phone or computer with an internet connection.
- Your Initiative ERP username or email and password.
- If you upload data: the complete Busy sales export for the dates you need.

**Tap** means touch a button once on a phone. **Click** means select it with your mouse on a computer. They do the same job here.

If someone has already uploaded the sales, go straight to step 4 after signing in.

## 2. Open the website and sign in

1. Open your internet browser.
2. Type **https://erp.initiative.co.in** in the address bar.
3. Open the website.
4. Find **Username / Email**.
5. Enter your username or email.
6. Find **Password** and enter your password.
7. Tap **Sign in**.

**You should see:** the Home page with the modules your account can use.

If you do not have an account, ask your administrator for access.

### If you forgot your password

1. On the sign-in page, tap **Forgot password?**
2. Enter your registered email.
3. Tap **Send Code**.
4. Check your email for the verification code.
5. Enter the code, your new password, and the same new password again.
6. Follow the reset button shown on the screen.
7. Sign in using your new password.

If the email does not arrive, check Spam and ask your administrator for help.

## 3. Open Daily Profitability

1. On Home, find **Daily Profitability** in the navigation. On a small screen, open the navigation menu if needed.
2. Tap **Daily Profitability**.
3. Wait for the page to load.

**You should see:** **Category-wise profitability report**, a **Filters** box, and either your results or a message saying no data is available.

The direct page address is `https://erp.initiative.co.in/daily-profitability`.

## 4. Upload the sales file — only if you handle uploads

If you do not see **Upload a Busy export**, ask the person who manages uploads to do this part.

### Prepare the file

1. Ask the person who uses Busy to export the sales for the required dates.
2. Ask for a complete export covering all stores needed for those dates.
3. Check that the file has sales information such as **Date**, **Vch No**, **Item**, **Qty**, **Sales Amt**, **Cost Amt**, **Profit/Loss**, and **Profit %**.
4. Save the file somewhere you can find it again.

The file picker accepts Excel (`.xlsx`, `.xls`), CSV, PDF, JPG, JPEG, and PNG. A file must contain readable sales rows; selecting an accepted file type does not guarantee that its contents can be read.

**Before uploading:** a new upload replaces existing records between the earliest and latest valid sales dates in that file, including dates between them. This replacement is not limited to your selected store or category. Use a complete export for that period. A partial file can remove other records from the same period.

### Upload it

1. Find **Upload a Busy export**.
2. Tap **Choose file...**.
3. Find your saved export.
4. Select the file.
5. Check that the correct filename appears.
6. Tap **Upload & Process**.
7. Wait while the screen says **Uploading and processing...**.
8. Read the result message.

**You should see:** a message like `Processed sales.xlsx: 120 row(s) loaded`.

The filename and number will be different for your file. If the message says rows were **skipped**, some rows were not loaded. Ask the uploader or administrator to check the source file before relying on the totals.

After upload, the page selects the latest available sales date. Always check the dates before reading the report.

The same uploaded data is also used by **Interval Sales Analytics Upload** and **Scheme-Matched Sales**. You do not need to upload the same file separately in both places.

## 5. Choose the dates you want to see

### To see one day

1. Find **Filters**.
2. Set **Start Date** to the day you want.
3. Set **End Date** to the same day.
4. Wait for the results to update.

Example: to see 10 September 2026, use 10 September 2026 in both boxes.

### To see several days

1. Set **Start Date** to the first day.
2. Set **End Date** to the last day.
3. Wait for the results to update.

Example: to see 1–10 September, use 1 September as the start and 10 September as the end.

### To choose quickly

Tap **Quick range** and select:

| Option | What it selects |
| --- | --- |
| Today | Today's date |
| This Week | Sunday through today |
| This Month | The first day of this month through today |
| Custom | Dates you choose yourself |

**You should see:** results for your chosen period, if sales have been uploaded for it. Opening the page normally selects the latest uploaded date, which may be older than today.

## 6. Choose a store or category

1. Find **Category**.
2. Select a category, or choose **All Categories**.
3. Find **Store**.
4. Select a store, or choose **All Stores**.
5. Wait for the results to update.

Example: choose one store and one category to see only that combination for your selected dates.

To return to the full view, select **All Categories** and **All Stores**. Your dates stay as selected.

## 7. Understand the big numbers

| Screen label | Simple meaning |
| --- | --- |
| Total Sales | The selling amount for the selected results |
| Total Cost | The cost amount for those results |
| Total Margin | Sales minus cost |
| Margin % | Margin divided by cost, multiplied by 100 |
| Line Items | Number of processed item entries; this is not the quantity of units sold |
| Loss-Making Items | Number of item entries where cost is greater than sales |

### A small example

Imagine the displayed sales are **Rs. 1,180** and the displayed cost is **Rs. 944**.

1. Subtract 944 from 1,180.
2. The margin is **Rs. 236**.
3. Divide 236 by 944, then multiply by 100.
4. The app shows **25%**.

The app calculates its percentage using **cost** as the base. If cost is zero, the current calculation shows 0%; check the cost data before interpreting that percentage.

These numbers show sales minus product cost. They do not establish the business's final profit after expenses such as salary, rent, and electricity.

## 8. Read the chart and tables

1. Look at **Sales & Margin by Category** to compare categories.
2. Look at **By Store** to compare store sales and margins.
3. Look at **Top Profitable Items** for the 10 highest-margin entries.
4. Look at **Loss-Making Items** for up to 15 entries with the largest losses.
5. If **Review notes** appears, ask the person responsible for the export to check the listed vouchers and cost allocation.

Categories are assigned from item names, and stores are derived from voucher numbers. Check unexpected results against your original records. Vouchers containing `PW` are excluded from this profitability calculation. Related product and spare lines may be combined, so the item count can differ from the source row count.

## 9. See every item in your selection

1. Check your dates, category, and store.
2. Tap **View Items**.
3. Look at the **Item Details** table.
4. Find the product you want to check.
5. Read its **Sale**, **Cost**, **Margin**, and **PL %**.
6. Use **Vch. No.** to find the matching voucher in the source records.
7. Tap **Hide Items** when finished.

**You should see:** the full item list for your current filters. Loss-making rows are red. **PL %** is the item's profit/loss percentage based on cost.

## 10. Download a report

Both download buttons use your selected dates, category, and store.

| Button | What you receive | Amounts used |
| --- | --- | --- |
| Profitability Report | An Excel workbook with category details and a dashboard | Includes the app's estimated 18% GST uplift |
| Daily Report | A division/outlet daily Excel report | Uses the original GST-exclusive amounts |

### Download your chosen report

1. Set the dates you need.
2. Choose your category and store, or select all.
3. Check the results on the screen.
4. Tap **Profitability Report** or **Daily Report**.
5. Wait for the download to finish.
6. Open the downloaded `.xlsx` file with an app that can read Excel workbooks.
7. Check the period and totals before using or sharing it.

Look in your browser's downloads if you cannot find the file.

### Why the two reports have different amounts

The dashboard and **Profitability Report** multiply sales and cost by **1.18**. The separate **Daily Report** removes that uplift.

Example: source sales of Rs. 1,000 and cost of Rs. 800 appear as Rs. 1,180 and Rs. 944 on the dashboard. The Daily Report uses Rs. 1,000 and Rs. 800. The percentage remains 25% in this example.

This is the application's fixed estimate. Compare reports using the same GST basis.

## 11. Correct a wrong upload

1. Find the mistake in the original sales export.
2. Ask the responsible person to correct the source and prepare a complete replacement export for the affected period.
3. Check the earliest and latest dates in the replacement file.
4. Confirm that it contains all the sales and stores required for that entire period.
5. Upload it using **Choose file...** and **Upload & Process**.
6. Check the loaded/skipped message.
7. Set the filters again and verify the corrected amounts.

The upload replaces records across that date span. Do not use **Clear Data** as a normal step before uploading.

### What Clear Data does

**Clear Data deletes all uploaded interval sales across all dates.** Your filters do not limit what is deleted. It also clears the data used by Scheme-Matched Sales.

If you opened this by mistake, tap **Cancel**. Use it only when the person responsible for the complete dataset intends to remove everything and has the files needed to restore it.

## 12. Finish and sign out

1. Tap **Back** to return to Home if you have more work.
2. When finished, tap **Logout**.
3. In the confirmation box, tap **Logout** again.

**You should see:** the sign-in page.

## 13. If something goes wrong

| Problem | What to do |
| --- | --- |
| No data for this range/filter | Choose a date covered by the upload. Try All Categories and All Stores. |
| Today is empty | Today's sales may not be uploaded yet. Check the available dates. |
| Upload area is missing | Ask your administrator or MIS upload operator to upload the file. |
| Access denied | Ask your administrator to check your account permissions. |
| Upload button cannot be tapped | Choose a file first. |
| No readable sales rows found | Check that the export contains the expected sales columns and readable rows. |
| Some rows were skipped | Ask the uploader to correct the file and verify the replacement period. |
| Totals look wrong | Check dates, store, category, skipped rows, and the report's GST basis. |
| A store or category looks wrong | Check voucher numbers and item names in the source file. |
| Report will not download | Check that your current selection contains data and read any message shown. |
| Sign-in page appears again | Sign in again, then reopen Daily Profitability. |

When asking for help, provide the page name, chosen dates, store/category, and the exact message you see. Never include your password.

## 14. Your daily checklist

- [ ] Sign in and open Daily Profitability.
- [ ] Upload the complete export if this is your responsibility.
- [ ] Check the upload result for skipped rows.
- [ ] Choose the correct dates.
- [ ] Choose the correct category and store.
- [ ] Read Total Sales, Total Cost, and Total Margin.
- [ ] Check loss-making items and review notes.
- [ ] Download the report with the GST basis you need.
- [ ] Open the file and check it.
- [ ] Log out when finished.

---

Documentation check: button names and behavior were checked against `static/login.html`, `static/home.html`, `static/daily_profitability.html`, and the upload/report handlers in `main.py`. This guide was checked against source code; it is not a record of testing the live website.
