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


def _mark_signed(si, s, irn, data):
    csid = data.get("csid") or data.get("CSID") or ""
    qr_text = data.get("qr_code") or data.get("qr") or ""
    if not qr_text and s.public_key and s.certificate:
        qr_text = qr.build_qr_string(irn, s.public_key, s.certificate)

    si.db_set({
        "nrs_status": "Signed",
        "nrs_csid": csid,
        "nrs_qr_code": qr_text,
        "nrs_qr_image": qr.qr_data_uri(qr_text) if qr_text else None,
        "nrs_error": None,
        "nrs_submitted_on": now_datetime(),
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
