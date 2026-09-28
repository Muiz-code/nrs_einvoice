frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		const st = frm.doc.nrs_status;

		if (st === "Failed" && frm.doc.nrs_error) {
			frm.set_intro(__("NRS submission failed: {0}", [frm.doc.nrs_error]), "red");
		} else if (st === "Signed") {
			frm.set_intro(__("NRS signed. IRN: {0}", [frm.doc.nrs_irn]), "green");
		}

		if (st !== "Signed") {
			frm.add_custom_button(__("Send to NRS"), () => {
				frappe.call({
					method: "nrs_einvoice.nrs.submission.submit_to_nrs",
					args: { invoice: frm.doc.name },
					freeze: true,
					freeze_message: __("Submitting to NRS..."),
					callback: () => frm.reload_doc(),
				});
			}, __("NRS"));
		} else {
			frm.add_custom_button(__("Confirm on NRS"), () => {
				frappe.call({
					method: "nrs_einvoice.nrs.submission.confirm_on_nrs",
					args: { invoice: frm.doc.name },
					freeze: true,
					callback: (r) => frappe.msgprint({
						title: __("NRS Status"),
						message: "<pre>" + frappe.utils.escape_html(JSON.stringify(r.message, null, 2)) + "</pre>",
					}),
				});
			}, __("NRS"));
		}
	},
});
