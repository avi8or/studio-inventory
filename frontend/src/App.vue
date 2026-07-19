<script setup>
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import { frappeRequest } from "frappe-ui";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Check,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  ExternalLink,
  History,
  Info,
  Menu,
  PackageOpen,
  PackagePlus,
  PanelLeftClose,
  Printer,
  QrCode,
  RefreshCw,
  ScanBarcode,
  Search,
  Tags,
  X,
} from "@lucide/vue";
import BarcodeSvg from "./BarcodeSvg.vue";
import ScannerCommandCard from "./ScannerCommandCard.vue";
import { filterLabels, toggleVisibleSelection } from "./labelCatalog.js";
import {
  applyNumericKey,
  inventoryModeFromUrl,
  inventoryUrl,
  parseScannerCommand,
} from "./scannerCommands.js";

const VIEW_COPY = {
  receive: {
    title: "Receive",
    action: "New receipt",
    prompt: "Scan purchased inventory",
    help: "Scan a manufacturer barcode or ERPNext Item barcode.",
  },
  consume: {
    title: "Consume",
    action: "Material use",
    prompt: "Scan inventory to consume",
    help: "Scan the reusable Item label. Enter feet for rolls or sheets for packs.",
  },
  count: {
    title: "Count",
    action: "Correct balance",
    prompt: "Scan inventory to count",
    help: "Enter the actual measured balance and record the reason for any difference.",
  },
};

const NAV_ITEMS = [
  { id: "receive", label: "Receive", icon: PackagePlus, permission: "receive" },
  { id: "consume", label: "Consume", icon: ArrowUpFromLine, permission: "consume" },
  { id: "count", label: "Count", icon: ClipboardCheck, permission: "count" },
  { id: "activity", label: "Activity", icon: History },
  { id: "labels", label: "Labels", icon: Tags },
  { id: "commands", label: "Command card", icon: QrCode },
];

const options = ref({ warehouses: [], suppliers: [], permissions: {} });
const activeView = ref("receive");
const mobileOpen = ref(false);
const sidebarCollapsed = ref(false);
const scanInput = ref(null);
const scanValue = ref("");
const scanError = ref("");
const scanning = ref(false);
const selected = ref(null);
const quantityEntry = ref("");
const saving = ref(false);
const activity = ref([]);
const labels = ref([]);
const selectedLabelCodes = ref([]);
const labelQuery = ref("");
const activityQuery = ref("");
const toast = ref(null);
const lastTransaction = ref(null);

const form = reactive({
  warehouse: "",
  supplier: "",
  purchaseUom: "",
  purchaseUnits: 1,
  unitCost: null,
  mode: "amount",
  value: 0,
  reason: "Physical measurement",
});

const page = computed(() => {
  if (VIEW_COPY[activeView.value]) return VIEW_COPY[activeView.value];
  if (activeView.value === "activity") return { title: "Activity", action: "Inventory history" };
  if (activeView.value === "commands") return { title: "Command card", action: "Scanner controls" };
  return { title: "Labels", action: "Inventory labels" };
});

const appBaseUrl = computed(() => inventoryUrl(window.location.origin));

const visibleNav = computed(() =>
  NAV_ITEMS.filter((item) => !item.permission || options.value.permissions?.[item.permission]),
);

const selectedPurchaseUom = computed(() =>
  selected.value?.purchase_uoms?.find((row) => row.uom === form.purchaseUom),
);

const receiveStockQty = computed(
  () => Number(form.purchaseUnits || 0) * Number(selectedPurchaseUom.value?.conversion_factor || 0),
);

const physicalUnits = computed(
  () => Number(form.purchaseUnits || 0) * Number(selectedPurchaseUom.value?.physical_units || 1),
);

const quantityChange = computed(() => {
  const before = Number(selected.value?.current_qty || 0);
  if (activeView.value === "consume") {
    const entered = Math.max(0, Number(form.value || 0));
    const used = form.mode === "ending" ? Math.max(0, before - entered) : entered;
    return { before, change: -used, after: Math.max(0, before - used) };
  }
  const after = Math.max(0, Number(form.value || 0));
  return { before, change: after - before, after };
});

