<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { frappeRequest } from "frappe-ui";
import { Calculator, ExternalLink, Info, RefreshCw } from "@lucide/vue";

const context = ref(null);
const paper = ref(null);
const result = ref(null);
const loading = ref(true);
const loadingPaper = ref(false);
const calculating = ref(false);
const error = ref("");

const form = reactive({
  print_item: "",
  paper_item: "",
  artwork_width_in: null,
  artwork_height_in: null,
  border_in: 0,
  quantity: 1,
  time_minutes: 0,
  ink_cost_per_sq_in: null,
  cost_override: null,
});

const selectedPaper = computed(() =>
  context.value?.paper_items?.find((item) => item.name === form.paper_item),
);

function apiError(value) {
  const messages = value?.messages || value?._server_messages;
  if (Array.isArray(messages) && messages.length) return messages.join(" ");
  return value?.message || "ERPNext could not complete the pricing request.";
}

async function callPricing(method, args = {}) {
  const response = await frappeRequest({
    url: `/api/method/studio_inventory.pricing_api.${method}`,
    method: "POST",
    params: args,
  });
  return response?.message ?? response;
}

function money(value) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: context.value?.currency || "USD",
  }).format(Number(value || 0));
}

function number(value, digits = 3) {
  return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: digits });
}

async function loadContext() {
  loading.value = true;
  error.value = "";
  try {
    context.value = await callPricing("get_pricing_context", { include_paper_items: 1 });
    form.print_item = context.value.default_print_item || "";
    form.ink_cost_per_sq_in = context.value.ink_cost_per_sq_in;
  } catch (value) {
    error.value = apiError(value);
  } finally {
    loading.value = false;
  }
}

async function loadPaper() {
  paper.value = null;
  result.value = null;
  error.value = "";
  if (!form.paper_item) return;
  loadingPaper.value = true;
  try {
    paper.value = await callPricing("get_paper_cost", { item_code: form.paper_item });
  } catch (value) {
    error.value = apiError(value);
  } finally {
    loadingPaper.value = false;
  }
}

async function calculate() {
  calculating.value = true;
  result.value = null;
  error.value = "";
  try {
    result.value = await callPricing("calculate_print", { payload: { ...form } });
  } catch (value) {
    error.value = apiError(value);
  } finally {
    calculating.value = false;
  }
}

function reset() {
  form.paper_item = "";
  form.artwork_width_in = null;
  form.artwork_height_in = null;
  form.border_in = 0;
  form.quantity = 1;
  form.time_minutes = 0;
  form.cost_override = null;
  form.ink_cost_per_sq_in = context.value?.ink_cost_per_sq_in ?? null;
  paper.value = null;
  result.value = null;
  error.value = "";
}

onMounted(loadContext);
</script>

