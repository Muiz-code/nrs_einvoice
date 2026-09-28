import json

import frappe
import requests

# Verify these paths against the Postman collection / API docs in your NRSMBS dashboard.
PATHS = {
    "validate_irn": "/invoice/irn/validate",
    "validate": "/invoice/validate",
    "sign": "/invoice/sign",
    "confirm": "/invoice/confirm/{irn}",
    "download": "/invoice/download/{irn}",
    "transmit": "/invoice/transmit/{irn}",
    "verify_tin": "/utilities/verify-tin",
    "resource": "/invoice/resources/{name}",
}


class NRSError(Exception):
    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


def _extract_error(body):
    if not isinstance(body, dict):
        return None
    err = body.get("error")
    if isinstance(err, dict):
        return err.get("public_message") or err.get("details") or err.get("message")
    if isinstance(err, str):
        return err
    return body.get("message")


class NRSClient:
    def __init__(self, reference_doctype=None, reference_name=None):
        s = frappe.get_single("NRS Settings")
        if not s.enabled:
            raise NRSError("NRS e-invoicing is disabled in NRS Settings")
        self.settings = s
        self.base_url = (s.base_url or "").rstrip("/")
        self.timeout = s.timeout or 30
        self.headers = {
            "x-api-key": s.get_password("api_key"),
            "x-api-secret": s.get_password("api_secret"),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.reference_doctype = reference_doctype
        self.reference_name = reference_name

    # ---- public API ----
    def validate_irn(self, invoice_reference, irn):
        return self._request("validate_irn", "POST", PATHS["validate_irn"], {
            "invoice_reference": invoice_reference,
            "business_id": self.settings.business_id,
            "irn": irn,
        })

    def validate_invoice(self, payload):
        return self._request("validate", "POST", PATHS["validate"], payload)

    def sign_invoice(self, payload):
        return self._request("sign", "POST", PATHS["sign"], payload)

    def confirm(self, irn):
        return self._request("confirm", "GET", PATHS["confirm"].format(irn=irn))

    def download(self, irn):
        return self._request("download", "GET", PATHS["download"].format(irn=irn))

    def transmit(self, irn):
        return self._request("transmit", "POST", PATHS["transmit"].format(irn=irn))

    def verify_tin(self, tin):
        return self._request("verify_tin", "POST", PATHS["verify_tin"], {"tin": tin})

    def resource(self, name):
        return self._request("resource", "GET", PATHS["resource"].format(name=name))

    # ---- internals ----
    def _request(self, action, method, path, payload=None):
        url = self.base_url + path
        status_code, body, ok = None, None, False
        try:
            r = requests.request(method, url, headers=self.headers, json=payload, timeout=self.timeout)
            status_code = r.status_code
            try:
                body = r.json()
            except ValueError:
                body = {"raw": r.text[:5000]}
            ok = 200 <= r.status_code < 300
        except requests.RequestException as e:
            body = {"error": str(e)}

        self._log(action, method, url, payload, status_code, body, ok)

        if not ok:
            raise NRSError(_extract_error(body) or f"NRS request failed ({status_code})", status_code, body)
        return body

    def _log(self, action, method, url, payload, status_code, body, ok):
        try:
            frappe.get_doc({
                "doctype": "NRS E-Invoice Log",
                "reference_doctype": self.reference_doctype,
                "reference_name": self.reference_name,
                "action": action,
                "method": method,
                "url": url,
                "status": "Success" if ok else "Failed",
                "http_status": status_code,
                "request": json.dumps(payload, indent=1, default=str) if payload else None,
                "response": json.dumps(body, indent=1, default=str)[:60000] if body else None,
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error("NRS log write failed")
