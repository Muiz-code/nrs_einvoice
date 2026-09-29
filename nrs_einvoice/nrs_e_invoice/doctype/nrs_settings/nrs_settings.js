frappe.ui.form.on("NRS Settings", {
	search_codes(frm) {
		frappe.call({
			method: "nrs_einvoice.nrs_e_invoice.doctype.nrs_settings.nrs_settings.search_codes",
			args: { list_name: frm.doc.code_search_list || "hs-codes", text: frm.doc.code_search_text },
			freeze: true,
			freeze_message: __("Searching NRS codes..."),
			callback(r) {
				const rows = (r.message || []).map((row) => {
					const vals = Object.values(row).map((v) => `<td>${frappe.utils.escape_html(String(v))}</td>`).join("");
					return `<tr>${vals}</tr>`;
				}).join("");
				frappe.msgprint({
					title: __("Matches ({0})", [(r.message || []).length]),
					message: rows ? `<table class="table table-bordered">${rows}</table>` : __("No matches. Try another word."),
					wide: true,
				});
			},
		});
	},
	fetch_code_lists(frm) {
		frappe.call({
			method: "nrs_einvoice.nrs_e_invoice.doctype.nrs_settings.nrs_settings.fetch_code_lists",
			freeze: true,
			freeze_message: __("Fetching code lists from NRS..."),
			callback(r) {
				const rows = Object.entries(r.message || {}).map(([k, v]) => `<tr><td>${k}</td><td>${frappe.utils.escape_html(String(v))}</td></tr>`).join("");
				frappe.msgprint({
					title: __("NRS Code Lists"),
					message: `<table class="table table-bordered">${rows}</table><p>Open <b>NRS E-Invoice Log</b> (action: resource) to see the full lists.</p>`,
				});
			},
		});
	},
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