const transactionReady = computed(() => {
  if (!selected.value || !form.warehouse) return false;
  if (activeView.value === "receive") {
    const units = Number(form.purchaseUnits);
    const hasCost = form.unitCost !== null && form.unitCost !== "" && Number.isFinite(Number(form.unitCost));
    return Boolean(form.supplier && form.purchaseUom && Number.isInteger(units) && units >= 1 && hasCost);
  }
  if (activeView.value === "consume") {
    return quantityChange.value.change < 0 && Math.abs(quantityChange.value.change) <= quantityChange.value.before;
  }
  return quantityChange.value.after >= 0 && quantityChange.value.change !== 0;
});

const filteredActivity = computed(() => {
  const query = activityQuery.value.trim().toLowerCase();
  if (!query) return activity.value;
  return activity.value.filter((row) =>
    `${row.item_name} ${row.item_code} ${row.voucher_no} ${row.detail}`.toLowerCase().includes(query),
  );
});

const filteredLabels = computed(() => filterLabels(labels.value, labelQuery.value));

const allFilteredLabelsSelected = computed(
  () =>
    filteredLabels.value.length > 0 &&
    filteredLabels.value.every((label) => selectedLabelCodes.value.includes(label.label_code)),
);

const printableLabels = computed(() =>
  labels.value.filter((label) => selectedLabelCodes.value.includes(label.label_code)),
);

const printableLabelPages = computed(() => {
  const pages = [];
  for (let start = 0; start < printableLabels.value.length; start += 10) {
    pages.push(printableLabels.value.slice(start, start + 10));
  }
  return pages;
});

function formatNumber(value) {
  return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 3 });
}

function formatUnit(unit, quantity) {
  if (unit === "Foot") return "ft";
  if (Math.abs(quantity) === 1) return unit.toLowerCase();
  return `${unit.toLowerCase()}s`;
}

function apiError(error) {
  const messages = error?.messages || error?._server_messages;
  if (Array.isArray(messages) && messages.length) return messages.join(" ");
  return error?.message || "ERPNext could not complete the request.";
}

async function call(method, args = {}) {
  const response = await frappeRequest({
    url: `/api/method/studio_inventory.api.${method}`,
    method: "POST",
    params: args,
  });
  return response?.message ?? response;
}

async function focusScanner() {
  await nextTick();
  scanInput.value?.focus();
}

async function loadOptions() {
  options.value = await call("get_options");
  form.warehouse = options.value.default_warehouse || options.value.warehouses?.[0]?.name || "";
  form.supplier = options.value.default_supplier || "";
  if (!options.value.permissions?.receive) {
    activeView.value = visibleNav.value[0]?.id || "activity";
  }
}

async function loadActivity() {
  activity.value = await call("get_recent_activity", { limit: 50 });
}

async function loadLabels() {
  if (!form.warehouse) return;
  try {
    labels.value = await call("get_inventory_labels", { warehouse: form.warehouse });
    selectedLabelCodes.value = [];
  } catch (error) {
    labels.value = [];
    selectedLabelCodes.value = [];
    toast.value = { title: "Labels unavailable", message: apiError(error) };
  }
}

async function openLabels(codes = []) {
  activeView.value = "labels";
  updateModeUrl("labels");
  selected.value = null;
  quantityEntry.value = "";
  scanValue.value = "";
  scanError.value = "";
  mobileOpen.value = false;
  await loadLabels();
  selectedLabelCodes.value = codes.filter((code) => labels.value.some((label) => label.label_code === code));
}

