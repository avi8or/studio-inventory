# Studio Inventory deployment

Studio Inventory must be installed on a bench that permits custom apps. On
Frappe Cloud, public benches do not permit custom app installation; move the
site to a private bench first.

## 1. Prepare the site

- Run Frappe and ERPNext 16.x on the target private bench.
- If the standalone `crm` app is installed, keep it installed. Studio Inventory
  does not replace, duplicate, or synchronize CRM records.
- In Stock Settings, enable the legacy Serial/Batch fields used by scanner
  rows (`Use Serial / Batch Fields`).
- Enable UOM conversion through each Item's UOM table.
- Configure a non-group Warehouse, an active Supplier, Company default
  currency, Company cost center, and Stock Adjustment account.

## 2. Verify the Item model

Roll variants:

- Stock UOM: `Foot`
- Maintain Stock: enabled
- Has Batch No: enabled
- One Item UOM per purchasable roll, for example `Roll 50 Foot` with conversion
  factor `50`
- A case UOM may use `Case 2 × 50 Foot Rolls` with conversion factor `100`;
  Studio Inventory creates two physical Batches per case

Sheet and card-set variants:

- Stock UOM: `Sheet` or `Card Set`
- Maintain Stock: enabled
- Has Batch No: disabled
- Purchase UOMs such as `Pack 25 Sheet` or `Pack 100 Sheet` use their sheet
  counts as conversion factors

Manufacturer barcodes belong in the Item's Barcode table. Studio Inventory
also accepts the Item code. For consumption and counting, a batched roll must
be scanned by its unique Studio Inventory Batch label.

The Labels view can print a reusable Code 128 Item/shelf label for every active
Sheet or Card Set Item, including Items with a zero balance. It also prints one
unique Code 128 Batch label for each positive-balance physical roll.

## 3. Publish and install

Publish this directory as its own Git repository, add that repository as a
custom app in Frappe Cloud, and install it on the site. The equivalent bench
commands are:

```sh
bench get-app <repository-url>
bench --site <site-name> install-app studio_inventory
bench build --app studio_inventory
bench --site <site-name> migrate
```

After installation, open `/studio-inventory` or choose Studio Inventory from
the Frappe app switcher.

## 4. Assign native permissions

The app deliberately relies on ERPNext's own permissions. Give operators only
the actions they need:

| Studio action | Native DocType | Required permissions |
|---|---|---|
| Receive | Purchase Receipt | Create, Submit |
| Consume | Stock Entry | Create, Submit |
| Count | Stock Reconciliation | Create, Submit |
| Quick undo | The created native document | Cancel |

Read permission and User Permissions must also allow the selected Company,
Warehouse, Item, Batch, and Supplier. The app does not use `ignore_permissions`.

## 5. Configure the scanner and labels

- Use a 1D/2D scanner in Bluetooth, USB, or 2.4G HID keyboard mode.
- Configure a carriage-return/Enter suffix.
- Print the generated roll labels as Code 128. The human-readable Batch ID is
  also printed below the barcode.
- No ERPNext mobile app, browser extension, or scanner SDK is required; the
  responsive web page works in a signed-in mobile browser.

## 6. Run the live smoke test

Use a temporary test Warehouse or clearly marked test Items before touching
real balances.

1. Receive one sheet pack and confirm its Purchase Receipt and converted Sheet
   quantity.
2. Receive one roll and confirm one `SIB.######` Batch and one printable label.
3. Consume a measured length from that Batch and confirm a Material Issue.
4. Consume again using an explicit ending balance and confirm the calculated
   difference.
5. Record a physical count and confirm a Stock Reconciliation.
6. Use quick undo within 15 minutes and confirm the native transaction is
   cancelled, not deleted.
7. Confirm Stock Ledger and accounting entries match the submitted native
   documents.

Do not run this smoke test against live inventory until the site owner
explicitly approves production writes.
