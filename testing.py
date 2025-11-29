import argparse
import csv
import datetime as dt
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from collections import defaultdict

# Toggle debug logging here
DEBUG = True
LOG_PATH = "debug_log.csv"

COMPANY_NAME = "Anatomy Shop - (from 1-Apr-23)"
WAREHOUSE_NAME = "Main location"  # hardcoded
DATE_IN_FMT = "%d-%m-%Y %H:%M"


def d(val):
    try:
        return Decimal(str(val).strip()) if str(val).strip() else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return dt.datetime.strptime(raw, DATE_IN_FMT)
    except ValueError:
        return dt.datetime.strptime(raw.split()[0], "%d-%m-%Y")


def tally_date(dt_obj):
    return dt_obj.strftime("%Y%m%d") if dt_obj else ""


def tally_disp_date(dt_obj):
    return dt_obj.strftime("%d %b %y") if dt_obj else ""


def is_interstate(row):
    return row.get("Ship From State", "").strip().lower() != row.get("Ship To State", "").strip().lower()


def fmt_amount(val: Decimal, force_two: bool = False) -> str:
    """
    Format amounts close to ecom export:
    - When force_two is True: always 2 decimals (e.g., 50 -> 50.00, 1016.1 -> 1016.10)
    - Otherwise: keep existing compact style (ints as 1 decimal, drop trailing zeros)
    """
    if force_two:
        return f"{val.quantize(Decimal('0.01')):.2f}"
    if val == 0:
        return "0"
    if val == val.to_integral():
        return f"{val:.1f}"
    return f"{val.quantize(Decimal('0.01'))}".rstrip("0").rstrip(".") if "." in f"{val}" else f"{val}"


def voucher_type(txn):
    txn = txn.lower()
    if txn == "refund":
        return "Amazon Return"
    if txn == "freereplacement":
        return "Amazon Sales"
    if txn == "cancel":
        return "Amazon Cancel"
    return "Amazon Sales"


def add_text(parent, tag, text):
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def add_gst_rate_details(parent):
    """Attach GST rate detail blocks similar to ecom2tally to prevent Tally recalculation."""
    for head in ["Integrated Tax", "Central Tax", "State Tax", "Cess"]:
        rd = ET.SubElement(parent, "RATEDETAILS.LIST")
        add_text(rd, "GSTRATEDUTYHEAD", head)
        add_text(rd, "GSTRATEVALUATIONTYPE", "Based on Value")


def add_tax_lock_scaffolding(parent):
    """Add empty GST-related allocation lists so Tally keeps supplied tax amounts."""
    for tag in [
        "SERVICETAXDETAILS.LIST",
        "BANKALLOCATIONS.LIST",
        "SERVICETAXDETAILS.LIST",  # duplicate to mirror ecom2tally structure
        "CATEGORYALLOCATIONS.LIST",
        "BANKALLOCATIONS.LIST",    # duplicate position to mirror ecom2tally structure
        "BILLALLOCATIONS.LIST",
        "INTERESTCOLLECTION.LIST",
        "OLDAUDITENTRIES.LIST",
        "ACCOUNTAUDITENTRIES.LIST",
        "AUDITENTRIES.LIST",
        "INPUTCRALLOCS.LIST",
        "DUTYHEADDETAILS.LIST",
        "EXCISEDUTYHEADDETAILS.LIST",
        "SUMMARYALLOCS.LIST",
        "STPYMTDETAILS.LIST",
        "EXCISEPAYMENTALLOCATIONS.LIST",
        "TAXBILLALLOCATIONS.LIST",
        "TAXOBJECTALLOCATIONS.LIST",
        "TDSEXPENSEALLOCATIONS.LIST",
        "VATSTATUTORYDETAILS.LIST",
        "COSTTRACKALLOCATIONS.LIST",
        "REFVOUCHERDETAILS.LIST",
        "INVOICEWISEDETAILS.LIST",
        "VATITCDETAILS.LIST",
        "ADVANCETAXDETAILS.LIST",
    ]:
        ET.SubElement(parent, tag)