<template>
  <div class="price-page">
    <div class="filter-row price-heading">
      <div class="page-description">
        <strong>Standalone print pricing</strong>
        <span>Explore a price without creating a Deal, Quotation, or inventory transaction.</span>
      </div>
      <button class="button subtle" type="button" :disabled="loading" @click="reset">
        <RefreshCw :size="14" /> Reset
      </button>
    </div>

    <div v-if="loading" class="price-loading">Loading pricing settings…</div>

    <div v-else-if="!context" class="price-loading price-error">
      <Info :size="18" />
      <div><strong>Pricing is unavailable</strong><span>{{ error }}</span></div>
    </div>

    <div v-else class="price-workspace">
      <form class="price-form" @submit.prevent="calculate">
        <section class="price-section">
          <div class="price-section-heading"><span>01</span><div><strong>Paper</strong><small>Choose the stock Item whose current buying cost should be used.</small></div></div>
          <label class="field price-field-wide">
            <span>Paper Item <em class="required-label">Required</em></span>
            <input v-model.trim="form.paper_item" list="price-paper-items" required placeholder="Type a paper name or Item code" autocomplete="off" @change="loadPaper" />
            <datalist id="price-paper-items">
              <option v-for="item in context.paper_items" :key="item.name" :value="item.name">{{ item.item_name }}</option>
            </datalist>
            <small v-if="selectedPaper" class="field-help">{{ selectedPaper.item_name }} · {{ selectedPaper.stock_uom }}<template v-if="selectedPaper.brand"> · {{ selectedPaper.brand }}</template></small>
          </label>
          <label class="field readonly-field price-field-wide">
            <span>Print service Item</span><div>{{ context.default_print_item }}</div>
          </label>
          <div v-if="loadingPaper" class="price-cost-note"><span>Loading current paper cost…</span></div>
          <div v-else-if="paper?.basis" class="price-cost-note">
            <div><strong>{{ money(paper.basis.rate) }} / {{ paper.basis.uom }}</strong><span>{{ number(paper.basis.cost_per_sq_in, 6) }} / sq in<template v-if="paper.basis.supplier"> · {{ paper.basis.supplier }}</template></span></div>
            <a v-if="paper.basis.merchant_url" :href="paper.basis.merchant_url" target="_blank" rel="noopener">Merchant <ExternalLink :size="12" /></a>
          </div>
          <div v-else-if="paper" class="price-cost-note price-cost-missing"><Info :size="15" /><span>No current Buying Item Price was found.</span></div>
        </section>

        <section class="price-section">
          <div class="price-section-heading"><span>02</span><div><strong>Print specification</strong><small>Artwork dimensions do not include the border.</small></div></div>
          <div class="price-field-grid">
            <label class="field"><span>Artwork width (in) <em class="required-label">Required</em></span><input v-model.number="form.artwork_width_in" type="number" min="0.01" step="0.01" required /></label>
            <label class="field"><span>Artwork height (in) <em class="required-label">Required</em></span><input v-model.number="form.artwork_height_in" type="number" min="0.01" step="0.01" required /></label>
            <label class="field"><span>Border on each side (in)</span><input v-model.number="form.border_in" type="number" min="0" step="0.01" /></label>
            <label class="field"><span>Quantity <em class="required-label">Required</em></span><input v-model.number="form.quantity" type="number" min="1" step="1" required /></label>
          </div>
        </section>

        <section class="price-section">
          <div class="price-section-heading"><span>03</span><div><strong>Internal costing</strong><small>These values affect cost and margin, not customer-facing notes.</small></div></div>
          <div class="price-field-grid">
            <label class="field"><span>Production time (minutes)</span><input v-model.number="form.time_minutes" type="number" min="0" step="1" /></label>
            <label class="field"><span>Ink cost / sq in</span><div class="number-wrap"><input v-model.number="form.ink_cost_per_sq_in" type="number" min="0" step="0.000001" /><em>$</em></div></label>
            <label v-if="context.can_override_cost" class="field price-field-wide"><span>Paper cost / sq in override</span><div class="number-wrap"><input v-model.number="form.cost_override" type="number" min="0" step="0.000001" placeholder="Use current Buying Item Price" /><em>$</em></div></label>
          </div>
        </section>

        <div v-if="error" class="notice red price-form-error"><Info :size="16" /><div><strong>Price not calculated</strong><span>{{ error }}</span></div></div>

        <div class="price-form-footer">
          <span>Nothing is saved by this calculator.</span>
          <button class="button primary price-calculate" type="submit" :disabled="calculating || loadingPaper">
            <Calculator :size="15" /> {{ calculating ? "Calculating…" : "Calculate price" }}
          </button>
        </div>
      </form>

      <aside class="price-results" aria-live="polite">
        <div v-if="!result" class="price-empty-result">
          <div><Calculator :size="24" /></div>
          <strong>Your price will appear here</strong>
          <span>Select a paper and enter the finished print specification.</span>
        </div>

        <template v-else>
          <div class="price-result-header"><span>Calculated price</span><strong>{{ money(result.calculation.list_unit_price) }}</strong><small>per print</small></div>
          <div class="price-total-card"><span>Line total · {{ result.calculation.quantity }} prints</span><strong>{{ money(result.calculation.line_total) }}</strong></div>
          <section class="price-result-section">
            <h3>Production estimate</h3>
            <div><span>Finished size</span><strong>{{ number(result.calculation.finished_width_in) }} × {{ number(result.calculation.finished_height_in) }} in</strong></div>
            <div><span>Estimated paper</span><strong>{{ number(result.consumption.quantity) }} {{ result.consumption.uom }}</strong></div>
          </section>
          <section class="price-result-section">
            <h3>Internal economics</h3>
            <div><span>Total cost</span><strong>{{ money(result.calculation.total_cost) }}</strong></div>
            <div><span>Gross profit</span><strong>{{ money(result.calculation.gross_profit) }}</strong></div>
            <div><span>Gross margin</span><strong>{{ number(result.calculation.gross_margin_pct, 1) }}%</strong></div>
          </section>
          <div v-for="warning in result.warnings" :key="warning" class="notice amber price-warning"><Info :size="16" /><div><strong>Margin warning</strong><span>{{ warning }}</span></div></div>
          <div class="price-not-saved"><Info :size="14" /><span>This result is temporary and has not created or changed any CRM or ERPNext record.</span></div>
        </template>
      </aside>
    </div>
  </div>
</template>
