<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { frappeRequest } from "frappe-ui";
import {
  ArrowLeftRight,
  Calculator,
  Check,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  FilePlus2,
  Info,
  RefreshCw,
  Search,
  X,
} from "@lucide/vue";
import { buildPaperSearchIndex, searchPaperOptions } from "./paperSearch.js";

const props = defineProps({
  estimateRequest: { type: String, default: "" },
});

const RECENT_PAPER_KEY = "studio-inventory:recent-paper-items";
const RECENT_PAPER_LIMIT = 5;
const SIZE_PRESETS = [
  { label: "8 × 10", width: 8, height: 10 },
  { label: "11 × 14", width: 11, height: 14 },
  { label: "16 × 20", width: 16, height: 20 },
  { label: "20 × 24", width: 20, height: 24 },
];

const context = ref(null);
const paper = ref(null);
const result = ref(null);
const loading = ref(true);
const loadingPaper = ref(false);
const calculating = ref(false);
const creatingEstimate = ref(false);
const error = ref("");
const paperQuery = ref("");
const paperPicker = ref(null);
const paperInput = ref(null);
const paperOpen = ref(false);
const activePaperIndex = ref(0);
const recentPaperNames = ref([]);
const resultStale = ref(false);
const resultBreakdownOpen = ref(false);
const internalCostingOpen = ref(false);
let suppressNextPaperOpen = false;

const validationErrors = reactive({
  paper: "",
  artwork_width: "",
  artwork_height: "",
  border: "",
  quantity: "",
  time: "",
  ink: "",
  cost_override: "",
});

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
const trimmedPaperQuery = computed(() => paperQuery.value.trim());
const showingRecentPapers = computed(() => !trimmedPaperQuery.value);
const paperSearchReady = computed(() => trimmedPaperQuery.value.length >= 2);
const recentPaperOptions = computed(() => {
  const items = context.value?.paper_items || [];
  return recentPaperNames.value
    .map((name) => items.find((item) => item.name === name))
    .filter(Boolean);
});
const paperMatches = computed(() => (
  paperSearchReady.value
    ? searchPaperOptions(paperSearchIndex.value, trimmedPaperQuery.value)
    : { options: [], total: 0 }
));
const visiblePaperOptions = computed(() => (
  showingRecentPapers.value ? recentPaperOptions.value : paperMatches.value.options
));
const activePaperOptionId = computed(() => (
  paperOpen.value && visiblePaperOptions.value.length
    ? `price-paper-option-${activePaperIndex.value}`
    : undefined
));
const validationErrorCount = computed(() => (
  Object.values(validationErrors).filter(Boolean).length
));
const internalCostSummary = computed(() => {
  const paperCost = form.cost_override === null || form.cost_override === ""
    ? "current buying price"
    : "manual paper cost";
  return `${number(form.time_minutes, 0)} min · ${number(form.ink_cost_per_sq_in, 6)} ink / sq in · ${paperCost}`;
});

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

function zeroWhenBlank(value) {
  return value === "" || value === null || value === undefined ? 0 : value;
}

function calculationPayload() {
  return {
    ...form,
    border_in: zeroWhenBlank(form.border_in),
    time_minutes: zeroWhenBlank(form.time_minutes),
    ink_cost_per_sq_in: zeroWhenBlank(form.ink_cost_per_sq_in),
  };
}

function printCount(quantity) {
  const count = Number(quantity) || 0;
  return `${count} ${count === 1 ? "print" : "prints"}`;
}

function loadRecentPaperNames() {
  try {
    const saved = JSON.parse(localStorage.getItem(RECENT_PAPER_KEY) || "[]");
    if (Array.isArray(saved)) recentPaperNames.value = saved.slice(0, RECENT_PAPER_LIMIT);
  } catch {
    recentPaperNames.value = [];
  }
}

function rememberPaper(name) {
  if (!name) return;
  recentPaperNames.value = [
    name,
    ...recentPaperNames.value.filter((itemName) => itemName !== name),
  ].slice(0, RECENT_PAPER_LIMIT);
  try {
    localStorage.setItem(RECENT_PAPER_KEY, JSON.stringify(recentPaperNames.value));
  } catch {
    // Recent papers are an optional device-local convenience.
  }
}

function clearValidationErrors() {
  Object.keys(validationErrors).forEach((key) => { validationErrors[key] = ""; });
}

