frappe.ui.form.on("Studio Pricing Model", {
	refresh(frm) {
		if (frm.is_new() || !frm.has_perm("create")) return;

		frm.add_custom_button(__("New Pricing Model"), () => {
			frappe.new_doc("Studio Pricing Model");
		});
		frm.add_custom_button(__("Duplicate Pricing Model"), () => {
			frm.copy_doc((copy) => {
				copy.model_name = "";
			});
		});
	},
});
