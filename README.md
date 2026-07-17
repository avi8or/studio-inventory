# Studio Inventory

Studio Inventory is a first-class Frappe application for fast receiving,
consumption, correction, and barcode-label workflows. It deliberately does not
keep a second inventory ledger.

| App action | Native ERPNext record |
|---|---|
| Receive sheets or rolls | Purchase Receipt |
| Consume paper | Stock Entry / Material Issue |
| Set an explicit remaining quantity | Stock Reconciliation |
| Undo a recent app action | Cancellation of the submitted native record |

Roll Items use `Foot` as Stock UOM and one ERPNext Batch per physical roll.
Sheet Items use `Sheet` as Stock UOM and Item-specific purchase UOM conversions
such as `Pack 25 Sheet`. The scanner remains a standard HID keyboard device;
no browser extension or vendor SDK is required.

The Labels view prints Code 128 Batch labels for individual rolls and reusable
Code 128 Item/shelf labels for sheets and card sets. Packs are counted in their
Stock UOM, so multiple packs of the same Item intentionally share one scannable
Item code.

The Command card view prints a letter-size scanner control sheet intended for
matte lamination. Its QR codes open the app or deep-link directly to Receive,
Consume, or Count. When one of those same URLs is scanned while the app's scan
field is focused, the app switches modes instead of sending the URL to ERPNext
as an Item lookup. Code 128 commands select amount-used versus ending-balance
entry, provide a numeric keypad, confirm or cancel a prepared transaction, and
undo the latest app-created transaction. Confirm still calls the normal app
method and cannot bypass ERPNext validation or permissions. Scanner commands
use the `SI:` namespace, and automatically created Batch IDs use the
`SIB.######` naming series.

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

Item, Batch, Warehouse, Supplier, and account permissions still apply.

## Current constraint

Receiving assumes the supplier transaction is in the Company's default
currency. Add explicit exchange-rate input before using the app for a
foreign-currency supplier.

## Author and license

Studio Inventory was created by Tyler Miller and is available under the MIT
License.
