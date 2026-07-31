import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const scriptPath = new URL(
	"../../studio_inventory/studio_inventory/doctype/studio_pricing_model/studio_pricing_model.js",
	import.meta.url,
);

async function loadFormHandlers() {
	const source = await readFile(scriptPath, "utf8");
	let handlers;
	const calls = {
		newDoc: [],
	};
	const context = {
		__: (value) => value,
		frappe: {
			new_doc: (doctype) => calls.newDoc.push(doctype),
			ui: {
				form: {
					on: (doctype, registeredHandlers) => {
						assert.equal(doctype, "Studio Pricing Model");
						handlers = registeredHandlers;
					},
				},
			},
		},
	};
	vm.runInNewContext(source, context);
	return { calls, handlers };
}

function existingForm({ canCreate = true } = {}) {
	const buttons = new Map();
	const copies = [];
	return {
		add_custom_button(label, action) {
			buttons.set(label, action);
		},
		buttons,
		copies,
		copy_doc(initialize) {
			const copy = { model_name: "Standard Pricing", material_markup: 2, rules: [{ value: 1.15 }] };
			initialize(copy);
			copies.push(copy);
		},
		has_perm(permission) {
			return permission === "create" && canCreate;
		},
		is_new() {
			return false;
		},
	};
}

test("adds explicit new and duplicate buttons to an existing pricing model", async () => {
	const { calls, handlers } = await loadFormHandlers();
	const frm = existingForm();

	handlers.refresh(frm);

	assert.deepEqual([...frm.buttons.keys()], ["New Pricing Model", "Duplicate Pricing Model"]);
	frm.buttons.get("New Pricing Model")();
	assert.deepEqual(calls.newDoc, ["Studio Pricing Model"]);

	frm.buttons.get("Duplicate Pricing Model")();
	assert.equal(frm.copies[0].model_name, "");
	assert.equal(frm.copies[0].material_markup, 2);
	assert.deepEqual(frm.copies[0].rules, [{ value: 1.15 }]);
});

test("hides creation shortcuts when the user cannot create pricing models", async () => {
	const { handlers } = await loadFormHandlers();
	const frm = existingForm({ canCreate: false });

	handlers.refresh(frm);

	assert.equal(frm.buttons.size, 0);
});