def add_inventory_scaffolding(inv):
    """Add flags and empty lists seen in ecom export to stop GST recompute."""
    add_text(inv, "ISAUTONEGATE", "No")
    add_text(inv, "ISCUSTOMSCLEARANCE", "No")
    add_text(inv, "ISTRACKCOMPONENT", "No")
    add_text(inv, "ISTRACKPRODUCTION", "No")
    add_text(inv, "ISPRIMARYITEM", "No")
    add_text(inv, "ISSCRAP", "No")
    for tag in [
        "DUTYHEADDETAILS.LIST",
        "SUPPLEMENTARYDUTYHEADDETAILS.LIST",
        "TAXOBJECTALLOCATIONS.LIST",
        "REFVOUCHERDETAILS.LIST",
        "EXCISEALLOCATIONS.LIST",
        "EXPENSEALLOCATIONS.LIST",
    ]:
        ET.SubElement(inv, tag)


def build_voucher(row, log_rows):
    txn = row["Transaction Type"].strip()
    vtype = voucher_type(txn)
    inv_no = row["Invoice Number"].strip()
    order_id = row["Order Id"].strip()
    credit_no = row.get("Credit Note No", "").strip()
    dt_invoice = parse_date(row["Invoice Date"])
    dt_order = parse_date(row.get("Order Date", "") or row["Invoice Date"])
    dt_credit = parse_date(row.get("Credit Note Date", "") or row["Invoice Date"])
    ship_state = row["Ship To State"].strip().title()
    ship_city = row["Ship To City"].strip()
    ship_pin = row["Ship To Postal Code"].strip()
    ship_country = row["Ship To Country"].strip() or "IN"
    qty = row.get("Quantity", "1").strip() or "1"

    principal_basis = d(row.get("Principal Amount Basis", 0))
    invoice_amount = d(row.get("Invoice Amount", 0))
    cgst = d(row.get("Cgst Tax", 0))
    sgst = d(row.get("Sgst Tax", 0))
    igst = d(row.get("Igst Tax", 0))
    utgst = d(row.get("Utgst Tax", 0))
    ship_amt = d(row.get("Shipping Amount Basis", 0))
    ship_promo = d(row.get("Shipping Promo Discount Basis", 0))
    ship_promo_tax = d(row.get("Shipping Promo Tax", 0))
    ship_cgst = d(row.get("Shipping Cgst Tax", 0))
    ship_sgst = d(row.get("Shipping Sgst Tax", 0))
    ship_igst = d(row.get("Shipping Igst Tax", 0))
    ship_utgst = d(row.get("Shipping Utgst Tax", 0))

    inter = is_interstate(row)

    if DEBUG:
        log_rows.append({
            "txn": txn,
            "voucher_type": vtype,
            "invoice": inv_no,
            "order": order_id,
            "interstate": inter,
            "principal_basis": str(principal_basis),
            "invoice_amount": str(invoice_amount),
            "cgst": str(cgst),
            "sgst": str(sgst),
            "igst": str(igst),
            "utgst": str(utgst),
            "ship_amt": str(ship_amt),
            "ship_promo": str(ship_promo),
            "ship_promo_tax": str(ship_promo_tax),
            "ship_cgst": str(ship_cgst),
            "ship_sgst": str(ship_sgst),
            "ship_igst": str(ship_igst),
            "ship_utgst": str(ship_utgst),
        })

    voucher = ET.Element("VOUCHER", {
        "REMOTEID": "",
        "VCHKEY": "",
        "VCHTYPE": vtype,
        "ACTION": "Create",
        "OBJVIEW": "Invoice Voucher View",
    })

    add_text(voucher, "STATENAME", ship_state)
    add_text(voucher, "PLACEOFSUPPLY", ship_state)
    add_text(voucher, "URDORIGINALSALEVALUE", "B2C (Small)")
    addr_list = ET.SubElement(voucher, "BASICBUYERADDRESS.LIST", {"TYPE": "String"})
    add_text(addr_list, "BASICBUYERADDRESS", ship_pin)
    old_ids = ET.SubElement(voucher, "OLDAUDITENTRYIDS.LIST", {"TYPE": "Number"})
    add_text(old_ids, "OLDAUDITENTRYIDS", "-1")

    date_for_voucher = dt_credit if txn.lower() == "refund" else dt_invoice
    add_text(voucher, "DATE", tally_date(date_for_voucher))
    add_text(voucher, "REFERENCEDATE", tally_date(dt_invoice) if txn.lower() == "refund" else "")
    add_text(voucher, "GUID", " ")
    add_text(voucher, "VATDEALERTYPE", "Unregistered")
    add_text(voucher, "COUNTRYOFRESIDENCE", "India")
    add_text(voucher, "PARTYNAME", "Amazon.in")
    add_text(voucher, "BASICBUYERNAME", "Amazon B2C Customer")
    add_text(voucher, "VOUCHERTYPENAME", vtype)
    add_text(voucher, "REFERENCE", inv_no if txn.lower() == "refund" else order_id)
    add_text(voucher, "VOUCHERNUMBER", credit_no if txn.lower() == "refund" else inv_no)
    add_text(voucher, "IRN", "")
    add_text(voucher, "BILLTOPLACE", "")
    add_text(voucher, "SHIPTOPLACE", ship_city)
    add_text(voucher, "PARTYPINCODE", ship_pin)
    add_text(voucher, "CONSIGNEEPINCODE", ship_pin)
    add_text(voucher, "PARTYLEDGERNAME", "Amazon.in")
    add_text(voucher, "BASICBASEPARTYNAME", "Amazon.in")
    add_text(voucher, "FBTPAYMENTTYPE", "Default")
    add_text(voucher, "PERSISTEDVIEW", "Invoice Voucher View")
    add_text(voucher, "BASICORDERREF", row.get("Fulfillment Channel", "").strip())
    add_text(voucher, "BASICDUEDATEOFPYMT", row.get("Payment Method Code", "").strip())
    add_text(voucher, "GSTREGISTRATIONTYPE", "Unregistered/Consumer")
    add_text(voucher, "BASICFINALDESTINATION", ship_city)
    add_text(voucher, "BASICDATETIMEOFINVOICE", tally_disp_date(dt_invoice))
    add_text(voucher, "BASICDATETIMEOFREMOVAL", tally_disp_date(dt_invoice))
    add_text(voucher, "CONSIGNEESTATENAME", ship_state)
    add_text(voucher, "EFFECTIVEDATE", tally_date(dt_invoice))
    add_text(voucher, "VCHGSTCLASS", "")
    add_text(voucher, "ENTEREDBY", "")
    add_text(voucher, "DIFFACTUALQTY", "No")
    add_text(voucher, "ISMSTFROMSYNC", "No")
    add_text(voucher, "ASORIGINAL", "No")
    add_text(voucher, "AUDITED", "No")
    add_text(voucher, "FORJOBCOSTING", "No")
    add_text(voucher, "ISOPTIONAL", "No")
    add_text(voucher, "USEFOREXCISE", "No")
    add_text(voucher, "ISFORJOBWORKIN", "No")
    add_text(voucher, "ALLOWCONSUMPTION", "No")
    add_text(voucher, "USEFORINTEREST", "No")
    add_text(voucher, "USEFORGAINLOSS", "No")
    add_text(voucher, "USEFORGODOWNTRANSFER", "No")
    add_text(voucher, "USEFORCOMPOUND", "No")
    add_text(voucher, "USEFORSERVICETAX", "No")
    add_text(voucher, "ISEXCISEVOUCHER", "No")
    add_text(voucher, "EXCISETAXOVERRIDE", "No")
    add_text(voucher, "USEFORTAXUNITTRANSFER", "No")
    add_text(voucher, "EXCISEOPENING", "No")
    add_text(voucher, "USEFORFINALPRODUCTION", "No")
    add_text(voucher, "ISTDSOVERRIDDEN", "No")
    add_text(voucher, "ISTCSOVERRIDDEN", "No")
    add_text(voucher, "ISTDSTCSCASHVCH", "No")
    add_text(voucher, "INCLUDEADVPYMTVCH", "No")
    add_text(voucher, "ISSUBWORKSCONTRACT", "No")
    add_text(voucher, "ISVATOVERRIDDEN", "No")
    add_text(voucher, "IGNOREORIGVCHDATE", "No")
    add_text(voucher, "ISVATPAIDATCUSTOMS", "No")
    add_text(voucher, "ISDECLAREDTOCUSTOMS", "No")
    add_text(voucher, "ISSERVICETAXOVERRIDDEN", "No")
    add_text(voucher, "ISISDVOUCHER", "No")
    add_text(voucher, "ISEXCISEOVERRIDDEN", "No")
    add_text(voucher, "ISEXCISESUPPLYVCH", "No")
    add_text(voucher, "ISGSTOVERRIDDEN", "No")
    add_text(voucher, "GSTNOTEXPORTED", "No")
    add_text(voucher, "ISVATPRINCIPALACCOUNT", "No")
    add_text(voucher, "ISBOENOTAPPLICABLE", "No")
    add_text(voucher, "ISSHIPPINGWITHINSTATE", "No")
    add_text(voucher, "ISOVERSEASTOURISTTRANS", "No")
    add_text(voucher, "ISCANCELLED", "No")
    add_text(voucher, "HASCASHFLOW", "No")
    add_text(voucher, "ISPOSTDATED", "No")
    add_text(voucher, "USETRACKINGNUMBER", "No")
    add_text(voucher, "ISINVOICE", "Yes")
    add_text(voucher, "MFGJOURNAL", "No")
    add_text(voucher, "HASDISCOUNTS", "No")
    add_text(voucher, "ASPAYSLIP", "No")
    add_text(voucher, "ISCOSTCENTRE", "No")
    add_text(voucher, "ISSTXNONREALIZEDVCH", "No")
    add_text(voucher, "ISEXCISEMANUFACTURERON", "No")
    add_text(voucher, "ISBLANKCHEQUE", "No")
    add_text(voucher, "ISVOID", "No")
    add_text(voucher, "ISONHOLD", "No")
    add_text(voucher, "ORDERLINESTATUS", "No" if txn.lower() != "shipment" else "No")
    add_text(voucher, "VATISAGNSTCANCSALES", "No")
    add_text(voucher, "VATISPURCEXEMPTED", "No")
    add_text(voucher, "ISVATRESTAXINVOICE", "No")
    add_text(voucher, "VATISASSESABLECALCVCH", "Yes")
    add_text(voucher, "ISVATDUTYPAID", "Yes")
    add_text(voucher, "ISDELIVERYSAMEASCONSIGNEE", "No")
    add_text(voucher, "ISDISPATCHSAMEASCONSIGNOR", "No")
    add_text(voucher, "ISDELETED", "No")
    add_text(voucher, "CHANGEVCHMODE", "No")
    add_text(voucher, "ALTERID", " ")
    add_text(voucher, "MASTERID", " ")
    add_text(voucher, "VOUCHERKEY", " ")

    if txn.lower() == "refund":
        add_text(voucher, "VATPARTYTRANSRETURNDATE", tally_date(date_for_voucher))
        add_text(voucher, "VATPARTYTRANSRETURNNUMBER", credit_no)
        add_text(voucher, "GSTNATUREOFRETURN", "01-Sales Return")

    inv_order = ET.SubElement(voucher, "INVOICEORDERLIST.LIST")
    add_text(inv_order, "BASICORDERDATE", tally_date(dt_order))
    add_text(inv_order, "BASICPURCHASEORDERNO", order_id)

    # Party ledger entry
    party_le = ET.SubElement(voucher, "LEDGERENTRIES.LIST")
    old = ET.SubElement(party_le, "OLDAUDITENTRYIDS.LIST", {"TYPE": "Number"})
    add_text(old, "OLDAUDITENTRYIDS", "-1")
    add_text(party_le, "LEDGERNAME", "Amazon.in")
    party_amount = abs(invoice_amount) if txn.lower() == "refund" else -invoice_amount
    add_text(party_le, "ISDEEMEDPOSITIVE", "Yes" if party_amount < 0 else "No")
    add_text(party_le, "LEDGERFROMITEM", "No")
    add_text(party_le, "REMOVEZEROENTRIES", "No")
    add_text(party_le, "ISPARTYLEDGER", "Yes")
    add_text(party_le, "ISLASTDEEMEDPOSITIVE", "Yes" if party_amount < 0 else "No")
    add_text(party_le, "AMOUNT", fmt_amount(party_amount))
    bills = ET.SubElement(party_le, "BILLALLOCATIONS.LIST")
    add_text(bills, "NAME", order_id)
    add_text(bills, "BILLTYPE", "New Ref")
    add_text(bills, "AMOUNT", fmt_amount(party_amount))

    # Shipping ledger
    if ship_amt != 0:
        ship_le = ET.SubElement(voucher, "LEDGERENTRIES.LIST")
        old = ET.SubElement(ship_le, "OLDAUDITENTRYIDS.LIST", {"TYPE": "Number"})
        add_text(old, "OLDAUDITENTRYIDS", "-1")
        add_text(ship_le, "APPROPRIATEFOR", "GST")
        add_text(ship_le, "GSTAPPROPRIATETO", "Goods and Services")
        add_text(ship_le, "EXCISEALLOCTYPE", "Based on Value")
        add_text(ship_le, "LEDGERNAME", "Shipping Charges")
        add_text(ship_le, "GSTCLASS", "")
        add_text(ship_le, "ISDEEMEDPOSITIVE", "Yes" if ship_amt < 0 else "No")
        add_text(ship_le, "LEDGERFROMITEM", "No")
        add_text(ship_le, "REMOVEZEROENTRIES", "No")
        add_text(ship_le, "ISPARTYLEDGER", "No")
        add_text(ship_le, "ISLASTDEEMEDPOSITIVE", "Yes" if ship_amt < 0 else "No")
        add_text(ship_le, "AMOUNT", fmt_amount(ship_amt, force_two=True))
        add_text(ship_le, "VATEXPAMOUNT", fmt_amount(ship_amt, force_two=True))
        add_tax_lock_scaffolding(ship_le)
        add_gst_rate_details(ship_le)

    if ship_promo != 0:
        promo_le = ET.SubElement(voucher, "LEDGERENTRIES.LIST")
        old = ET.SubElement(promo_le, "OLDAUDITENTRYIDS.LIST", {"TYPE": "Number"})
        add_text(old, "OLDAUDITENTRYIDS", "-1")
        add_text(promo_le, "LEDGERNAME", "ship-promotion-discount")
        add_text(promo_le, "GSTCLASS", "")
        # Use explicit negative amount (ship_promo) and keep deemed positive as No to avoid double-negating in Tally UI.
        add_text(promo_le, "ISDEEMEDPOSITIVE", "No")
        add_text(promo_le, "LEDGERFROMITEM", "No")
        add_text(promo_le, "REMOVEZEROENTRIES", "No")
        add_text(promo_le, "ISPARTYLEDGER", "No")
        add_text(promo_le, "ISLASTDEEMEDPOSITIVE", "No")
        add_text(promo_le, "AMOUNT", fmt_amount(ship_promo, force_two=True))
        add_text(promo_le, "VATEXPAMOUNT", fmt_amount(ship_promo, force_two=True))
        add_tax_lock_scaffolding(promo_le)
        add_gst_rate_details(promo_le)

    # GST ledgers
    if inter:
        # Include shipping IGST and shipping promo tax (promo tax is typically negative)
        total_igst = igst + ship_igst + ship_promo_tax
        if total_igst != 0:
            igst_le = ET.SubElement(voucher, "LEDGERENTRIES.LIST")
            old = ET.SubElement(igst_le, "OLDAUDITENTRYIDS.LIST", {"TYPE": "Number"})
            add_text(old, "OLDAUDITENTRYIDS", "-1")
            add_text(igst_le, "LEDGERNAME", "IGST @ 18%")
            add_text(igst_le, "GSTCLASS", "")
            add_text(igst_le, "ISDEEMEDPOSITIVE", "Yes" if total_igst < 0 else "No")
            add_text(igst_le, "LEDGERFROMITEM", "No")
            add_text(igst_le, "REMOVEZEROENTRIES", "No")
            add_text(igst_le, "ISPARTYLEDGER", "No")
            add_text(igst_le, "ISLASTDEEMEDPOSITIVE", "Yes" if total_igst < 0 else "No")
            add_text(igst_le, "AMOUNT", fmt_amount(total_igst))
            add_text(igst_le, "VATEXPAMOUNT", fmt_amount(total_igst))
            add_tax_lock_scaffolding(igst_le)
            add_gst_rate_details(igst_le)
    else:
        # For intrastate, shipping promo tax should reduce local GST; if UTGST is in play, assign it there, else split between CGST/SGST.
        if utgst != 0 or ship_utgst != 0:
            total_utgst = utgst + ship_utgst + ship_promo_tax
            total_cgst = cgst + ship_cgst
            total_sgst = sgst + ship_sgst
        else:
            promo_split = ship_promo_tax / Decimal("2")
            total_cgst = cgst + ship_cgst + promo_split
            total_sgst = sgst + ship_sgst + promo_split
            total_utgst = utgst + ship_utgst
        if total_cgst != 0:
            le = ET.SubElement(voucher, "LEDGERENTRIES.LIST")
            old = ET.SubElement(le, "OLDAUDITENTRYIDS.LIST", {"TYPE": "Number"})
            add_text(old, "OLDAUDITENTRYIDS", "-1")
            add_text(le, "LEDGERNAME", "CGST @ 9%")
            add_text(le, "GSTCLASS", "")
            add_text(le, "ISDEEMEDPOSITIVE", "Yes" if total_cgst < 0 else "No")
            add_text(le, "AMOUNT", fmt_amount(total_cgst))
            add_text(le, "VATEXPAMOUNT", fmt_amount(total_cgst))
            add_tax_lock_scaffolding(le)
            add_gst_rate_details(le)
        if total_sgst != 0:
            le = ET.SubElement(voucher, "LEDGERENTRIES.LIST")
            old = ET.SubElement(le, "OLDAUDITENTRYIDS.LIST", {"TYPE": "Number"})
            add_text(old, "OLDAUDITENTRYIDS", "-1")
            add_text(le, "LEDGERNAME", "SGST @ 9%")
            add_text(le, "GSTCLASS", "")
            add_text(le, "ISDEEMEDPOSITIVE", "Yes" if total_sgst < 0 else "No")
            add_text(le, "AMOUNT", fmt_amount(total_sgst))
            add_text(le, "VATEXPAMOUNT", fmt_amount(total_sgst))
            add_tax_lock_scaffolding(le)
            add_gst_rate_details(le)
        if total_utgst != 0:
            le = ET.SubElement(voucher, "LEDGERENTRIES.LIST")
            old = ET.SubElement(le, "OLDAUDITENTRYIDS.LIST", {"TYPE": "Number"})
            add_text(old, "OLDAUDITENTRYIDS", "-1")
            add_text(le, "LEDGERNAME", "UTGST @ 9%")
            add_text(le, "GSTCLASS", "")
            add_text(le, "ISDEEMEDPOSITIVE", "Yes" if total_utgst < 0 else "No")
            add_text(le, "AMOUNT", fmt_amount(total_utgst))
            add_text(le, "VATEXPAMOUNT", fmt_amount(total_utgst))
            add_tax_lock_scaffolding(le)
            add_gst_rate_details(le)

    # Inventory line
    inv = ET.SubElement(voucher, "ALLINVENTORYENTRIES.LIST")
    desc_list = ET.SubElement(inv, "BASICUSERDESCRIPTION.LIST", {"TYPE": "String"})
    add_text(desc_list, "BASICUSERDESCRIPTION", row.get("Item Description", "").strip())
    add_text(inv, "STOCKITEMNAME", row.get("Sku", "").strip())
    add_text(inv, "ISDEEMEDPOSITIVE", "Yes" if principal_basis < 0 else "No")
    add_text(inv, "ISLASTDEEMEDPOSITIVE", "Yes" if principal_basis < 0 else "No")
    add_text(inv, "RATE", f"{fmt_amount(principal_basis.copy_abs(), force_two=True)}/Nos")
    add_text(inv, "AMOUNT", fmt_amount(principal_basis, force_two=True))
    add_text(inv, "VATASSBLVALUE", fmt_amount(principal_basis, force_two=True))
    add_text(inv, "ACTUALQTY", f"{qty} Nos")
    add_text(inv, "BILLEDQTY", f"{qty} Nos")

    batch = ET.SubElement(inv, "BATCHALLOCATIONS.LIST")
    add_text(batch, "GODOWNNAME", f" {WAREHOUSE_NAME}")
    add_text(batch, "BATCHNAME", "Primary Batch")
    add_text(batch, "DESTINATIONGODOWNNAME", f" {WAREHOUSE_NAME}")
    add_text(batch, "AMOUNT", fmt_amount(principal_basis, force_two=True))
    add_text(batch, "ACTUALQTY", f"{qty} Nos")
    add_text(batch, "BILLEDQTY", f"{qty} Nos")

    add_inventory_scaffolding(inv)

    acc = ET.SubElement(inv, "ACCOUNTINGALLOCATIONS.LIST")
    old = ET.SubElement(acc, "OLDAUDITENTRYIDS.LIST", {"TYPE": "Number"})
    add_text(old, "OLDAUDITENTRYIDS", "-1")
    add_text(acc, "LEDGERNAME", "Sales GST Interstate @ 18%" if inter else "Sales GST Local @ 18%")
    add_text(acc, "GSTCLASS", "")
    add_text(acc, "ISDEEMEDPOSITIVE", "Yes" if principal_basis < 0 else "No")
    add_text(acc, "LEDGERFROMITEM", "No")
    add_text(acc, "REMOVEZEROENTRIES", "No")
    add_text(acc, "ISPARTYLEDGER", "No")
    add_text(acc, "ISLASTDEEMEDPOSITIVE", "Yes" if principal_basis < 0 else "No")
    add_text(acc, "AMOUNT", fmt_amount(principal_basis, force_two=True))
    add_gst_rate_details(acc)

    return voucher


