<script setup>
import { nextTick, onMounted, ref, watch } from "vue";
import JsBarcode from "jsbarcode";

const props = defineProps({ value: { type: String, required: true } });
const barcode = ref(null);

async function render() {
  await nextTick();
  if (!barcode.value || !props.value) return;
  JsBarcode(barcode.value, props.value, {
    format: "CODE128",
    width: 1.45,
    height: 46,
    margin: 0,
    marginLeft: 15,
    marginRight: 15,
    displayValue: false,
    background: "transparent",
  });
}

onMounted(render);
watch(() => props.value, render);
</script>

<template>
  <svg ref="barcode" class="barcode-svg" :aria-label="`Code 128 barcode ${value}`" />
</template>
