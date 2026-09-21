# Purchase order receipt and verification

1. MIS sends the approved PO using the existing email action. The PO loop shows **50%**. Sending alone never completes it.
2. Open **Receive / match / verify** on the sent PO. Warehouse logistics staff (LogisticManager or Supervisor) can enter a warehouse or outlet receipt. Staff with an assigned outlet can enter receipts for that outlet. MIS, Admin and Owner can also enter receipts.
3. Enter the invoice or delivery challan number, receiving location, date and actual quantities in this delivery. Multiple partial deliveries, including deliveries at different locations, accumulate against the same PO.
4. Review the item-by-item match. Shortages and excess quantities keep the PO open. An incorrect receipt can be voided by its author or a verifier and re-entered; the original remains in the history.
5. **Accounts, MIS Executive, warehouse staff (LogisticManager or Supervisor), or the receiving outlet manager** selects **Verify and complete PO loop** after reviewing the goods and documents. Outlet manager roles are AsstSalesManager, StoreManager and Branch Manager, with an assigned outlet; they may verify only POs whose active receipts are all at that outlet. Accounts, MIS Executive or warehouse staff handle mixed-location POs. Admin and Owner do not have verification permission. Every item must match exactly. The loop then shows **100% / Completed**, including the verifier and time.

Sent PO details are locked so receipt matching always uses the original sent order. Sent POs cannot be deleted. Completed POs cannot accept or void receipts. Existing sent orders begin at 50% until receipts are entered and verified. Receipt entry does not create stock or accounting ledger postings.

Brand Partner access remains restricted. An account without an assigned outlet needs a warehouse logistics role to enter warehouse receipts. Receipt matching uses the selected PO item and its model/variant; receipt document files and individual serial-number scanning are not part of this entry screen.

## Validation

Install `requirements-dev.txt` to run the isolated API tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_po_receiving.py -v
node --test tests/purchase-order-access.test.cjs tests/purchase-order-pdf.test.cjs
```
