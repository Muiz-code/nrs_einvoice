import re

from frappe.utils import getdate


def clean_invoice_number(name):
    """NRS expects an alphanumeric invoice number (no dashes or symbols)."""
    return re.sub(r"[^A-Za-z0-9]", "", name or "")


def build_irn(invoice_name, service_id, posting_date):
    """IRN format: InvoiceNumber-ServiceID-YYYYMMDD"""
    return f"{clean_invoice_number(invoice_name)}-{service_id.strip()}-{getdate(posting_date).strftime('%Y%m%d')}"
