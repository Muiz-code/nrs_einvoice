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
