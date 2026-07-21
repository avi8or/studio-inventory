# Studio Inventory deployment

Studio Inventory must be installed on a bench that permits custom apps. On
Frappe Cloud, public benches do not permit custom app installation; move the
site to a private bench first.

## 1. Prepare the site

- Run Frappe and ERPNext 16.x on the target private bench.
- If the standalone `crm` app is installed, keep it installed. Studio Inventory
  does not replace, duplicate, or synchronize CRM records.
- Enable UOM conversion through each Item's UOM table.
- Configure a non-group Warehouse, an active Supplier, Company default
  currency, Company cost center, and Stock Adjustment account.

## 2. Verify the Item model

Roll variants:

- Stock UOM: `Foot`
- Maintain Stock: enabled
- Has Batch No: disabled
- One Item UOM per purchasable roll, for example `Roll 50 Foot` with conversion
  factor `50`
- A case UOM may use `Case 2 × 50 Foot Rolls` with conversion factor `100`

Sheet and card-set variants:

- Stock UOM: `Sheet` or `Card Set`
- Maintain Stock: enabled
- Has Batch No: disabled
- Purchase UOMs such as `Pack 25 Sheet` or `Pack 100 Sheet` use their sheet
  counts as conversion factors

Manufacturer barcodes belong in the Item's Barcode table. Studio Inventory
also accepts the Item code. The same reusable Item barcode works for receiving,
consumption, and counting.

The Labels view can print a reusable Code 128 Item label for every active Paper
roll, Sheet, or Card Set Item, including Items with a zero balance.

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

## 4. Configure print pricing

Open `Studio Pricing Settings` and set:

- Company
- Default Print Item
- Paper Cost Price List, normally `Standard Buying`
- pricing constants and warning threshold

The Default Print Item should be an active sellable Item without variants. It
can be a non-stock service Item such as `Custom Fine Art Print`; paper remains
raw inventory and is not sold on the Quotation.

Add a valid Buying Item Price for each quotable Paper Item and purchase UOM.
For example, a $100 `Roll 50 Foot` price is normalized through its conversion
factor to a Foot cost and then through the variant's `Roll Width` to cost per
square inch. A `Pack 25 Sheet` price is normalized through the Sheet Size and
pack conversion. Merchant URL and Price Last Verified are optional fields on
Item Price.

If Frappe CRM is installed, run migrate after installing the app. The migration
adds the CRM Deal quotation link, a save-nothing **Price Calculator** action,
and the **Create Print Quotation** action. Leave
Frappe CRM's full ERPNext integration disabled unless its Item-to-Product sync
policy is acceptable for the site.

## 5. Assign native permissions

The app deliberately relies on ERPNext's own permissions. Give operators only
the actions they need:

| Studio action | Native DocType | Required permissions |
|---|---|---|
| Receive | Purchase Receipt | Create, Submit |
| Consume | Stock Entry | Create, Submit |
| Count | Stock Reconciliation | Create, Submit |
| Quick undo | The created native document | Cancel |
| Calculated quote | Quotation | Create, Read, Write, Submit |
| Quote to order | Sales Order and Customer | Create; Customer create when needed |

Read permission and User Permissions must also allow the selected Company,
Warehouse, Item, Item Price, and Supplier. The app does not bypass
transaction or Customer permissions.

## 6. Configure the scanner and labels

- Use a 1D/2D scanner in Bluetooth, USB, or 2.4G HID keyboard mode.
- Configure a carriage-return/Enter suffix.
- Print the generated reusable Item labels as Code 128. The human-readable
  Item code is also printed below the barcode.
- No ERPNext mobile app, browser extension, or scanner SDK is required; the
  responsive web page works in a signed-in mobile browser.

## 7. Run the live smoke test

Use a temporary test Warehouse or clearly marked test Items before touching
real balances.

1. Receive one sheet pack and confirm its Purchase Receipt and converted Sheet
   quantity.
2. Receive one roll and confirm the purchase UOM converts to the correct feet.
3. Scan the same Item label, consume a measured length, and confirm a Material Issue.
4. Consume again using an explicit ending balance and confirm the calculated
   difference.
5. Record a physical count and confirm a Stock Reconciliation.
6. Use quick undo within 15 minutes and confirm the native transaction is
   cancelled, not deleted.
7. Confirm Stock Ledger and accounting entries match the submitted native
   documents.
8. From a CRM Deal, create a print Quotation and add two calculated print lines.
9. Confirm taxes, discounts, terms, and the customer print format remain native
   ERPNext behavior.
10. Submit the Quotation, make a Sales Order, and confirm the CRM Deal link and
    calculated print specification carry forward.

Do not run this smoke test against live inventory until the site owner
explicitly approves production writes.
