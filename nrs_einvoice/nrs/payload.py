import frappe
from frappe.utils import cstr, flt, get_time, getdate


def _money(v):
    return round(abs(flt(v)), 2)


def _address(name):
    if not name:
        return {}
    a = frappe.get_cached_doc("Address", name)
    country = (frappe.db.get_value("Country", a.country, "code") or "ng").upper()
    return {
        "street_name": ", ".join(filter(None, [a.address_line1, a.address_line2])),
        "city_name": a.city or "",
        "postal_zone": a.pincode or "",
        "country": country,
    }


def _phone(v):
    v = "".join(ch for ch in cstr(v) if ch.isdigit() or ch == "+")
    if not v or v.startswith("+"):
        return v
    if v.startswith("234"):
        return "+" + v
    if v.startswith("0"):
        return "+234" + v[1:]
    return "+" + v


def _company_address(si):
    if si.company_address:
        return si.company_address
    try:
        from erpnext.setup.doctype.company.company import get_default_company_address
        return get_default_company_address(si.company)
    except Exception:
        return None


def _customer_address(si):
    if si.customer_address:
        return si.customer_address
    from frappe.contacts.doctype.address.address import get_default_address
    return get_default_address("Customer", si.customer)


def _vat_rate(si):
    for t in si.taxes or []:
        if flt(t.rate):
            return flt(t.rate)
    return 7.5 if flt(si.total_taxes_and_charges) else 0


def build_payload(si, s, irn):
    company = frappe.get_cached_doc("Company", si.company)
    customer = frappe.get_cached_doc("Customer", si.customer)
    rate = _vat_rate(si)
    net = _money(si.net_total)
    tax = _money(si.total_taxes_and_charges)
    gross = _money(si.grand_total)

    payload = {
        "business_id": s.business_id,
        "irn": irn,
        "issue_date": str(getdate(si.posting_date)),
        "issue_time": get_time(si.posting_time).strftime("%H:%M:%S"),
        "due_date": str(getdate(si.due_date or si.posting_date)),
        "invoice_type_code": s.credit_note_type_code if si.is_return else s.default_invoice_type_code,
        "payment_status": "PAID" if flt(si.outstanding_amount) <= 0 else "PENDING",
        "note": cstr(si.remarks)[:500],
        "document_currency_code": si.currency,
        "tax_currency_code": "NGN",
        "accounting_supplier_party": {
            "party_name": company.company_name,
            "tin": company.tax_id,
            "email": s.supplier_email or company.email,
            "telephone": _phone(s.supplier_phone or company.phone_no),
            "business_description": s.business_description or "",
            "postal_address": _address(_company_address(si)),
        },
        "accounting_customer_party": {
            "party_name": si.customer_name,
            "tin": customer.tax_id,
            "email": si.contact_email or customer.email_id,
            "telephone": _phone(si.contact_mobile or customer.mobile_no),
            "business_description": cstr(customer.customer_details)[:300],
            "postal_address": _address(_customer_address(si)),
        },
        "payment_means": [{
            "payment_means_code": s.default_payment_means_code or "10",
            "payment_due_date": str(getdate(si.due_date or si.posting_date)),
        }],
        "tax_total": [{
            "tax_amount": tax,
            "tax_subtotal": [{
                "taxable_amount": net,
                "tax_amount": tax,
                "tax_category": {"id": s.default_tax_category, "percent": rate},
            }],
        }],
        "legal_monetary_total": {
            "line_extension_amount": net,
            "tax_exclusive_amount": net,
            "tax_inclusive_amount": gross,
            "payable_amount": gross,
        },
        "invoice_line": [_line(i, s, si.currency) for i in si.items],
    }

    if si.is_return and si.return_against:
        orig = frappe.db.get_value("Sales Invoice", si.return_against, ["nrs_irn", "posting_date"], as_dict=True)
        if not orig or not orig.nrs_irn:
            frappe.throw(f"Original invoice {si.return_against} has no NRS IRN, so the credit note cannot reference it.")
        payload["billing_reference"] = [{"irn": orig.nrs_irn, "issue_date": str(getdate(orig.posting_date))}]

    return payload


def _line(item, s, currency):
    meta = frappe.db.get_value("Item", item.item_code, ["nrs_hsn_code", "nrs_product_category"], as_dict=True) or {}
    return {
        "hsn_code": meta.get("nrs_hsn_code") or s.default_hsn_code,
        "product_category": meta.get("nrs_product_category") or s.default_product_category,
        "discount_rate": 0,
        "discount_amount": 0,
        "fee_rate": 0,
        "fee_amount": 0,
        "invoiced_quantity": abs(flt(item.qty)),
        "line_extension_amount": _money(item.net_amount),
        "item": {
            "name": item.item_name,
            "description": cstr(item.description)[:300] or item.item_name,
            "sellers_item_identification": item.item_code,
        },
        "price": {
            "price_amount": _money(item.net_rate),
            "base_quantity": 1,
            "price_unit": f"{currency} per {item.uom}",
        },
    }
