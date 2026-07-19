# Studio Inventory

Studio Inventory is a first-class Frappe application for fast receiving,
consumption, correction, barcode-label workflows, and dimension-based print
pricing. It deliberately does not keep a second inventory or quotation ledger.

| App action | Native ERPNext record |
|---|---|
| Receive sheets or rolls | Purchase Receipt |
| Consume paper | Stock Entry / Material Issue |
| Set an explicit remaining quantity | Stock Reconciliation |
| Undo a recent app action | Cancellation of the submitted native record |
| Build a calculated print quote | ERPNext Quotation and Quotation Item |
| Accept a calculated quote | ERPNext Sales Order |

Roll Items use `Foot` as Stock UOM, and Sheet Items use `Sheet` as Stock UOM.
Both use one reusable Item barcode and Item-specific purchase UOM conversions,
such as `Roll 39.37 Foot` or `Pack 25 Sheet`. The scanner remains a standard
HID keyboard device; no browser extension or vendor SDK is required.

## Print pricing and quotations

The calculator extends the native ERPNext Quotation form. Choose **Add > Add
Calculated Print**, then select a sellable print Item, a Paper Item variant,
dimensions, border, quantity, ink cost, and production time. The server
calculates the unit rate, internal cost, margin, physical fit, and estimated
Sheet or Foot consumption. The resulting row remains a normal Quotation Item,
so ERPNext continues to own taxes, discounts, terms, printing, amendments, and
Sales Order conversion.

`Studio Pricing Settings` holds the pricing constants, default sellable print
Item, Company, and paper-cost Buying Price List. Valid ERPNext Item Prices are
normalized through the paper Item's UOM conversion and `Sheet Size` or `Roll
Width` attribute. A Sales Manager or System Manager can enter a cost-per-square-
inch override when a current Item Price has not been loaded yet.

When the standalone Frappe CRM app is installed, the app adds a **Create Print
Quotation** action to CRM Deals and links the native Quotation back to the Deal.
It does not enable Frappe CRM's broad Item-to-Product synchronization. A
Customer is created or linked only when an accepted CRM Deal quotation becomes
a Sales Order.

The Labels view assigns and prints reusable fixed-length Code 128 Item barcodes
for rolls, sheets, and card sets. The generated `INV######` value is stored in
the native Item Barcodes table without replacing manufacturer or legacy
barcodes. Rolls are counted in feet, while packs are counted in their Stock
UOM. Multiple physical packages of the same Item intentionally share one
scannable Item barcode and one aggregate warehouse balance.

The Command card view prints a letter-size scanner control sheet intended for
matte lamination. Its QR codes open the app or deep-link directly to Receive,
Consume, or Count. When one of those same URLs is scanned while the app's scan
field is focused, the app switches modes instead of sending the URL to ERPNext
as an Item lookup. Code 128 commands select amount-used versus ending-balance
entry, provide a numeric keypad, confirm or cancel a prepared transaction, and
undo the latest app-created transaction. Confirm still calls the normal app
method and cannot bypass ERPNext validation or permissions. Scanner commands
use the `SI:` namespace.

Supported deep links are:

```text
/studio-inventory?mode=receive
/studio-inventory?mode=consume
/studio-inventory?mode=count
```

## Local checks

```sh
python3 -m unittest discover -s tests -v
pnpm --dir frontend install --ignore-scripts
pnpm --dir frontend test
pnpm --dir frontend build
```

The committed Yarn lockfiles and root build script are intentional: Bench 6
installs and runs custom-app assets with Yarn. The pnpm commands above are the
equivalent project-local development workflow used in this repository.

## Standalone command card

The installed app can print the command card directly. To generate a PDF before
installation, use an isolated Python environment and pass the ERPNext site
origin explicitly:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ".[command-card]"
.venv/bin/python scripts/generate_command_card.py \
  --origin https://erp.example.com \
  --brand "Example Studio"
```

The optional brand is used only in the generated PDF. Site URLs and business
names are not stored in the repository.

## Frappe installation

The target bench must run Frappe and ERPNext 16.x. After this directory is
published as its own Git repository:

```sh
bench get-app <repository-url>
bench --site <site-name> install-app studio_inventory
bench build --app studio_inventory
bench --site <site-name> migrate
```

Frappe Cloud public benches cannot install custom apps. Move the site to a
private bench before running these steps. See [DEPLOYMENT.md](DEPLOYMENT.md)
for the prerequisites, roles, and smoke-test sequence.

## Permissions

The app does not bypass ERPNext roles. A user needs create and submit/cancel
permission for the native document used by the action:

- Purchase Receipt for Receive
- Stock Entry for Consume
- Stock Reconciliation for Count
- Quotation for calculated print quotes
- Customer create permission when converting a CRM Deal quotation to a Sales Order

Item, Batch, Warehouse, Supplier, and account permissions still apply.
Calculated quotes also require read access to Item and Item Price. Only Sales
Manager and System Manager roles may override a missing paper cost.

## Current constraint

Receiving assumes the supplier transaction is in the Company's default
currency. Add explicit exchange-rate input before using the app for a
foreign-currency supplier.

## Author and license

Studio Inventory was created by Tyler Miller and is available under the MIT
License.
