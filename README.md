# NRS E-Invoice for ERPNext

Signs Sales Invoices on the NRS Merchant Buyer Solution (MBS) and stores the IRN, CSID and QR code on the invoice.

## Install
    cd ~/frappe-bench
    bench get-app https://github.com/<you>/nrs_einvoice.git   # or copy this folder into apps/
    bench --site yoursite install-app nrs_einvoice
    bench --site yoursite migrate
    bench restart

## Configure (NRS Settings)
1. Tick Enabled, keep Environment on Sandbox, paste the sandbox Base URL from the NRSMBS dashboard.
2. Paste API Key, API Secret, Service ID and Business ID.
3. Fill supplier email and phone (+234 format).
4. Click Test Connection.

## Master data
- Company: Tax ID = your TIN. Set a company address on invoices.
- Customer: Tax ID = buyer TIN (B2B). Primary address and email.
- Item: NRS HSN Code and NRS Product Category (or set defaults in NRS Settings).
- Sales Taxes template: VAT 7.5%.

## Flow
Submit Sales Invoice -> background job -> validate IRN -> validate invoice -> sign -> IRN/CSID/QR saved.
Failures show in red on the invoice, are logged in NRS E-Invoice Log and retried every 15 minutes.
Use the NRS > Send to NRS button to retry manually. Returns are sent as credit notes (380) referencing the original IRN.

## QR code and print format
- After signing, the app builds the NRS QR from the cryptographic key file (public_key + certificate in NRS Settings) and shows it in the invoice's NRS E-Invoice section.
- Signed invoices without a QR: open the invoice, NRS > Generate QR. The migrate patch also backfills them.
- The app ships a print format, **NRS E-Invoice** (Sales Invoice): supplier and buyer TINs, HSN codes, IRN and QR. Make it the default under Customize Form > Sales Invoice > Default Print Format, and send customers this PDF.
- To use your own print format instead, add:

      {% if doc.nrs_irn %}
        <div>IRN: {{ doc.nrs_irn }}</div>
        {% if doc.nrs_qr_image %}<img src="{{ doc.nrs_qr_image }}" style="width:120px">{% endif %}
      {% endif %}

## Imports and contacts
Data Import leaves the invoice contact empty, so the buyer email falls back to the customer's primary contact, then any contact linked to the customer with an email.

## Deleting
A cancelled invoice that was never signed can be deleted; its NRS logs go with it. Signed invoices cannot be deleted: issue a credit note.

## Before going live, verify
- Endpoint paths in nrs/client.py (PATHS) against the Postman collection in your dashboard.
- Header names (x-api-key / x-api-secret) and the response shape of /invoice/sign.
- Codes (invoice type, tax category, payment means) against the /invoice/resources endpoints.
