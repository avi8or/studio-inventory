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
| Build a calculated Estimate | ERPNext Quotation and Quotation Item |
| Accept an Estimate as a Client Order | ERPNext Sales Order |

Roll Items use `Foot` as Stock UOM, and Sheet Items use `Sheet` as Stock UOM.
Both use one reusable Item barcode and Item-specific purchase UOM conversions,
such as `Roll 39.37 Foot` or `Pack 25 Sheet`. The scanner remains a standard
HID keyboard device; no browser extension or vendor SDK is required.

## Print pricing and Estimates

Open **Price calculator** from Studio Inventory, choose **Price Calculator**
from the Frappe CRM logo menu on any CRM page, or use the shortcut on a CRM
Estimate Request (`CRM Deal`). A calculator opened from an Estimate Request
can create a draft **Estimate** containing the calculated line. The global
calculator remains temporary and does not create or change an Inquiry,
Estimate Request, Estimate, or inventory record. Both paths use
the same server-side paper costs, pricing settings, margin warning, and
consumption estimate as calculated Estimate rows.

The calculator extends the native ERPNext Quotation form, displayed to users
as **Estimate**. Choose **Add > Add
Calculated Print**, then select a sellable print Item, a Paper Item variant,
dimensions, border, quantity, ink cost, and production time. The server
calculates the unit rate, internal cost, margin, physical fit, and estimated
Sheet or Foot consumption. The resulting row remains a normal Quotation Item,
so ERPNext continues to own taxes, discounts, terms, printing, amendments, and
Sales Order conversion. Sales Order is displayed as **Client Order**; no
separate job or fulfillment ledger is created.

The customer-facing base rate uses the finished print and selected paper cost,
not the width of the loaded roll. Internal paper cost and margin use the actual
estimated sheets or roll length consumed, so unused stock width reduces margin
without making the same print more expensive merely because it was loaded on a
wider roll. A model or conditional rule can optionally enforce a minimum
pricing margin based on finished-area cost, while the realized-margin warning
continues to include actual stock waste.

`Studio Pricing Settings` selects the active `Studio Pricing Model` and holds
the default sellable print Item, Company, and paper-cost Buying Price List.
Pricing Models contain the base constants and ordered conditional rules.
Rules can match a Paper Item, Brand, Sheet or Roll form, exact size, artwork
area, normalized paper-cost range, or quantity, then set, add, or multiply a
controlled pricing parameter. A migration creates `Standard Pricing` from the
previous settings without changing existing prices.

Rules run in ascending priority. Matching parameter rules adjust the base
model first; Minimum Unit Price and Raw Unit Price adjustments run during
pricing; the pricing-margin guardrail runs next; and an explicit Final Unit
Price adjustment runs last. If two matching rules change the same target at
the same priority, the calculation stops and names the conflict instead of
silently choosing one.

Examples:

- Set `Minimum Unit Price` to `20` for an exact `8 × 10` size on one Paper
  Item.
- Multiply `Material Markup Multiplier` by `1.15` for paper costs within a
  premium normalized-cost range.
- Set `Minimum Pricing Margin` for one paper, Brand, size range, or any
  combination of those conditions.

Every calculated line stores the model name, revision, resolved values,
matched rules, cost source, and calculation result. Saving an older draft
reuses that snapshot instead of silently applying a newly edited model.

Valid ERPNext Item Prices are
normalized through the paper Item's UOM conversion and `Sheet Size` or `Roll
Width` attribute. A Sales Manager or System Manager can enter a cost-per-square-
inch override when a current Item Price has not been loaded yet.

When the standalone Frappe CRM app is installed, the app adds a **Create
Estimate** action to Estimate Requests and links the native Quotation back to
the CRM Deal.
It does not enable Frappe CRM's broad Item-to-Product synchronization. A
Customer is created or linked only when an accepted Estimate becomes a Client
Order.

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