function validationErrorsForForm() {
  const errors = {
    paper: form.paper_item ? "" : "Choose a paper from the matching results.",
    artwork_width: Number(form.artwork_width_in) > 0 ? "" : "Enter an artwork width greater than 0.",
    artwork_height: Number(form.artwork_height_in) > 0 ? "" : "Enter an artwork height greater than 0.",
    border: Number(form.border_in) >= 0 ? "" : "Border cannot be negative.",
    quantity: Number.isInteger(Number(form.quantity)) && Number(form.quantity) >= 1
      ? ""
      : "Enter a whole-number quantity of at least 1.",
    time: Number(form.time_minutes) >= 0 ? "" : "Production time cannot be negative.",
    ink: Number(form.ink_cost_per_sq_in) >= 0 ? "" : "Ink cost cannot be negative.",
    cost_override: form.cost_override === null || form.cost_override === "" || Number(form.cost_override) >= 0
      ? ""
      : "Paper cost override cannot be negative.",
  };
  return errors;
}

function applyValidationErrors(errors) {
  Object.keys(validationErrors).forEach((key) => { validationErrors[key] = errors[key] || ""; });
}

function focusFirstInvalidField() {
  const fieldIds = {
    paper: "price-paper-input",
    artwork_width: "price-artwork-width",
    artwork_height: "price-artwork-height",
    border: "price-border",
    quantity: "price-quantity",
    time: "price-time",
    ink: "price-ink",
    cost_override: "price-cost-override",
  };
  const firstInvalid = Object.keys(validationErrors).find((key) => validationErrors[key]);
  if (!firstInvalid) return;
  if (firstInvalid === "paper") suppressNextPaperOpen = true;
  nextTick(() => document.getElementById(fieldIds[firstInvalid])?.focus());
}

function validateForm() {
  applyValidationErrors(validationErrorsForForm());
  if (!validationErrorCount.value) return true;
  if (validationErrors.time || validationErrors.ink || validationErrors.cost_override) {
    internalCostingOpen.value = true;
  }
  paperOpen.value = false;
  focusFirstInvalidField();
  return false;
}

function applySizePreset(preset) {
  form.artwork_width_in = preset.width;
  form.artwork_height_in = preset.height;
}

function isSizePresetActive(preset) {
  return Number(form.artwork_width_in) === preset.width
    && Number(form.artwork_height_in) === preset.height;
}

function swapArtworkDimensions() {
  if (!(Number(form.artwork_width_in) > 0) || !(Number(form.artwork_height_in) > 0)) return;
  const width = form.artwork_width_in;
  form.artwork_width_in = form.artwork_height_in;
  form.artwork_height_in = width;
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
  if (suppressNextPaperOpen) {
    suppressNextPaperOpen = false;
    return;
  }
  paperOpen.value = true;
  activePaperIndex.value = 0;
}

function onPaperInput() {
  form.paper_item = "";
  paper.value = null;
  error.value = "";
  activePaperIndex.value = 0;
  paperOpen.value = true;
  if (validationErrors.paper) validationErrors.paper = "Choose a paper from the matching results.";
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
  validationErrors.paper = "";
  rememberPaper(item.name);
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
  if (!validateForm()) return;
  calculating.value = true;
  result.value = null;
  resultStale.value = false;
  resultBreakdownOpen.value = false;
  internalCostingOpen.value = false;
  error.value = "";
  try {
    result.value = await callPricing("calculate_print", { payload: calculationPayload() });
  } catch (value) {
    error.value = apiError(value);
  } finally {
    calculating.value = false;
  }
}

async function createEstimate() {
  if (!result.value || !props.estimateRequest || !validateForm()) return;
  creatingEstimate.value = true;
  error.value = "";
  try {
    const estimate = await callPricing("create_estimate", {
      payload: calculationPayload(),
      crm_deal: props.estimateRequest,
    });
    window.location.assign(estimate.url);
  } catch (value) {
    error.value = apiError(value);
  } finally {
    creatingEstimate.value = false;
  }
}

function reset() {
  result.value = null;
  resultStale.value = false;
  resultBreakdownOpen.value = false;
  internalCostingOpen.value = false;
  error.value = "";
  clearValidationErrors();
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
  paper.value = null;
}

watch(form, () => {
  if (result.value) {
    result.value = null;
    resultStale.value = true;
    resultBreakdownOpen.value = false;
  }
  if (error.value) error.value = "";
  if (validationErrorCount.value) applyValidationErrors(validationErrorsForForm());
}, { deep: true, flush: "sync" });

onMounted(() => {
  loadRecentPaperNames();
  document.addEventListener("pointerdown", closePaperOptions);
  loadContext();
});

onBeforeUnmount(() => document.removeEventListener("pointerdown", closePaperOptions));
</script>

