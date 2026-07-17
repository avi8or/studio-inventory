import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";

export default defineConfig({
  plugins: [
    frappeui({
      frappeProxy: true,
      lucideIcons: true,
      jinjaBootData: true,
      buildConfig: {
        indexHtmlPath: "../studio_inventory/www/studio_inventory.html",
        emptyOutDir: true,
        sourcemap: true,
      },
    }),
    vue(),
  ],
});
