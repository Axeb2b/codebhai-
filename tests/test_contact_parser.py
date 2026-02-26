"""Unit tests for the contact parser (contact_parser.py)."""

import io
from typing import Any
import pytest
import openpyxl

from contact_parser import (
    Contact,
    ContactParseError,
    parse_contacts_csv,
    parse_contacts_excel,
    parse_contacts_file,
    _normalise_phone,
)


# ---------------------------------------------------------------------------
# _normalise_phone
# ---------------------------------------------------------------------------

def test_normalise_phone_with_plus():
    assert _normalise_phone("+14155552671") == "+14155552671"


def test_normalise_phone_without_plus():
    assert _normalise_phone("14155552671") == "+14155552671"


def test_normalise_phone_strips_spaces_dashes():
    assert _normalise_phone("+1 415-555-2671") == "+14155552671"


def test_normalise_phone_empty_raises():
    with pytest.raises(ValueError):
        _normalise_phone("")


def test_normalise_phone_invalid_raises():
    with pytest.raises(ValueError):
        _normalise_phone("not-a-number")


# ---------------------------------------------------------------------------
# parse_contacts_csv
# ---------------------------------------------------------------------------

def test_csv_with_header():
    csv_data = "phone,name\n+14155552671,Alice\n+442071234567,Bob\n"
    contacts = parse_contacts_csv(csv_data)
    assert len(contacts) == 2
    assert contacts[0].phone == "+14155552671"
    assert contacts[0].name == "Alice"
    assert contacts[1].phone == "+442071234567"
    assert contacts[1].name == "Bob"


def test_csv_phone_only_header():
    csv_data = "phone\n+14155552671\n+442071234567\n"
    contacts = parse_contacts_csv(csv_data)
    assert len(contacts) == 2
    assert contacts[0].name == ""


def test_csv_no_header_first_col_is_phone():
    csv_data = "+14155552671,Alice\n+442071234567,Bob\n"
    contacts = parse_contacts_csv(csv_data)
    assert len(contacts) == 2
    assert contacts[0].phone == "+14155552671"


def test_csv_skips_invalid_phones():
    csv_data = "phone,name\nnot-a-phone,Alice\n+14155552671,Bob\n"
    contacts = parse_contacts_csv(csv_data)
    assert len(contacts) == 1
    assert contacts[0].phone == "+14155552671"


def test_csv_empty_raises():
    with pytest.raises(ContactParseError):
        parse_contacts_csv("phone,name\n")


def test_csv_bytes_input():
    csv_bytes = b"phone,name\n+14155552671,Alice\n"
    contacts = parse_contacts_csv(csv_bytes)
    assert len(contacts) == 1


def test_csv_bom_handling():
    # UTF-8 BOM prefix
    csv_bytes = "\ufeffphone,name\n+14155552671,Alice\n".encode("utf-8-sig")
    contacts = parse_contacts_csv(csv_bytes)
    assert len(contacts) == 1


def test_csv_no_plus_normalised():
    csv_data = "phone\n14155552671\n"
    contacts = parse_contacts_csv(csv_data)
    assert contacts[0].phone == "+14155552671"


# ---------------------------------------------------------------------------
# parse_contacts_excel
# ---------------------------------------------------------------------------

def _make_excel(rows: list[tuple[Any, ...]]) -> bytes:
    """Create an in-memory Excel workbook and return its bytes."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_excel_with_header():
    data = _make_excel([("phone", "name"), ("+14155552671", "Alice"), ("+442071234567", "Bob")])
    contacts = parse_contacts_excel(data)
    assert len(contacts) == 2
    assert contacts[0].phone == "+14155552671"
    assert contacts[0].name == "Alice"


def test_excel_phone_only_header():
    data = _make_excel([("phone",), ("+14155552671",)])
    contacts = parse_contacts_excel(data)
    assert len(contacts) == 1
    assert contacts[0].name == ""


def test_excel_no_header():
    data = _make_excel([("+14155552671", "Alice")])
    contacts = parse_contacts_excel(data)
    assert len(contacts) == 1
    assert contacts[0].phone == "+14155552671"


def test_excel_skips_invalid():
    data = _make_excel([("phone",), ("not-a-phone",), ("+14155552671",)])
    contacts = parse_contacts_excel(data)
    assert len(contacts) == 1


def test_excel_empty_raises():
    wb = openpyxl.Workbook()
    ws = wb.active
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ContactParseError):
        parse_contacts_excel(buf.getvalue())


# ---------------------------------------------------------------------------
# parse_contacts_file dispatch
# ---------------------------------------------------------------------------

def test_dispatch_csv():
    csv_bytes = b"phone\n+14155552671\n"
    contacts = parse_contacts_file("contacts.csv", csv_bytes)
    assert len(contacts) == 1


def test_dispatch_xlsx():
    data = _make_excel([("phone",), ("+14155552671",)])
    contacts = parse_contacts_file("contacts.xlsx", data)
    assert len(contacts) == 1


def test_dispatch_unsupported_format():
    with pytest.raises(ContactParseError, match="Unsupported file format"):
        parse_contacts_file("contacts.txt", b"some data")