<template>
  <div class="price-page">
    <div class="filter-row price-heading">
      <div class="page-description">
        <strong>{{ props.estimateRequest ? "Estimate pricing" : "Standalone print pricing" }}</strong>
        <span v-if="props.estimateRequest">Calculate for Estimate Request {{ props.estimateRequest }} and start an Estimate when ready.</span>
        <span v-else>Explore a price without creating an Inquiry, Estimate Request, Estimate, or inventory transaction.</span>
      </div>
      <div class="price-heading-actions">
        <a v-if="context?.can_manage_pricing" class="button subtle" href="/app/studio-pricing-model">Manage pricing</a>
        <button class="button subtle price-reset" type="button" :disabled="loading" @click="reset">
          <RefreshCw :size="14" /> Reset
        </button>
      </div>
    </div>

    <div v-if="loading" class="price-loading">Loading pricing settings…</div>

    <div v-else-if="!context" class="price-loading price-error">
      <Info :size="18" />
      <div><strong>Pricing is unavailable</strong><span>{{ error }}</span></div>
    </div>

    <div v-else class="price-workspace">
      <form id="price-calculator-form" class="price-form" novalidate @submit.prevent="calculate">
        <section class="price-section">
          <div class="price-section-heading"><span>01</span><div><strong>Paper</strong><small>Choose the stock Item whose current buying cost should be used.</small></div></div>
          <div ref="paperPicker" class="field price-field-wide paper-picker" :class="{ invalid: validationErrors.paper }">
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
                :aria-invalid="Boolean(validationErrors.paper)"
                :aria-describedby="validationErrors.paper ? 'price-paper-error' : 'price-paper-help'"
                @focus="openPaperOptions"
                @input="onPaperInput"
                @keydown.down.prevent="movePaperSelection(1)"
                @keydown.up.prevent="movePaperSelection(-1)"
                @keydown.enter="selectActivePaper"
                @keydown.esc.stop="paperOpen = false"
                @keydown.tab="paperOpen = false"
              />
              <div v-if="paperOpen" id="price-paper-options" class="paper-options" role="listbox" aria-label="Paper Items">
                <div v-if="showingRecentPapers && visiblePaperOptions.length" class="paper-options-heading">Recent papers</div>
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
                <div v-if="!visiblePaperOptions.length && paperSearchReady" class="paper-options-empty" role="status">No papers match “{{ paperQuery }}”.</div>
                <div v-else-if="!visiblePaperOptions.length" class="paper-options-empty" role="status">Type at least 2 characters to search {{ paperSearchIndex.length }} papers.</div>
                <div v-if="showingRecentPapers && visiblePaperOptions.length" class="paper-options-limit">Recent papers · type to search the full catalog.</div>
                <div v-else-if="paperMatches.total > visiblePaperOptions.length" class="paper-options-limit">
                  Showing {{ visiblePaperOptions.length }} of {{ paperMatches.total }} matches. Type more to narrow the list.
                </div>
              </div>
            </div>
            <small v-if="validationErrors.paper" id="price-paper-error" class="field-error">{{ validationErrors.paper }}</small>
            <small v-else-if="selectedPaper" id="price-paper-help" class="field-help">{{ selectedPaper.name }} · {{ selectedPaper.stock_uom }}<template v-if="selectedPaper.brand"> · {{ selectedPaper.brand }}</template></small>
            <small v-else id="price-paper-help" class="field-help">Choose a matching result to load its current cost.</small>
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
          <div class="price-size-tools">
            <span>Common sizes</span>
            <div class="price-size-presets">
              <button
                v-for="preset in SIZE_PRESETS"
                :key="preset.label"
                class="price-size-preset"
                :class="{ active: isSizePresetActive(preset) }"
                type="button"
                @click="applySizePreset(preset)"
              >{{ preset.label }}</button>
            </div>
            <button class="button subtle price-swap" type="button" :disabled="!(Number(form.artwork_width_in) > 0) || !(Number(form.artwork_height_in) > 0)" @click="swapArtworkDimensions">
              <ArrowLeftRight :size="14" /> Swap
            </button>
          </div>
          <div class="price-field-grid">
            <label class="field" :class="{ invalid: validationErrors.artwork_width }"><span>Artwork width (in) <em class="required-label">Required</em></span><input id="price-artwork-width" v-model.number="form.artwork_width_in" type="number" min="0.01" step="0.01" required :aria-invalid="Boolean(validationErrors.artwork_width)" aria-describedby="price-artwork-width-error" /><small v-if="validationErrors.artwork_width" id="price-artwork-width-error" class="field-error">{{ validationErrors.artwork_width }}</small></label>
            <label class="field" :class="{ invalid: validationErrors.artwork_height }"><span>Artwork height (in) <em class="required-label">Required</em></span><input id="price-artwork-height" v-model.number="form.artwork_height_in" type="number" min="0.01" step="0.01" required :aria-invalid="Boolean(validationErrors.artwork_height)" aria-describedby="price-artwork-height-error" /><small v-if="validationErrors.artwork_height" id="price-artwork-height-error" class="field-error">{{ validationErrors.artwork_height }}</small></label>
            <label class="field" :class="{ invalid: validationErrors.border }"><span>Border on each side (in)</span><input id="price-border" v-model.number="form.border_in" type="number" min="0" step="0.01" :aria-invalid="Boolean(validationErrors.border)" aria-describedby="price-border-error" /><small v-if="validationErrors.border" id="price-border-error" class="field-error">{{ validationErrors.border }}</small></label>
            <label class="field" :class="{ invalid: validationErrors.quantity }"><span>Quantity <em class="required-label">Required</em></span><input id="price-quantity" v-model.number="form.quantity" type="number" min="1" step="1" required :aria-invalid="Boolean(validationErrors.quantity)" aria-describedby="price-quantity-error" /><small v-if="validationErrors.quantity" id="price-quantity-error" class="field-error">{{ validationErrors.quantity }}</small></label>
          </div>
        </section>

        <section class="price-section price-internal-section" :class="{ open: internalCostingOpen }">
          <div class="price-section-heading"><span>03</span><div><strong>Internal costing</strong><small>These values affect cost and margin, not customer-facing notes.</small></div></div>
          <button class="price-mobile-section-toggle" type="button" :aria-expanded="internalCostingOpen" @click="internalCostingOpen = !internalCostingOpen">
            <span>03</span><div><strong>Internal costing</strong><small>{{ internalCostSummary }}</small></div><ChevronDown :size="17" />
          </button>
          <div class="price-field-grid price-internal-fields">
            <label class="field" :class="{ invalid: validationErrors.time }"><span>Production time (minutes)</span><input id="price-time" v-model.number="form.time_minutes" type="number" min="0" step="1" :aria-invalid="Boolean(validationErrors.time)" aria-describedby="price-time-error" /><small v-if="validationErrors.time" id="price-time-error" class="field-error">{{ validationErrors.time }}</small></label>
            <label class="field" :class="{ invalid: validationErrors.ink }"><span>Ink cost / sq in</span><div class="number-wrap"><input id="price-ink" v-model.number="form.ink_cost_per_sq_in" type="number" min="0" step="0.000001" :aria-invalid="Boolean(validationErrors.ink)" aria-describedby="price-ink-error" /><em>$</em></div><small v-if="validationErrors.ink" id="price-ink-error" class="field-error">{{ validationErrors.ink }}</small></label>
            <label v-if="context.can_override_cost" class="field price-field-wide" :class="{ invalid: validationErrors.cost_override }"><span>Paper cost / sq in override</span><div class="number-wrap"><input id="price-cost-override" v-model.number="form.cost_override" type="number" min="0" step="0.000001" placeholder="Use current Buying Item Price" :aria-invalid="Boolean(validationErrors.cost_override)" aria-describedby="price-cost-override-error" /><em>$</em></div><small v-if="validationErrors.cost_override" id="price-cost-override-error" class="field-error">{{ validationErrors.cost_override }}</small></label>
          </div>
        </section>

        <div v-if="error" class="notice red price-form-error"><Info :size="16" /><div><strong>Price not calculated</strong><span>{{ error }}</span></div></div>
      </form>

      <aside class="price-results" :class="{ 'mobile-open': resultBreakdownOpen }" aria-live="polite">
        <div class="price-results-mobile-head"><strong>Price breakdown</strong><button class="icon-button" type="button" aria-label="Close price breakdown" @click="resultBreakdownOpen = false"><X :size="18" /></button></div>
        <div v-if="resultStale" class="price-empty-result price-stale-result">
          <div><RefreshCw :size="24" /></div>
          <strong>Inputs changed</strong>
          <span>Recalculate to update the price and production estimate.</span>
        </div>
        <div v-else-if="!result" class="price-empty-result">
          <div><Calculator :size="24" /></div>
          <strong>Your price will appear here</strong>
          <span>Select a paper and enter the finished print specification.</span>
        </div>

        <template v-else>
          <div class="price-result-header">
            <span>{{ Number(result.calculation.quantity) === 1 ? "Total price" : "Price per print" }}</span>
            <strong>{{ money(Number(result.calculation.quantity) === 1 ? result.calculation.line_total : result.calculation.list_unit_price) }}</strong>
            <small>{{ Number(result.calculation.quantity) === 1 ? printCount(result.calculation.quantity) : "per print" }}</small>
          </div>
          <div class="price-result-paper"><span>Paper</span><strong>{{ selectedPaper?.item_name || selectedPaper?.name || form.paper_item }}</strong></div>
          <div v-if="Number(result.calculation.quantity) > 1" class="price-total-card"><span>Line total · {{ printCount(result.calculation.quantity) }}</span><strong>{{ money(result.calculation.line_total) }}</strong></div>
          <section class="price-result-section">
            <h3>Production estimate</h3>
            <div><span>Finished size</span><strong>{{ number(result.calculation.finished_width_in) }} × {{ number(result.calculation.finished_height_in) }} in</strong></div>
            <div><span>Estimated paper</span><strong>{{ number(result.consumption.quantity) }} {{ result.consumption.uom }}</strong></div>
          </section>
          <section class="price-result-section">
            <h3>Internal economics</h3>
            <div v-if="result.pricing_model"><span>Pricing model</span><strong>{{ result.pricing_model.name }} · r{{ result.pricing_model.revision }}</strong></div>
            <div v-if="result.matched_rules?.length"><span>Matched rules</span><strong>{{ result.matched_rules.map((rule) => rule.rule_name).join(", ") }}</strong></div>
            <div v-if="result.pricing_cost_source?.item_code && result.pricing_cost_source.item_code !== result.paper_item.item_code"><span>Pricing paper basis</span><strong>{{ result.pricing_cost_source.item_name || result.pricing_cost_source.item_code }}</strong></div>
            <div><span>Total cost</span><strong>{{ money(result.calculation.total_cost) }}</strong></div>
            <div><span>Gross profit</span><strong>{{ money(result.calculation.gross_profit) }}</strong></div>
            <div><span>Gross margin</span><strong>{{ number(result.calculation.gross_margin_pct, 1) }}%</strong></div>
          </section>
          <div v-for="warning in result.warnings" :key="warning" class="notice amber price-warning"><Info :size="16" /><div><strong>Margin warning</strong><span>{{ warning }}</span></div></div>
          <div class="price-not-saved"><Info :size="14" /><span>This result is temporary and has not created or changed any CRM or ERPNext record.</span></div>
        </template>
      </aside>
    </div>
    <button v-if="resultBreakdownOpen" class="price-results-scrim" type="button" aria-label="Close price breakdown" @click="resultBreakdownOpen = false"></button>
    <div
      v-if="context"
      class="price-action-bar"
      :class="{ 'has-estimate-action': props.estimateRequest && result && !resultStale }"
    >
      <div class="price-action-total" aria-live="polite">
        <span>{{ validationErrorCount ? "Needs attention" : resultStale ? "Price" : "Line total" }}</span>
        <strong v-if="validationErrorCount">{{ validationErrorCount }} {{ validationErrorCount === 1 ? "field" : "fields" }}</strong>
        <strong v-else>{{ result ? money(result.calculation.line_total) : "—" }}</strong>
        <small v-if="validationErrorCount">Correct the highlighted entries.</small>
        <small v-else-if="resultStale">Inputs changed · recalculate for a new total.</small>
        <small v-else-if="result"><template v-if="Number(result.calculation.quantity) > 1">{{ printCount(result.calculation.quantity) }} · {{ money(result.calculation.list_unit_price) }} per print</template><template v-else>{{ printCount(result.calculation.quantity) }}</template> <button class="price-breakdown-link" type="button" @click="resultBreakdownOpen = true">View breakdown <ChevronUp :size="13" /></button></small>
        <small v-else>Nothing is saved by this calculator.</small>
      </div>
      <div class="price-action-buttons">
        <button class="button primary price-calculate" type="submit" form="price-calculator-form" :disabled="calculating || loadingPaper">
          <Calculator :size="15" /> {{ calculating ? "Calculating…" : resultStale ? "Recalculate" : "Calculate price" }}
        </button>
        <button
          v-if="props.estimateRequest && result && !resultStale"
          class="button primary"
          type="button"
          :disabled="creatingEstimate || calculating"
          @click="createEstimate"
        >
          <FilePlus2 :size="15" /> {{ creatingEstimate ? "Starting Estimate…" : "Start Estimate" }}
        </button>
      </div>
    </div>
  </div>
</template>
