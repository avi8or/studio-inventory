<script setup>
import { nextTick, onMounted, ref, watch } from "vue";
import QRCode from "qrcode";

const props = defineProps({
  value: { type: String, required: true },
  size: { type: Number, default: 144 },
});

const markup = ref("");

async function render() {
  await nextTick();
  if (!props.value) return;
  markup.value = await QRCode.toString(props.value, {
    type: "svg",
    width: props.size,
    margin: 1,
    errorCorrectionLevel: "M",
    color: { dark: "#000000", light: "#ffffff" },
  });
}

onMounted(render);
watch(() => [props.value, props.size], render);
</script>

<template>
  <div class="qr-code-svg" role="img" :aria-label="`QR code for ${value}`" v-html="markup" />
</template>
