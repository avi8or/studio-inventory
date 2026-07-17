<script setup>
import { computed } from "vue";

import BarcodeSvg from "./BarcodeSvg.vue";
import commandCardData from "./commandCardData.json";
import QrCodeSvg from "./QrCodeSvg.vue";
import { inventoryUrl } from "./scannerCommands.js";

const props = defineProps({ baseUrl: { type: String, required: true } });

const openUrl = computed(() => inventoryUrl(props.baseUrl));
const modes = computed(() => commandCardData.modes.map((mode) => ({
  ...mode,
  url: inventoryUrl(props.baseUrl, mode.mode),
})));
const { entryModes, keys, actions } = commandCardData;
</script>

<template>
  <article class="command-card">
    <header class="command-card-header">
      <div><span>STUDIO INVENTORY</span><h1>Scanner command card</h1></div>
      <strong>SCAN → ENTER</strong>
    </header>

    <section class="command-open-section">
      <QrCodeSvg :value="openUrl" :size="150" />
      <div>
        <span class="command-step">START HERE</span>
        <h2>Open Studio Inventory</h2>
        <p>Use a phone camera, or focus the browser address bar and scan with the Tera. The scanner's Enter suffix opens the page.</p>
        <code>{{ openUrl }}</code>
      </div>
    </section>

    <section class="command-section">
      <div class="command-section-heading"><span>1</span><div><h2>Choose a mode, then scan the paper label</h2><p>The QR codes work as browser deep links; the next scan selects the roll or pack.</p></div></div>
      <div class="mode-command-grid">
        <div v-for="mode in modes" :key="mode.label" class="mode-command">
          <QrCodeSvg :value="mode.url" :size="116" />
          <div><strong>{{ mode.label }}</strong><span>{{ mode.detail }}</span></div>
        </div>
      </div>
    </section>

    <section class="command-section compact-section">
      <div class="command-section-heading"><span>2</span><div><h2>For consumption, choose how to enter it</h2><p>Skip this for Receive or Count.</p></div></div>
      <div class="entry-command-grid">
        <div v-for="entry in entryModes" :key="entry.code" class="barcode-command">
          <strong>{{ entry.label }}</strong><BarcodeSvg :value="entry.code" /><code>{{ entry.code }}</code>
        </div>
      </div>
    </section>

    <section class="command-section keypad-section">
      <div class="command-section-heading"><span>3</span><div><h2>Enter quantity</h2><p>Feet allow decimals; packs and sheets remain whole numbers.</p></div></div>
      <div class="command-keypad">
        <div v-for="key in keys" :key="key.code" class="key-command" :class="{ wide: key.wide }">
          <strong>{{ key.label }}</strong><BarcodeSvg :value="key.code" />
        </div>
      </div>
    </section>

    <section class="command-section compact-section">
      <div class="command-section-heading"><span>4</span><div><h2>Finish</h2><p>Confirm never bypasses the app's ERPNext validation.</p></div></div>
      <div class="action-command-grid">
        <div v-for="action in actions" :key="action.code" class="barcode-command action-command" :class="action.tone">
          <div><strong>{{ action.label }}</strong><span>{{ action.detail }}</span></div>
          <BarcodeSvg :value="action.code" /><code>{{ action.code }}</code>
        </div>
      </div>
    </section>

    <footer>Keep the scanner connected as Bluetooth HID or 2.4G keyboard input with its Enter suffix enabled. Recommended finish: matte lamination.</footer>
  </article>
</template>
