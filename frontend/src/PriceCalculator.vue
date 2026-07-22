<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { frappeRequest } from "frappe-ui";
import { Calculator, Check, ExternalLink, Info, RefreshCw, Search } from "@lucide/vue";
import { buildPaperSearchIndex, searchPaperOptions } from "./paperSearch.js";

const context = ref(null);
const paper = ref(null);
const result = ref(null);
const loading = ref(true);
const loadingPaper = ref(false);
const calculating = ref(false);
const error = ref("");
const paperQuery = ref("");
const paperPicker = ref(null);
const paperInput = ref(null);
const paperOpen = ref(false);
const activePaperIndex = ref(0);

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

const paperSearchIndex = computed(() => buildPaperSearchIndex(context.value?.paper_items));
const paperMatches = computed(() => searchPaperOptions(paperSearchIndex.value, paperQuery.value));
const visiblePaperOptions = computed(() => paperMatches.value.options);
const activePaperOptionId = computed(() => (
  paperOpen.value && visiblePaperOptions.value.length
    ? `price-paper-option-${activePaperIndex.value}`
    : undefined
));

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

function openPaperOptions() {
  paperOpen.value = true;
  activePaperIndex.value = 0;
}

function onPaperInput() {
  form.paper_item = "";
  paper.value = null;
  result.value = null;
  error.value = "";
  activePaperIndex.value = 0;
  paperOpen.value = true;
  paperInput.value?.setCustomValidity(
    paperQuery.value ? "Choose a paper from the matching results." : "",
  );
}

function closePaperOptions(event) {
  if (!paperPicker.value?.contains(event.target)) paperOpen.value = false;
}

function scrollToActivePaper() {
  nextTick(() => {
    document.getElementById(activePaperOptionId.value)?.scrollIntoView({ block: "nearest" });
  });
}

function movePaperSelection(direction) {
  if (!paperOpen.value) openPaperOptions();
  const count = visiblePaperOptions.value.length;
  if (!count) return;
  activePaperIndex.value = (activePaperIndex.value + direction + count) % count;
  scrollToActivePaper();
}

function selectPaper(item, blur = false) {
  const shouldLoad = form.paper_item !== item.name || (!paper.value && !loadingPaper.value);
  form.paper_item = item.name;
  paperQuery.value = item.item_name || item.name;
  paperInput.value?.setCustomValidity("");
  paperOpen.value = false;
  if (blur) paperInput.value?.blur();
  if (shouldLoad) loadPaper();
}

function selectActivePaper(event) {
  if (!paperOpen.value || !visiblePaperOptions.value.length) return;
  event.preventDefault();
  selectPaper(visiblePaperOptions.value[activePaperIndex.value]);
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
  paperQuery.value = "";
  paperOpen.value = false;
  paperInput.value?.setCustomValidity("");
  paper.value = null;
  result.value = null;
  error.value = "";
}

onMounted(() => {
  document.addEventListener("pointerdown", closePaperOptions);
  loadContext();
});

onBeforeUnmount(() => document.removeEventListener("pointerdown", closePaperOptions));
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
          <div ref="paperPicker" class="field price-field-wide paper-picker">
            <label for="price-paper-input">Paper Item <em class="required-label">Required</em></label>
            <div class="paper-combobox">
              <Search class="paper-search-icon" :size="15" aria-hidden="true" />
              <input
                id="price-paper-input"
                ref="paperInput"
                v-model="paperQuery"
                type="search"
                role="combobox"
                required
                placeholder="Search paper name, Item code, or brand"
                autocomplete="off"
                autocorrect="off"
                :spellcheck="false"
                aria-autocomplete="list"
                aria-controls="price-paper-options"
                :aria-expanded="paperOpen"
                :aria-activedescendant="activePaperOptionId"
                @focus="openPaperOptions"
                @input="onPaperInput"
                @keydown.down.prevent="movePaperSelection(1)"
                @keydown.up.prevent="movePaperSelection(-1)"
                @keydown.enter="selectActivePaper"
                @keydown.esc.stop="paperOpen = false"
                @keydown.tab="paperOpen = false"
              />
              <div v-if="paperOpen" id="price-paper-options" class="paper-options" role="listbox" aria-label="Paper Items">
                <button
                  v-for="(item, index) in visiblePaperOptions"
                  :id="`price-paper-option-${index}`"
                  :key="item.name"
                  class="paper-option"
                  :class="{ active: index === activePaperIndex, selected: item.name === form.paper_item }"
                  type="button"
                  role="option"
                  tabindex="-1"
                  :aria-selected="item.name === form.paper_item"
                  @mouseenter="activePaperIndex = index"
                  @click="selectPaper(item, true)"
                >
                  <span><strong>{{ item.item_name || item.name }}</strong><small>{{ item.name }} · {{ item.stock_uom }}<template v-if="item.brand"> · {{ item.brand }}</template></small></span>
                  <Check v-if="item.name === form.paper_item" :size="15" aria-hidden="true" />
                </button>
                <div v-if="!visiblePaperOptions.length" class="paper-options-empty" role="status">No papers match “{{ paperQuery }}”.</div>
                <div v-else-if="paperMatches.total > visiblePaperOptions.length" class="paper-options-limit">
                  Showing {{ visiblePaperOptions.length }} of {{ paperMatches.total }} matches. Type more to narrow the list.
                </div>
              </div>
            </div>
            <small v-if="selectedPaper" class="field-help">{{ selectedPaper.name }} · {{ selectedPaper.stock_uom }}<template v-if="selectedPaper.brand"> · {{ selectedPaper.brand }}</template></small>
            <small v-else class="field-help">Choose a matching result to load its current cost.</small>
          </div>
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
