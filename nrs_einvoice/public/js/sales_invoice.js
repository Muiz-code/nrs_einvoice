frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		render_qr(frm);
		if (frm.doc.docstatus !== 1) return;
		const st = frm.doc.nrs_status;

		if (st === "Failed" && frm.doc.nrs_error) {
			frm.set_intro(__("NRS submission failed: {0}", [frm.doc.nrs_error]), "red");
		} else if (st === "Signed" && !frm.doc.nrs_qr_image) {
			frm.set_intro(__("NRS signed. IRN: {0}. QR code missing: use NRS > Generate QR.", [frm.doc.nrs_irn]), "orange");
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
			frm.add_custom_button(frm.doc.nrs_qr_image ? __("Regenerate QR") : __("Generate QR"), () => {
				frappe.call({
					method: "nrs_einvoice.nrs.submission.generate_qr",
					args: { invoice: frm.doc.name, force: frm.doc.nrs_qr_image ? 1 : 0 },
					freeze: true,
					freeze_message: __("Building QR code..."),
					callback: () => frm.reload_doc(),
				});
			}, __("NRS"));
		}
	},
});

function render_qr(frm) {
	const field = frm.get_field("nrs_qr_preview");
	if (!field) return;
	const img = frm.doc.nrs_qr_image;
	field.$wrapper.html(img && img.startsWith("data:image/")
		? `<div style="margin-top:8px"><div class="text-muted small">${__("NRS QR Code")}</div>
		   <img src="${img}" style="width:140px;height:140px;border:1px solid var(--border-color);padding:4px;background:#fff"></div>`
		: "");
}
