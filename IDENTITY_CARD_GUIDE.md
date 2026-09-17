# Identity Card

Open **Home > Identity Card** after restarting the ERP server with these changes.
The page is available at `/identity-card` (or `/erp/identity-card` when hosted under `/erp`).

- Admin, Owner, and HR can view and correct every eligible user's card.
- Other eligible users can view and print only their own card.
- Brand Promoters (`BrandPartner`) are excluded from the directory and API.
- Both active and inactive users appear in the management directory; use the status filter when needed.

## Correct a card

Select a person. Edit Employee name, Designation, or Mobile number. Employee ID is generated automatically and is read-only.
Upload a JPG, PNG, or WebP photo up to 3 MB and 16 megapixels. Photos are centre-cropped into a square and displayed in a circle.
Click **Save card details**. Changes persist in the database. **Discard changes** restores the saved card.

New cards start with the account's full name (or username), a designation derived from its role, and an outlet-based ID such as `IDS-HZT-26001`. Here `HZT` is Hazratganj, `26` is the issuance year 2026, and `001` is the outlet's sequence number for that year. Each outlet/year starts at 001; numbers grow beyond 999 without truncation. Missing photos and mobile numbers are clearly labelled.

Known outlet abbreviations are HZT, ALM, ASH, GNG, VKN, WH, and HO. Other outlets use their configured code, or OUT plus their store ID if no code exists. Users without a store use UNASSIGNED. Set their outlet in account management before issuing the card.

Opening Identity Card assigns numbers to eligible users in account-ID order and converts legacy IDs while preserving all other card details. IDs are stored and do not change on a year rollover. Moving a user to a different outlet issues the next number for that outlet and the current year. Sequence counters survive account deletion and transfers so issued serial numbers are not reused. Brand Promoters do not receive numbers.

Card corrections are separate from login names, user profile names, roles, and account permissions. The company name, head-office address, and email on the back use the supplied company details.

## Print or save a PDF

Save or discard edits first. Choose **Print / Save PDF** for the selected employee, or **Print visible cards** for the directory's current search and status filter. In the browser print dialog, choose a printer or **Save as PDF**.

The A4 layout places the front and back side by side, with two employees per page. It is intended for cutting and assembly, not automatic duplex alignment. Use 100% scale, disable browser headers/footers, and enable background graphics if the browser requires it. Each side is approximately 54 × 85.6 mm.

## Storage and access

`identity_cards.py` implements the authenticated API. The `identity_cards` and `identity_card_sequences` tables are created through the existing SQLAlchemy startup process. No existing user columns are changed. Photos are validated and re-encoded as 480 × 480 JPEG images, stored with the card rather than in a publicly accessible uploads folder. Include both tables in normal database backups.

## Validation

- `tests/test_identity_cards.py`: isolated API tests for scope, permissions, promoter exclusion, corrections, unique IDs, field validation, and photo handling.
- `tests/identity-card-ui.cjs`: browser checks against `tmp/identity-preview.cjs` on port 8769 and a dedicated Chrome debugging instance on port 9231. The preview uses fictional employees, never the production database.
