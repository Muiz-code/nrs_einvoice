from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
    make_custom_fields()
    ensure_print_format()


def ensure_print_format():
    """Create/refresh the NRS E-Invoice print format from the app's JSON and make it
    the Sales Invoice default when none is set. Safe to run on every migrate."""
    import json
    import os

    import frappe

    path = frappe.get_app_path("nrs_einvoice", "nrs_e_invoice", "print_format", "nrs_e_invoice", "nrs_e_invoice.json")
    with open(path) as f:
        data = json.load(f)
    if frappe.db.exists("Print Format", data["name"]):
        doc = frappe.get_doc("Print Format", data["name"])
        doc.update({k: v for k, v in data.items() if k not in ("doctype", "name")})
        doc.flags.ignore_permissions = True
        doc.save()
    else:
        doc = frappe.get_doc(data)
        doc.flags.ignore_permissions = True
        doc.insert()

    current = frappe.db.get_value(
        "Property Setter",
        {"doc_type": "Sales Invoice", "property": "default_print_format"},
        "value",
    )
    if not current:
        from frappe.custom.doctype.property_setter.property_setter import make_property_setter
        make_property_setter("Sales Invoice", None, "default_print_format", data["name"], "Data", for_doctype=True)
    frappe.db.commit()


def make_custom_fields():
    ro = {"read_only": 1, "allow_on_submit": 1, "no_copy": 1, "print_hide": 1}
    create_custom_fields(
        {
            "Sales Invoice": [
                {"fieldname": "nrs_section", "label": "NRS E-Invoice", "fieldtype": "Section Break",
                 "insert_after": "amended_from", "collapsible": 1},
                {"fieldname": "nrs_status", "label": "NRS Status", "fieldtype": "Select",
                 "options": "\nQueued\nSigned\nFailed", "insert_after": "nrs_section",
                 "in_standard_filter": 1, **ro},
                {"fieldname": "nrs_irn", "label": "IRN", "fieldtype": "Data",
                 "insert_after": "nrs_status", **ro, "print_hide": 0},
                {"fieldname": "nrs_csid", "label": "CSID", "fieldtype": "Small Text",
                 "insert_after": "nrs_irn", **ro},
                {"fieldname": "nrs_submitted_on", "label": "Signed On", "fieldtype": "Datetime",
                 "insert_after": "nrs_csid", **ro},
                {"fieldname": "nrs_col", "fieldtype": "Column Break", "insert_after": "nrs_submitted_on"},
                {"fieldname": "nrs_attempts", "label": "Attempts", "fieldtype": "Int",
                 "insert_after": "nrs_col", **ro},
                {"fieldname": "nrs_last_attempt", "label": "Last Attempt", "fieldtype": "Datetime",
                 "insert_after": "nrs_attempts", **ro},
                {"fieldname": "nrs_error", "label": "NRS Error", "fieldtype": "Small Text",
                 "insert_after": "nrs_last_attempt", **ro},
                {"fieldname": "nrs_qr_code", "label": "QR Payload", "fieldtype": "Long Text",
                 "insert_after": "nrs_error", "hidden": 1, **ro},
                {"fieldname": "nrs_qr_image", "label": "QR Image", "fieldtype": "Long Text",
                 "insert_after": "nrs_qr_code", "hidden": 1, **ro},
                {"fieldname": "nrs_qr_preview", "label": "NRS QR Code", "fieldtype": "HTML",
                 "insert_after": "nrs_qr_image", "print_hide": 1},
                {"fieldname": "nrs_payment_details", "label": "Payment Details (bank)",
                 "fieldtype": "Link", "options": "Terms and Conditions",
                 "insert_after": "nrs_qr_preview", "allow_on_submit": 1, "print_hide": 1,
                 "description": "Bank account printed under Payment Details. Can be changed after submit."},
            ],
            "Item": [
                {"fieldname": "nrs_hsn_code", "label": "NRS HSN Code", "fieldtype": "Data",
                 "insert_after": "item_group"},
                {"fieldname": "nrs_product_category", "label": "NRS Product Category",
                 "fieldtype": "Data", "insert_after": "nrs_hsn_code"},
                {"fieldname": "nrs_price_unit", "label": "NRS Price Unit", "fieldtype": "Data",
                 "insert_after": "nrs_product_category",
                 "description": "Unit code from the NRS quantity code list. Leave blank to use the default in NRS Settings."},
            ],
        },
        update=True,
    )