function updateModeUrl(view) {
  const url = new URL(window.location.href);
  if (VIEW_COPY[view]) url.searchParams.set("mode", view);
  else url.searchParams.delete("mode");
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

async function navigate(view) {
  activeView.value = view;
  updateModeUrl(view);
  selected.value = null;
  quantityEntry.value = "";
  scanValue.value = "";
  scanError.value = "";
  mobileOpen.value = false;
  if (view === "activity") await loadActivity();
  if (view === "labels") await openLabels();
  if (VIEW_COPY[view]) await focusScanner();
}

function commandError(message) {
  scanError.value = message;
  toast.value = { title: "Scanner command unavailable", message };
}

function currentQuantityEntry() {
  return activeView.value === "receive" ? form.purchaseUnits : form.value;
}

function setQuantityEntry(value) {
  if (activeView.value === "receive") form.purchaseUnits = value;
  else form.value = value;
}

async function executeScannerCommand(command) {
  scanError.value = "";
  try {
    if (command.type === "open" || command.type === "mode") {
      const mode = command.mode;
      if (!mode) {
        toast.value = { title: "Studio Inventory ready", message: "Scan an inventory label or a mode command." };
        return;
      }
      if (!options.value.permissions?.[mode]) {
        commandError(`You do not have permission to use ${VIEW_COPY[mode].title}.`);
        return;
      }
      await navigate(mode);
      toast.value = { title: `${VIEW_COPY[mode].title} mode`, message: VIEW_COPY[mode].prompt };
      return;
    }

    if (command.type === "entry") {
      if (activeView.value !== "consume" || !selected.value) {
        commandError("Scan a roll or sheet Item in Consume before choosing its entry method.");
        return;
      }
      form.mode = command.mode;
      quantityEntry.value = "";
      toast.value = {
        title: command.mode === "amount" ? "Enter amount used" : "Enter ending balance",
        message: `Use the command-card keypad, then scan Confirm.`,
      };
      return;
    }

    if (command.type === "key") {
      if (!selected.value || !VIEW_COPY[activeView.value]) {
        commandError("Scan an inventory label before entering a quantity.");
        return;
      }
      const allowDecimal = activeView.value !== "receive" && selected.value.stock_uom === "Foot";
      if (command.key === "." && !allowDecimal) {
        commandError("This quantity must be a whole number.");
        return;
      }
      let current = quantityEntry.value;
      if (command.key === "backspace" && !current) current = String(currentQuantityEntry() ?? "");
      const next = applyNumericKey(current, command.key, { allowDecimal });
      quantityEntry.value = next;
      setQuantityEntry(Number(next || 0));
      return;
    }

    if (command.type !== "action") return;
    if (command.action === "cancel") {
      selected.value = null;
      quantityEntry.value = "";
      toast.value = { title: "Entry cleared", message: "No inventory transaction was created." };
      return;
    }
    if (command.action === "undo") {
      if (!lastTransaction.value) {
        commandError("There is no recent Studio Inventory transaction available to undo.");
        return;
      }
      await undoTransaction();
      return;
    }
    if (!selected.value) {
      commandError("Scan an inventory label before confirming.");
      return;
    }
    if (!transactionReady.value) {
      commandError("Complete the required transaction fields before confirming.");
      return;
    }
    await confirmTransaction();
  } finally {
    await focusScanner();
  }
}

async function resolveScan() {
  const code = scanValue.value.trim();
  if (!code) return;
  const command = parseScannerCommand(code, window.location.origin);
  if (command) {
    scanValue.value = "";
    await executeScannerCommand(command);
    return;
  }
  scanning.value = true;
  scanError.value = "";
  try {
    const result = await call("resolve_scan", {
      code,
      action: activeView.value,
      warehouse: form.warehouse,
    });
    selected.value = result;
    quantityEntry.value = "";
    form.warehouse = result.warehouse;
    form.purchaseUnits = 1;
    form.unitCost = null;
    form.purchaseUom =
      result.purchase_uoms.find((row) => row.uom === result.barcode_uom)?.uom ||
      result.purchase_uoms.find((row) => row.uom === result.default_purchase_uom)?.uom ||
      result.purchase_uoms.find((row) => row.uom !== result.stock_uom)?.uom ||
      result.purchase_uoms[0]?.uom ||
      "";
    form.mode = "amount";
    form.value = activeView.value === "count" ? result.current_qty : 0;
    form.reason = "Physical measurement";
    scanValue.value = "";
  } catch (error) {
    scanError.value = apiError(error);
  } finally {
    scanning.value = false;
    await focusScanner();
  }
}

async function confirmTransaction() {
  if (!selected.value || saving.value) return;
  saving.value = true;
  scanError.value = "";
  try {
    let result;
    if (activeView.value === "receive") {
      result = await call("receive_inventory", {
        payload: {
          item_code: selected.value.item_code,
          warehouse: form.warehouse,
          supplier: form.supplier,
          purchase_uom: form.purchaseUom,
          purchase_units: form.purchaseUnits,
          unit_cost: form.unitCost,
        },
      });
    } else if (activeView.value === "consume") {
      result = await call("consume_inventory", {
        payload: {
          item_code: selected.value.item_code,
          warehouse: form.warehouse,
          batch_no: selected.value.batch_no,
          mode: form.mode,
          value: form.value,
        },
      });
    } else {
      result = await call("reconcile_inventory", {
        payload: {
          item_code: selected.value.item_code,
          warehouse: form.warehouse,
          batch_no: selected.value.batch_no,
          actual: form.value,
          reason: form.reason,
        },
      });
    }

    if (result.labels?.length) labels.value = [...result.labels, ...labels.value];
    toast.value = {
      title: "Inventory updated",
      message: `${result.item_name} · ${result.change > 0 ? "+" : ""}${formatNumber(result.change)} ${formatUnit(result.stock_uom, result.change)}`,
      transaction: result,
      labelCodes: result.labels?.map((label) => label.label_code) || [],
    };
    lastTransaction.value = result;
    selected.value = null;
    quantityEntry.value = "";
    await loadActivity();
    await focusScanner();
  } catch (error) {
    scanError.value = apiError(error);
  } finally {
    saving.value = false;
  }
}

async function undoTransaction() {
  const transaction = lastTransaction.value;
  if (!transaction) return;
  try {
    await call("cancel_transaction", {
      voucher_type: transaction.voucher_type,
      voucher_no: transaction.voucher_no,
    });
    toast.value = { title: "Transaction cancelled", message: transaction.voucher_no };
    lastTransaction.value = null;
    await loadActivity();
    if (activeView.value === "labels") await loadLabels();
  } catch (error) {
    toast.value = { title: "Undo unavailable", message: apiError(error) };
  }
}

function printLabels() {
  if (!selectedLabelCodes.value.length) return;
  window.print();
}

function printCommandCard() {
  window.print();
}

function toggleAllLabels() {
  selectedLabelCodes.value = toggleVisibleSelection(selectedLabelCodes.value, filteredLabels.value);
}

onMounted(async () => {
  try {
    await Promise.all([loadOptions(), loadActivity()]);
    const requestedMode = inventoryModeFromUrl(window.location.href, window.location.origin);
    if (requestedMode && options.value.permissions?.[requestedMode]) await navigate(requestedMode);
    await focusScanner();
  } catch (error) {
    scanError.value = apiError(error);
  }
});
</script>

<template>
  <div class="app-shell">
    <div class="mobile-scrim" :class="{ open: mobileOpen }" @click="mobileOpen = false" />
    <aside class="sidebar" :class="{ 'mobile-open': mobileOpen, collapsed: sidebarCollapsed }">
      <div class="sidebar-account">
        <details class="app-menu">
          <summary aria-label="Open ERPNext inventory links">
            <div class="app-mark"><PackageOpen :size="18" :stroke-width="1.7" /></div>
            <div class="account-copy">
              <strong>Studio Inventory</strong>
              <span>Native ERPNext stock</span>
            </div>
            <ChevronDown class="account-chevron" :size="14" />
          </summary>
          <div class="app-menu-popover" role="menu">
            <strong>Open in ERPNext</strong>
            <a href="/app/stock" role="menuitem"><span>Stock workspace</span><ExternalLink :size="13" /></a>
            <a href="/app/item" role="menuitem"><span>Items &amp; barcodes</span><ExternalLink :size="13" /></a>
            <a href="/app/purchase-receipt" role="menuitem"><span>Purchase Receipts</span><ExternalLink :size="13" /></a>
            <a href="/app/stock-entry" role="menuitem"><span>Stock Entries</span><ExternalLink :size="13" /></a>
            <a href="/app/stock-reconciliation" role="menuitem"><span>Stock Reconciliations</span><ExternalLink :size="13" /></a>
          </div>
        </details>
        <button class="icon-button mobile-close" type="button" aria-label="Close navigation" @click="mobileOpen = false"><X :size="16" /></button>
      </div>

      <nav class="sidebar-nav" aria-label="Inventory navigation">
        <button
          v-for="item in visibleNav"
          :key="item.id"
          type="button"
          class="nav-link"
          :class="{ active: activeView === item.id }"
          @click="navigate(item.id)"
        >
          <component :is="item.icon" :size="16" :stroke-width="1.6" />
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <div class="scanner-status">
          <span class="status-dot" />
          <div><strong>Barcode input</strong><span>Type a code or connect an HID scanner</span></div>
        </div>
        <button class="nav-link collapse-link" type="button" :aria-label="sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'" @click="sidebarCollapsed = !sidebarCollapsed"><PanelLeftClose :size="16" /><span>Collapse</span></button>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div class="breadcrumbs">
          <button class="icon-button mobile-menu" type="button" aria-label="Open navigation" @click="mobileOpen = true"><Menu :size="17" /></button>
          <strong>{{ page.title }}</strong><span>/</span><span>{{ page.action }}</span>
        </div>
        <div class="topbar-actions">
          <button v-if="selected" class="button ghost" type="button" @click="selected = null"><X :size="14" /> Close</button>
          <button class="button primary" type="button" @click="navigate('activity')"><Clock3 :size="14" /> Recent</button>
        </div>
      </header>

      <main class="main-area">
        <div v-if="VIEW_COPY[activeView]" class="scanner-page">
          <form class="scan-zone" @submit.prevent="resolveScan">
            <label class="scan-field-wrap">
              <ScanBarcode class="scan-leading-icon" :size="18" />
              <input ref="scanInput" v-model="scanValue" :placeholder="page.prompt" :aria-label="page.prompt" :disabled="scanning" autocomplete="off" />
              <kbd class="enter-key">Enter</kbd>
            </label>
            <div class="scan-hint-row"><span :class="{ 'scan-error': scanError }">{{ scanError || page.help }}</span><select v-model="form.warehouse" class="warehouse-picker" aria-label="Warehouse" @change="selected = null"><option v-for="warehouse in options.warehouses" :key="warehouse.name" :value="warehouse.name">{{ warehouse.name }}</option></select></div>
          </form>
          <div class="scanner-canvas">
            <div class="ready-state">
              <div class="ready-icon"><component :is="activeView === 'receive' ? ArrowDownToLine : activeView === 'consume' ? ArrowUpFromLine : ClipboardCheck" :size="24" /></div>
              <strong>{{ page.prompt }}</strong><p>{{ page.help }}</p>
            </div>
          </div>
        </div>

        <div v-else-if="activeView === 'activity'" class="list-page">
          <div class="filter-row">
            <label class="compact-search"><Search :size="14" /><input v-model="activityQuery" placeholder="Search activity" aria-label="Search activity" /></label>
            <button class="button subtle" type="button" @click="loadActivity"><RefreshCw :size="14" /> Refresh</button>
          </div>
          <div class="activity-list">
            <div v-for="row in filteredActivity" :key="`${row.voucher_type}-${row.voucher_no}`" class="activity-row" :class="{ cancelled: row.cancelled }">
              <div class="activity-icon" :class="row.change >= 0 ? 'receive' : 'consume'">
                <ArrowDownToLine v-if="row.change >= 0" :size="15" /><ArrowUpFromLine v-else :size="15" />
              </div>
              <div class="activity-main"><strong>{{ row.item_name }}</strong><span>{{ row.detail }}</span></div>
              <strong class="activity-change" :class="row.change >= 0 ? 'receive' : 'consume'">{{ row.change > 0 ? '+' : '' }}{{ formatNumber(row.change) }} {{ formatUnit(row.stock_uom, row.change) }}</strong>
              <div class="activity-meta"><span>{{ row.owner }}</span><span>{{ row.cancelled ? 'Cancelled' : row.voucher_type }}</span></div>
              <code>{{ row.voucher_no }}</code>
            </div>
            <div v-if="!filteredActivity.length" class="empty-list">No Studio Inventory transactions yet.</div>
          </div>
        </div>

        <div v-else-if="activeView === 'commands'" class="list-page command-card-page">
          <div class="filter-row">
            <div class="page-description"><strong>Printable scanner controls</strong><span>Use a matte letter-size lamination and keep the scanner's Enter suffix enabled.</span></div>
            <button class="button primary" type="button" @click="printCommandCard"><Printer :size="14" /> Print command card</button>
          </div>
          <ScannerCommandCard :base-url="appBaseUrl" />
        </div>

        <div v-else class="list-page labels-page">
          <div class="filter-row labels-filter-row">
            <div class="label-toolbar">
              <div class="page-description"><strong>Inventory labels</strong><span>Reusable Item labels identify rolls, sheets, and cards; quantities use each Item's stock UOM.</span></div>
              <label class="compact-search label-search"><Search :size="14" /><input v-model="labelQuery" placeholder="Search name, SKU, or unit" aria-label="Search inventory labels" /><button v-if="labelQuery" class="search-clear" type="button" aria-label="Clear label search" @click="labelQuery = ''"><X :size="13" /></button></label>
              <span class="label-count">{{ filteredLabels.length === labels.length ? `${labels.length} labels` : `${filteredLabels.length} of ${labels.length} labels` }} · {{ form.warehouse }}</span>
            </div>
            <div class="label-actions"><button class="button subtle" type="button" :disabled="!filteredLabels.length" @click="toggleAllLabels">{{ allFilteredLabelsSelected ? 'Clear results' : 'Select results' }}</button><button class="button primary" type="button" :disabled="!selectedLabelCodes.length" @click="printLabels"><Printer :size="14" /> Print selected<span v-if="selectedLabelCodes.length"> ({{ selectedLabelCodes.length }})</span></button></div>
          </div>
          <div class="label-grid">
            <article v-for="label in filteredLabels" :key="label.label_code" class="label-card" :class="{ selected: selectedLabelCodes.includes(label.label_code) }">
              <input v-model="selectedLabelCodes" class="label-checkbox" type="checkbox" :value="label.label_code" :aria-label="`Select ${label.item_name} ${label.tracking} label`" />
              <strong>{{ label.item_name }}</strong><span>{{ label.item_code }}</span>
              <div class="barcode-wrap"><BarcodeSvg :value="label.label_code" /></div>
              <code>{{ label.label_code }}</code><em>Reusable Item label · {{ formatNumber(label.remaining) }} {{ formatUnit(label.stock_uom, label.remaining) }} on hand</em>
            </article>
            <div v-if="!labels.length" class="empty-list">No roll, sheet, or card Items were found for this Warehouse.</div>
            <div v-else-if="!filteredLabels.length" class="empty-list">No labels match “{{ labelQuery }}”.</div>
          </div>
          <div class="print-label-pages" aria-hidden="true">
            <section v-for="(page, pageIndex) in printableLabelPages" :key="`print-page-${pageIndex}`" class="print-label-page">
              <article v-for="label in page" :key="`print-${label.label_code}`" class="label-card print-label-card">
                <strong>{{ label.item_name }}</strong><span>{{ label.item_code }}</span>
                <div class="barcode-wrap"><BarcodeSvg :value="label.label_code" /></div>
                <code>{{ label.label_code }}</code><em>Reusable Item label</em>
              </article>
            </section>
          </div>
        </div>

        <aside v-if="selected" class="detail-panel" :aria-label="`${page.title} ${selected.item_name}`">
          <div class="panel-header">
            <div><span>{{ page.action }}</span><strong>{{ selected.batch_no || selected.item_code }}</strong></div>
            <button class="icon-button" type="button" aria-label="Close item" @click="selected = null"><X :size="16" /></button>
          </div>
          <div class="panel-scroll">
            <div class="item-identity">
              <div class="paper-icon"><PackageOpen :size="18" /></div>
              <div><strong>{{ selected.item_name }}</strong><span>{{ selected.brand || selected.item_group }} · {{ selected.stock_uom }}</span><code>{{ selected.item_code }}</code></div>
            </div>

            <div v-if="scanError" class="notice red"><Info :size="16" /><div><strong>ERPNext did not save this transaction.</strong><span>{{ scanError }}</span></div></div>

            <section v-if="activeView === 'receive'" class="form-section">
              <h3>Purchase details</h3>
              <div class="field-grid">
                <label class="field"><span>Supplier</span><select v-model="form.supplier"><option value="">Select supplier</option><option v-for="supplier in options.suppliers" :key="supplier.name" :value="supplier.name">{{ supplier.supplier_name || supplier.name }}</option></select></label>
                <label class="field"><span>Warehouse</span><select v-model="form.warehouse"><option v-for="warehouse in options.warehouses" :key="warehouse.name" :value="warehouse.name">{{ warehouse.name }}</option></select></label>
                <label class="field"><span>Purchase unit</span><select v-model="form.purchaseUom"><option v-for="uom in selected.purchase_uoms" :key="uom.uom" :value="uom.uom">{{ uom.uom }}</option></select></label>
                <label class="field"><span>Number of purchase units</span><input v-model.number="form.purchaseUnits" type="number" min="1" step="1" /></label>
                <label class="field"><span>Unit cost</span><div class="number-wrap"><input v-model.number="form.unitCost" type="number" min="0" step="0.01" /><em>$</em></div></label>
                <label class="field readonly-field"><span>Stock received</span><div>{{ formatNumber(receiveStockQty) }} {{ formatUnit(selected.stock_uom, receiveStockQty) }}</div></label>
              </div>
              <div v-if="selected.has_batch_no" class="notice blue"><Info :size="16" /><div><strong>{{ physicalUnits }} physical {{ physicalUnits === 1 ? 'roll' : 'rolls' }} will create {{ physicalUnits }} unique {{ physicalUnits === 1 ? 'Batch' : 'Batches' }}.</strong><span>Every physical roll receives its own printable Code 128 label.</span></div></div>
            </section>

            <section v-else-if="activeView === 'consume'" class="form-section">
              <h3>Material used</h3>
              <div class="segmented-control" role="group" aria-label="Consumption entry mode"><button type="button" :class="{ active: form.mode === 'amount' }" @click="form.mode = 'amount'">Amount used</button><button type="button" :class="{ active: form.mode === 'ending' }" @click="form.mode = 'ending'">Ending balance</button></div>
              <label class="field"><span>{{ form.mode === 'amount' ? 'Amount consumed' : 'Amount remaining' }}</span><div class="number-wrap"><input v-model.number="form.value" type="number" min="0" :step="selected.stock_uom === 'Foot' ? 0.01 : 1" /><em>{{ formatUnit(selected.stock_uom, form.value) }}</em></div></label>
              <div class="change-preview red"><div><span>Current</span><strong>{{ formatNumber(quantityChange.before) }} {{ formatUnit(selected.stock_uom, quantityChange.before) }}</strong></div><ChevronRight :size="16" /><div><span>Change</span><strong>{{ formatNumber(quantityChange.change) }} {{ formatUnit(selected.stock_uom, quantityChange.change) }}</strong></div><ChevronRight :size="16" /><div><span>After</span><strong>{{ formatNumber(quantityChange.after) }} {{ formatUnit(selected.stock_uom, quantityChange.after) }}</strong></div></div>
              <label class="field readonly-field"><span>Warehouse</span><div>{{ form.warehouse }}</div></label><label class="field readonly-field"><span>{{ selected.batch_no ? 'Batch' : 'Item barcode' }}</span><div>{{ selected.batch_no || selected.item_code }}</div></label>
            </section>

            <section v-else class="form-section">
              <h3>Measured inventory</h3>
              <label class="field"><span>Actual remaining</span><div class="number-wrap"><input v-model.number="form.value" type="number" min="0" :step="selected.stock_uom === 'Foot' ? 0.01 : 1" /><em>{{ formatUnit(selected.stock_uom, form.value) }}</em></div></label>
              <label class="field"><span>Reason</span><select v-model="form.reason"><option>Physical measurement</option><option>Damaged material</option><option>Receiving correction</option><option>Data-entry correction</option></select></label>
              <div class="change-preview" :class="quantityChange.change < 0 ? 'red' : 'green'"><div><span>Current</span><strong>{{ formatNumber(quantityChange.before) }} {{ formatUnit(selected.stock_uom, quantityChange.before) }}</strong></div><ChevronRight :size="16" /><div><span>Change</span><strong>{{ quantityChange.change > 0 ? '+' : '' }}{{ formatNumber(quantityChange.change) }} {{ formatUnit(selected.stock_uom, quantityChange.change) }}</strong></div><ChevronRight :size="16" /><div><span>After</span><strong>{{ formatNumber(quantityChange.after) }} {{ formatUnit(selected.stock_uom, quantityChange.after) }}</strong></div></div>
              <div class="notice amber"><Info :size="16" /><div><strong>This records a Stock Reconciliation.</strong><span>The original transactions remain in ERPNext's audit history.</span></div></div>
            </section>
          </div>
          <div class="panel-footer">
            <button class="button ghost" type="button" @click="selected = null">Cancel</button>
            <button class="button primary confirm-button" type="button" :disabled="saving || !transactionReady" @click="confirmTransaction"><Check :size="15" />{{ saving ? 'Saving…' : activeView === 'receive' ? 'Receive inventory' : activeView === 'consume' ? 'Record consumption' : 'Correct balance' }}</button>
          </div>
        </aside>
      </main>
    </div>

    <div v-if="toast" class="toast" :class="{ 'panel-open': selected }" role="status">
      <div class="toast-icon"><Check :size="14" /></div><div><strong>{{ toast.title }}</strong><span>{{ toast.message }}</span></div>
      <button v-if="toast.transaction" type="button" @click="undoTransaction">Undo</button>
      <button v-if="toast.labelCodes?.length" type="button" @click="openLabels(toast.labelCodes)">Labels</button>
      <button class="icon-button" type="button" aria-label="Dismiss notification" @click="toast = null"><X :size="14" /></button>
    </div>
  </div>
</template>
