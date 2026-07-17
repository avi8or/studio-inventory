frappe.ui.form.on("Quotation", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0 || !frm.has_perm("write")) return;
		frm.add_custom_button(__("Add Calculated Print"), () => open_print_calculator(frm), __("Add"));
	},
});

let pricing_context;

async function call_pricing(method, args = {}) {
	const response = await frappe.call({
		method: `studio_inventory.pricing_api.${method}`,
		type: "POST",
		args,
	});
	return response.message;
}

async function get_pricing_context() {
	if (!pricing_context) pricing_context = await call_pricing("get_pricing_context");
	return pricing_context;
}

function money(value, currency) {
	return format_currency(value || 0, currency || frappe.defaults.get_default("currency"));
}

function error_message(error) {
	if (Array.isArray(error?.messages) && error.messages.length) return error.messages.join(" ");
	return error?.message || __("ERPNext could not complete the pricing request.");
}

function cost_source_html(paper) {
	const basis = paper?.basis;
	if (!basis) {
		return `<div class="text-muted">${__("No current Buying Item Price was found. A Pricing Manager can enter a cost override.")}</div>`;
	}
	const supplier = basis.supplier ? ` · ${frappe.utils.escape_html(basis.supplier)}` : "";
	const merchant_url = basis.merchant_url
		? frappe.utils.escape_html(encodeURI(basis.merchant_url))
		: "";
	const link = basis.merchant_url
		? ` · <a href="${merchant_url}" target="_blank" rel="noopener">${__("merchant")}</a>`
		: "";
	return `<div class="text-muted">${__("Cost basis")}: ${money(basis.rate)} / ${frappe.utils.escape_html(basis.uom)}${supplier}${link}<br>${__("Normalized cost")}: ${Number(basis.cost_per_sq_in).toFixed(6)} / sq in</div>`;
}

function preview_html(result, currency) {
	const calculation = result.calculation;
	const consumption = result.consumption;
	const warning = result.warnings?.length
		? `<div class="alert alert-warning mt-3 mb-0">${result.warnings.map(frappe.utils.escape_html).join("<br>")}</div>`
		: "";
	return `
		<div class="rounded border p-3">
			<div class="d-flex justify-content-between"><span>${__("Unit price")}</span><strong>${money(calculation.list_unit_price, currency)}</strong></div>
			<div class="d-flex justify-content-between"><span>${__("Line total")}</span><strong>${money(calculation.line_total, currency)}</strong></div>
			<hr>
			<div class="d-flex justify-content-between"><span>${__("Estimated paper")}</span><span>${format_number(consumption.quantity)} ${frappe.utils.escape_html(consumption.uom)}</span></div>
			<div class="d-flex justify-content-between"><span>${__("Internal cost")}</span><span>${money(calculation.total_cost, currency)}</span></div>
			<div class="d-flex justify-content-between"><span>${__("Gross margin")}</span><span>${format_number(calculation.gross_margin_pct, null, 1)}%</span></div>
		</div>${warning}`;
}

