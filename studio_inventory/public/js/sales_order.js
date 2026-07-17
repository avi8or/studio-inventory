frappe.ui.form.on("Sales Order", {
	async refresh(frm) {
		if (frm.doc.docstatus !== 0 || frm.doc.customer || frm.__studio_inventory_customer_checked) return;
		const quotation = (frm.doc.items || []).find((row) => row.prevdoc_docname)?.prevdoc_docname;
		if (!quotation) return;
		frm.__studio_inventory_customer_checked = true;
		try {
			const response = await frappe.call({
				method: "studio_inventory.crm_bridge.get_or_create_customer",
				type: "POST",
				args: { quotation },
			});
			if (response.message) await frm.set_value("customer", response.message);
		} catch (error) {
			frm.__studio_inventory_customer_checked = false;
			const message = Array.isArray(error?.messages) && error.messages.length
				? error.messages.join(" ")
				: error?.message || __("Could not create the ERPNext Customer for this CRM Deal.");
			frappe.msgprint({
				title: __("Customer is required"),
				message: frappe.utils.escape_html(message),
				indicator: "red",
			});
		}
	},
});
