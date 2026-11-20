import frappe
from frappe.utils import add_to_date, cint, now_datetime

from nrs_einvoice.nrs import qr
from nrs_einvoice.nrs.client import NRSClient, NRSError
from nrs_einvoice.nrs.irn import build_irn
from nrs_einvoice.nrs.payload import build_payload


def _settings():
    return frappe.get_single("NRS Settings")


def enqueue_submission(doc, method=None):
    s = _settings()
    if not (s.enabled and s.submit_on_invoice_submit):
        return
    doc.db_set("nrs_status", "Queued", update_modified=False)
    frappe.enqueue(
        "nrs_einvoice.nrs.submission.process_invoice",
        queue="short",
        timeout=300,
        enqueue_after_commit=True,
        job_id=f"nrs::{doc.name}",
        deduplicate=True,
        invoice=doc.name,
    )


def process_invoice(invoice):
    si = frappe.get_doc("Sales Invoice", invoice)
    if si.docstatus != 1 or si.nrs_status == "Signed":
        return

    s = _settings()
    irn = si.nrs_irn or build_irn(si.name, s.service_id, si.posting_date)
    si.db_set({
        "nrs_irn": irn,
        "nrs_attempts": cint(si.nrs_attempts) + 1,
        "nrs_last_attempt": now_datetime(),
    }, update_modified=False)

    try:
        client = NRSClient("Sales Invoice", si.name)

        # Retry safety: if this IRN was already signed on a previous attempt, just mark it.
        if cint(si.nrs_attempts) > 1 and _already_signed(client, irn):
            _mark_signed(si, s, irn, {})
            return

        payload = build_payload(si, s, irn)
        client.validate_irn(irn.split("-")[0], irn)
        client.validate_invoice(payload)
        resp = client.sign_invoice(payload)
        _mark_signed(si, s, irn, (resp or {}).get("data") or {})

        if s.transmit_after_sign:
            try:
                client.transmit(irn)
            except NRSError as e:
                si.db_set("nrs_error", f"Signed, but transmit failed: {e}", update_modified=False)

    except NRSError as e:
        si.db_set({"nrs_status": "Failed", "nrs_error": str(e)[:1000]}, update_modified=False)
    except Exception as e:
        si.db_set({"nrs_status": "Failed", "nrs_error": str(e)[:1000]}, update_modified=False)
        frappe.log_error(f"NRS submission error: {si.name}")


def _already_signed(client, irn):
    try:
        client.confirm(irn)
        return True
    except NRSError:
        return False


def _qr_fields(s, irn, data=None):
    """QR payload + PNG data URI. Uses NRS's own QR if the sign response has one,
    otherwise builds it from the cryptographic key file (public_key + certificate).
    Never raises: a QR problem must not undo a successful signing."""
    data = data or {}
    qr_text = data.get("qr_code") or data.get("qr") or data.get("qrCode") or ""
    try:
        if not qr_text:
            if not (s.public_key and s.certificate):
                return {}, "QR not generated: paste public_key and certificate from the NRS cryptographic key file into NRS Settings."
            qr_text = qr.build_qr_string(irn, s.public_key, s.certificate)
        return {"nrs_qr_code": qr_text, "nrs_qr_image": qr.qr_data_uri(qr_text)}, None
    except Exception as e:
        frappe.log_error(f"NRS QR generation failed: {irn}")
        return {}, f"QR not generated: {e}"


def _mark_signed(si, s, irn, data):
    csid = data.get("csid") or data.get("CSID") or ""
    qr_values, qr_error = _qr_fields(s, irn, data)
    si.db_set({
        "nrs_status": "Signed",
        "nrs_csid": csid,
        "nrs_error": qr_error,
        "nrs_submitted_on": now_datetime(),
        **qr_values,
    }, update_modified=False)


def retry_pending():
    s = _settings()
    if not s.enabled:
        return
    cutoff = add_to_date(now_datetime(), minutes=-10)
    names = frappe.db.sql_list(
        """select name from `tabSales Invoice`
           where docstatus = 1 and nrs_status in ('Queued', 'Failed')
             and ifnull(nrs_attempts, 0) < %s
             and (nrs_last_attempt is null or nrs_last_attempt < %s)
           order by posting_date limit 50""",
        (cint(s.max_attempts) or 5, cutoff),
    )
    for name in names:
        process_invoice(name)
        frappe.db.commit()


@frappe.whitelist()
def submit_to_nrs(invoice):
    frappe.has_permission("Sales Invoice", "submit", invoice, throw=True)
    process_invoice(invoice)
    return frappe.db.get_value("Sales Invoice", invoice, ["nrs_status", "nrs_irn", "nrs_error"], as_dict=True)


@frappe.whitelist()
def confirm_on_nrs(invoice):
    frappe.has_permission("Sales Invoice", "read", invoice, throw=True)
    irn = frappe.db.get_value("Sales Invoice", invoice, "nrs_irn")
    if not irn:
        frappe.throw("This invoice has no IRN yet.")
    return NRSClient("Sales Invoice", invoice).confirm(irn)


@frappe.whitelist()
def generate_qr(invoice, force=0):
    """Build (or rebuild) the QR for an invoice that is already signed on NRS. No NRS call is made."""
    frappe.has_permission("Sales Invoice", "write", invoice, throw=True)
    si = frappe.get_doc("Sales Invoice", invoice)
    if si.nrs_status != "Signed" or not si.nrs_irn:
        frappe.throw("Only invoices already signed on NRS can get a QR code.")
    if si.nrs_qr_image and not cint(force):
        return {"ok": True, "message": "QR already present."}
    values, err = _qr_fields(_settings(), si.nrs_irn)
    if err:
        frappe.throw(err)
    si.db_set({**values, "nrs_error": None}, update_modified=False)
    return {"ok": True, "message": "QR generated."}


def backfill_missing_qr():
    """Patch/console helper: add QR to every signed invoice that has none."""
    s = _settings()
    for name, irn in frappe.db.sql(
        """select name, nrs_irn from `tabSales Invoice`
           where nrs_status = 'Signed' and ifnull(nrs_irn, '') != '' and ifnull(nrs_qr_image, '') = ''"""
    ):
        values, _err = _qr_fields(s, irn)
        if values:
            frappe.db.set_value("Sales Invoice", name, values, update_modified=False)
    frappe.db.commit()


def delete_logs_on_trash(doc, method=None):
    """Let a cancelled, never-signed invoice be deleted: drop its NRS logs first.
    Signed invoices keep their audit trail (and cannot reach here unless cancelled)."""
    if doc.get("nrs_status") == "Signed":
        frappe.throw("This invoice is signed on NRS. Keep it for the audit trail; issue a credit note instead.")
    frappe.db.delete("NRS E-Invoice Log", {"reference_doctype": doc.doctype, "reference_name": doc.name})