async function open_print_calculator(frm) {
	let context;
	try {
		context = await get_pricing_context();
	} catch (error) {
		frappe.msgprint({
			title: __("Pricing is not configured"),
			message: frappe.utils.escape_html(error_message(error)),
			indicator: "red",
		});
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Add Calculated Print"),
		fields: [
			{
				fieldname: "print_item",
				fieldtype: "Link",
				options: "Item",
				label: __("Print Item"),
				default: context.default_print_item,
				reqd: 1,
				get_query: () => ({ filters: { disabled: 0, is_sales_item: 1, has_variants: 0 } }),
			},
			{
				fieldname: "paper_item",
				fieldtype: "Link",
				options: "Item",
				label: __("Paper"),
				reqd: 1,
				get_query: () => ({
					filters: { disabled: 0, is_stock_item: 1, has_variants: 0, stock_uom: ["in", ["Sheet", "Foot"]] },
				}),
				onchange: async () => {
					const item_code = dialog.get_value("paper_item");
					if (!item_code) return;
					try {
						const paper = await call_pricing("get_paper_cost", { item_code });
						dialog.get_field("cost_status").$wrapper.html(cost_source_html(paper));
					} catch (error) {
						dialog.get_field("cost_status").$wrapper.html(`<div class="text-danger">${frappe.utils.escape_html(error_message(error))}</div>`);
					}
				},
			},
			{ fieldname: "dimensions_section", fieldtype: "Section Break", label: __("Print specification") },
			{ fieldname: "artwork_width_in", fieldtype: "Float", label: __("Artwork width (in)"), reqd: 1 },
			{ fieldname: "artwork_height_in", fieldtype: "Float", label: __("Artwork height (in)"), reqd: 1 },
			{ fieldname: "dimension_column", fieldtype: "Column Break" },
			{ fieldname: "border_in", fieldtype: "Float", label: __("Border on each side (in)"), default: 0 },
			{ fieldname: "quantity", fieldtype: "Int", label: __("Quantity"), default: 1, reqd: 1 },
			{ fieldname: "cost_section", fieldtype: "Section Break", label: __("Internal costing") },
			{ fieldname: "time_minutes", fieldtype: "Float", label: __("Production time (minutes)"), default: 0 },
			{
				fieldname: "ink_cost_per_sq_in",
				fieldtype: "Currency",
				label: __("Ink cost / sq in"),
				precision: 6,
				default: context.ink_cost_per_sq_in,
			},
			{ fieldname: "cost_column", fieldtype: "Column Break" },
			{
				fieldname: "cost_override",
				fieldtype: "Currency",
				label: __("Paper cost / sq in override"),
				precision: 6,
				hidden: !context.can_override_cost,
				description: __("Leave blank to use the current Buying Item Price."),
			},
			{ fieldname: "cost_status", fieldtype: "HTML" },
			{ fieldname: "preview_section", fieldtype: "Section Break", label: __("Preview") },
			{ fieldname: "preview", fieldtype: "HTML" },
		],
		primary_action_label: __("Add to quotation"),
		primary_action: async (values) => {
			try {
				const result = await call_pricing("calculate_print", { payload: values });
				await add_calculated_row(frm, values, result);
				dialog.hide();
				frappe.show_alert({
					message: __("Calculated print added at {0} each", [money(result.calculation.list_unit_price, frm.doc.currency)]),
					indicator: result.warnings?.length ? "orange" : "green",
				});
			} catch (error) {
				frappe.msgprint({
					title: __("Could not calculate print"),
					message: frappe.utils.escape_html(error_message(error)),
					indicator: "red",
				});
			}
		},
	});

	dialog.set_secondary_action_label(__("Preview"));
	dialog.set_secondary_action(async () => {
		const values = dialog.get_values();
		if (!values) return;
		try {
			const result = await call_pricing("calculate_print", { payload: values });
			dialog.get_field("preview").$wrapper.html(preview_html(result, frm.doc.currency));
		} catch (error) {
			dialog.get_field("preview").$wrapper.html(`<div class="text-danger">${frappe.utils.escape_html(error_message(error))}</div>`);
		}
	});
	dialog.show();
}

async function add_calculated_row(frm, values, result) {
	const row = frm.add_child("items");
	await frappe.model.set_value(row.doctype, row.name, "item_code", result.print_item.item_code);
	await frappe.model.set_value(row.doctype, row.name, "qty", result.calculation.quantity);
	await frappe.model.set_value(row.doctype, row.name, "description", result.description);
	await frappe.model.set_value(row.doctype, row.name, "si_is_calculated_print", 1);
	await frappe.model.set_value(row.doctype, row.name, "si_paper_item", result.paper_item.item_code);
	await frappe.model.set_value(row.doctype, row.name, "si_artwork_width_in", values.artwork_width_in);
	await frappe.model.set_value(row.doctype, row.name, "si_artwork_height_in", values.artwork_height_in);
	await frappe.model.set_value(row.doctype, row.name, "si_border_in", values.border_in || 0);
	await frappe.model.set_value(row.doctype, row.name, "si_time_minutes", values.time_minutes || 0);
	await frappe.model.set_value(row.doctype, row.name, "si_ink_cost_per_sq_in", values.ink_cost_per_sq_in);
	await frappe.model.set_value(row.doctype, row.name, "si_paper_cost_per_sq_in", result.paper_cost_per_sq_in);
	await frappe.model.set_value(row.doctype, row.name, "si_cost_override", result.cost_was_overridden ? 1 : 0);
	await frappe.model.set_value(row.doctype, row.name, "si_cost_source", JSON.stringify(result.cost_source));
	await frappe.model.set_value(row.doctype, row.name, "si_estimated_stock_qty", result.consumption.quantity);
	await frappe.model.set_value(row.doctype, row.name, "si_estimated_stock_uom", result.consumption.uom);
	await frappe.model.set_value(row.doctype, row.name, "si_internal_cost", result.calculation.total_cost);
	await frappe.model.set_value(row.doctype, row.name, "si_gross_margin_pct", result.calculation.gross_margin_pct);
	await frappe.model.set_value(row.doctype, row.name, "si_formula_version", result.calculation.formula_version);
	await frappe.model.set_value(row.doctype, row.name, "si_calculation_snapshot", result.snapshot);
	await frappe.model.set_value(row.doctype, row.name, "price_list_rate", result.calculation.list_unit_price);
	await frappe.model.set_value(row.doctype, row.name, "rate", result.calculation.list_unit_price);
	frm.refresh_field("items");
	frm.dirty();
}
