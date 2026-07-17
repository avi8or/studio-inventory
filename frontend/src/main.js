import { createApp } from "vue";
import { FrappeUI, frappeRequest, setConfig } from "frappe-ui";
import "frappe-ui/style.css";
import "./index.css";
import App from "./App.vue";

setConfig("resourceFetcher", frappeRequest);
createApp(App).use(FrappeUI).mount("#app");
