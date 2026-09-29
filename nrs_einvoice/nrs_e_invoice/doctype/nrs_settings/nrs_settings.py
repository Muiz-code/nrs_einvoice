import frappe
from frappe.model.document import Document


class NRSSettings(Document):
    def validate(self):
        if self.base_url:
            self.base_url = self.base_url.strip().rstrip("/")
        if self.service_id and len(self.service_id.strip()) != 8:
            frappe.msgprint("Service ID is usually 8 characters. Double check it on the NRSMBS dashboard.")


@frappe.whitelist()
def test_connection():
    frappe.only_for("System Manager")
    from nrs_einvoice.nrs.client import NRSClient

    res = NRSClient().resource("invoice-types")
    data = res.get("data") if isinstance(res, dict) else res
    return {"ok": True, "count": len(data) if isinstance(data, list) else None}


@frappe.whitelist()
def fetch_code_lists():
    """Pull NRS reference lists. Each call is saved in NRS E-Invoice Log so codes can be looked up there."""
    frappe.only_for("System Manager")
    from nrs_einvoice.nrs.client import NRSClient, NRSError

    client = NRSClient()
    out = {}
    for name in ["hs-codes", "services-codes", "service-codes", "product-categories", "tax-categories", "payment-means", "currencies"]:
        try:
            res = client.resource(name)
            data = res.get("data") if isinstance(res, dict) else res
            out[name] = len(data) if isinstance(data, list) else "ok"
        except NRSError as e:
            out[name] = f"not available ({e})"
    frappe.db.commit()
    return out


@frappe.whitelist()
def search_codes(list_name, text):
    """Search an NRS code list by word or code, so users can pick valid codes."""
    frappe.only_for("System Manager")
    from nrs_einvoice.nrs.client import NRSClient

    if list_name not in ("hs-codes", "services-codes"):
        frappe.throw("Unknown list")
    text = (text or "").strip().lower()
    if len(text) < 2:
        frappe.throw("Type at least 2 characters to search")
    res = NRSClient().resource(list_name)
    data = res.get("data") if isinstance(res, dict) else res
    out = []
    for row in data or []:
        blob = " ".join(str(v) for v in row.values()).lower() if isinstance(row, dict) else str(row).lower()
        if text in blob:
            out.append(row)
        if len(out) >= 60:
            break
    return out