def build_tcs_voucher(rows, debug_rows):
    totals = defaultdict(Decimal)
    per_order = defaultdict(Decimal)
    for r in rows:
        cg = d(r.get("Tcs Cgst Amount", 0))
        sg = d(r.get("Tcs Sgst Amount", 0))
        ug = d(r.get("Tcs Utgst Amount", 0))
        ig = d(r.get("Tcs Igst Amount", 0))
        totals["cgst"] += cg
        totals["sgst"] += sg
        totals["utgst"] += ug
        totals["igst"] += ig
        per_order[r.get("Order Id", "").strip()] += (cg + sg + ug + ig)

    if DEBUG:
        debug_rows.append({"tcs_totals": dict((k, str(v)) for k, v in totals.items())})

    if all(v == 0 for v in totals.values()):
        return None

    voucher = ET.Element("VOUCHER", {
        "REMOTEID": "",
        "VCHKEY": "",
        "VCHTYPE": "Journal",
        "ACTION": "Create",
        "OBJVIEW": "Accounting Voucher View",
    })
    dt_invoices = [parse_date(r.get("Invoice Date", "")) for r in rows if parse_date(r.get("Invoice Date", ""))]
    dt_min = min(dt_invoices) if dt_invoices else dt.datetime.today()
    dt_max = max(dt_invoices) if dt_invoices else dt.datetime.today()
    add_text(voucher, "DATE", tally_date(dt_max))
    add_text(voucher, "GUID", " ")
    add_text(voucher, "NARRATION", f"TCS Recorded from  {dt_min.strftime('%b  %d %Y  %I:%M%p')} to {dt_max.strftime('%b  %d %Y  %I:%M%p')}")
    add_text(voucher, "PARTYLEDGERNAME", "Amazon.in")
    add_text(voucher, "VOUCHERTYPENAME", "Amazon TCS")
    add_text(voucher, "VOUCHERNUMBER", dt_max.strftime("%b  %d %Y  %I:%M%p"))
    add_text(voucher, "EFFECTIVEDATE", tally_date(dt_max))

    def add_tcs_line(name, amount):
        le = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        old = ET.SubElement(le, "OLDAUDITENTRYIDS.LIST", {"TYPE": "Number"})
        add_text(old, "OLDAUDITENTRYIDS", "-1")
        add_text(le, "LEDGERNAME", name)
        add_text(le, "ISDEEMEDPOSITIVE", "Yes" if amount < 0 else "No")
        add_text(le, "LEDGERFROMITEM", "No")
        add_text(le, "REMOVEZEROENTRIES", "No")
        add_text(le, "ISPARTYLEDGER", "No")
        add_text(le, "ISLASTDEEMEDPOSITIVE", "Yes" if amount < 0 else "No")
        add_text(le, "AMOUNT", fmt_amount(amount))
        add_text(le, "VATEXPAMOUNT", fmt_amount(amount))

    add_tcs_line("Amazon - TCS - CGST", -totals["cgst"])
    add_tcs_line("Amazon - TCS - SGST", -totals["sgst"])
    add_tcs_line("Amazon - TCS - UTGST", -totals["utgst"])
    add_tcs_line("Amazon - TCS - IGST", -totals["igst"])

    total_net = totals["cgst"] + totals["sgst"] + totals["utgst"] + totals["igst"]
    if total_net != 0:
        le = ET.SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        old = ET.SubElement(le, "OLDAUDITENTRYIDS.LIST", {"TYPE": "Number"})
        add_text(old, "OLDAUDITENTRYIDS", "-1")
        add_text(le, "LEDGERNAME", "Amazon.in")
        add_text(le, "ISDEEMEDPOSITIVE", "No" if total_net > 0 else "Yes")
        add_text(le, "LEDGERFROMITEM", "No")
        add_text(le, "REMOVEZEROENTRIES", "No")
        add_text(le, "ISPARTYLEDGER", "Yes")
        add_text(le, "ISLASTDEEMEDPOSITIVE", "No" if total_net > 0 else "Yes")
        add_text(le, "AMOUNT", fmt_amount(total_net))
        add_text(le, "VATEXPAMOUNT", fmt_amount(total_net))
        for order, amt in per_order.items():
            if amt == 0:
                continue
            ba = ET.SubElement(le, "BILLALLOCATIONS.LIST")
            add_text(ba, "NAME", order)
            add_text(ba, "BILLTYPE", "New Ref")
            add_text(ba, "AMOUNT", fmt_amount(amt))

    return voucher


