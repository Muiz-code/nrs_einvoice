app_name = "nrs_einvoice"
app_title = "NRS E-Invoice"
app_publisher = "Raavon Limited"
app_description = "NRS MBS e-invoicing for ERPNext"
app_license = "MIT"
required_apps = ["erpnext"]

after_install = "nrs_einvoice.install.after_install"
after_migrate = ["nrs_einvoice.install.make_custom_fields"]

doctype_js = {"Sales Invoice": "public/js/sales_invoice.js"}

doc_events = {
    "Sales Invoice": {
        "on_submit": "nrs_einvoice.nrs.submission.enqueue_submission",
    }
}

scheduler_events = {
    "cron": {
        "*/15 * * * *": ["nrs_einvoice.nrs.submission.retry_pending"],
    }
}
