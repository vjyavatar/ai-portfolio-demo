"""
r63.71 — 13F-HR information table XML parser.

The information table is structured XML with one <infoTable> element per
holding. Schema reference:
https://www.sec.gov/info/edgar/specifications/form13fxmltechspec.pdf

Critical detail: 13F filings report VALUE in thousands of dollars.
A holding with <value>100000</value> means $100,000,000 (not $100,000).
We multiply by 1000 on parse and store raw USD.
"""

from dataclasses import dataclass
from typing import List, Optional

from lxml import etree


# 13F XML uses the namespace prefix from the schema spec
_NS = {
    "ns1": "http://www.sec.gov/edgar/document/thirteenf/informationtable",
    "info": "http://www.sec.gov/edgar/document/thirteenf/informationtable",
}


@dataclass
class ParsedHolding:
    """One row from a 13F information table, normalized."""
    cusip: str
    issuer_name: str
    title_of_class: str
    value_usd: int           # filing value × 1000 (filings report in thousands)
    shares: Optional[int]
    put_call: Optional[str]  # "PUT" / "CALL" / None
    investment_discretion: Optional[str]  # "SOLE" / "DFND" / "OTR"


def _txt(elem, tag: str) -> str:
    """Find first matching tag (any namespace) and return stripped text or ''."""
    if elem is None:
        return ""
    # Try namespaced lookups, then bare
    for ns_prefix in ("ns1", "info"):
        found = elem.find(f"{{{_NS[ns_prefix]}}}{tag}")
        if found is not None and found.text:
            return found.text.strip()
    # Bare lookup (some filings ship without namespace)
    found = elem.find(tag)
    if found is not None and found.text:
        return found.text.strip()
    # Local-name-based fallback (handles unexpected namespaces)
    for child in elem.iter():
        if etree.QName(child.tag).localname == tag and child.text:
            return child.text.strip()
    return ""


def parse_information_table(xml_bytes: bytes) -> List[ParsedHolding]:
    """
    Parse a 13F information table XML into a list of ParsedHolding rows.
    Tolerant of namespace variation, missing optional fields, and
    minor schema drift across filer software.
    """
    if not xml_bytes:
        return []

    try:
        # recover=True tolerates mildly malformed XML (some filers ship dirty XML)
        parser = etree.XMLParser(recover=True, huge_tree=True)
        root = etree.fromstring(xml_bytes, parser=parser)
    except Exception:
        return []

    holdings: List[ParsedHolding] = []

    # Find all infoTable elements (any namespace)
    info_tables = []
    for elem in root.iter():
        if etree.QName(elem.tag).localname == "infoTable":
            info_tables.append(elem)

    for it in info_tables:
        try:
            cusip = _txt(it, "cusip").upper().replace(" ", "")
            if not cusip or len(cusip) > 9:
                continue  # malformed CUSIP — skip rather than corrupt the row

            issuer = _txt(it, "nameOfIssuer")
            tclass = _txt(it, "titleOfClass")

            # Value in thousands per spec — multiply
            val_str = _txt(it, "value")
            if not val_str:
                continue
            try:
                value_usd = int(float(val_str.replace(",", "")) * 1000)
            except ValueError:
                continue
            if value_usd <= 0:
                continue

            # Shares: nested under <shrsOrPrnAmt><sshPrnamt>
            shares_str = ""
            for child in it.iter():
                if etree.QName(child.tag).localname == "sshPrnamt" and child.text:
                    shares_str = child.text.strip()
                    break
            shares = None
            if shares_str:
                try:
                    shares = int(float(shares_str.replace(",", "")))
                except ValueError:
                    shares = None

            put_call = _txt(it, "putCall").upper() or None
            inv_disc = _txt(it, "investmentDiscretion").upper() or None

            holdings.append(ParsedHolding(
                cusip=cusip,
                issuer_name=issuer[:255],  # safety cap
                title_of_class=tclass[:255],
                value_usd=value_usd,
                shares=shares,
                put_call=put_call,
                investment_discretion=inv_disc,
            ))
        except Exception:
            # Skip malformed rows rather than failing the whole filing
            continue

    return holdings


def total_value_and_count(holdings: List[ParsedHolding]) -> tuple:
    """Aggregate stats for filings table denormalization."""
    total = sum(h.value_usd for h in holdings)
    return total, len(holdings)