def convert(csv_path, xml_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    debug_rows = [] if DEBUG else None

    envelope = ET.Element("ENVELOPE")
    header = ET.SubElement(envelope, "HEADER")
    add_text(header, "TALLYREQUEST", "Import Data")
    body = ET.SubElement(envelope, "BODY")
    importdata = ET.SubElement(body, "IMPORTDATA")
    reqdesc = ET.SubElement(importdata, "REQUESTDESC")
    add_text(reqdesc, "REPORTNAME", "Vouchers")
    statvars = ET.SubElement(reqdesc, "STATICVARIABLES")
    add_text(statvars, "SVCURRENTCOMPANY", COMPANY_NAME)
    reqdata = ET.SubElement(importdata, "REQUESTDATA")

    for row in rows:
        voucher = build_voucher(row, debug_rows)
        msg = ET.SubElement(reqdata, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        msg.append(voucher)

    tcs_voucher = build_tcs_voucher(rows, debug_rows)
    if tcs_voucher is not None:
        msg = ET.SubElement(reqdata, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        msg.append(tcs_voucher)

    tree = ET.ElementTree(envelope)
    tree.write(xml_path, encoding="utf-8", xml_declaration=False)

    if DEBUG and debug_rows is not None:
        fieldnames = sorted({k for row in debug_rows for k in row.keys()})
        with open(LOG_PATH, "w", newline="", encoding="utf-8") as logf:
            writer = csv.DictWriter(logf, fieldnames=fieldnames)
            writer.writeheader()
            for row in debug_rows:
                writer.writerow(row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Amazon CSV to Tally XML")
    parser.add_argument("csv_path", help="Input CSV path")
    parser.add_argument("xml_path", help="Output XML path")
    args = parser.parse_args()
    convert(args.csv_path, args.xml_path)
