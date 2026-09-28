frappe.ui.form.on("NRS Settings", {
	test_connection(frm) {
		frappe.call({
			method: "nrs_einvoice.nrs_e_invoice.doctype.nrs_settings.nrs_settings.test_connection",
			freeze: true,
			freeze_message: __("Calling NRS..."),
			callback(r) {
				if (r.message && r.message.ok) {
					frappe.msgprint(__("Connected to NRS. Invoice types returned: {0}", [r.message.count ?? "?"]));
				}
			},
		});
	},
});
