"""CSV and Excel contact file parser for bulk WhatsApp messaging."""

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from logger import logger


@dataclass
class Contact:
    """Represents a single contact with a phone number and optional name."""

    phone: str
    name: str = ""

    def __post_init__(self) -> None:
        # Normalise: strip whitespace
        self.phone = self.phone.strip()
        self.name = self.name.strip()


class ContactParseError(Exception):
    """Raised when the contact file cannot be parsed or contains no valid contacts."""


def _normalise_phone(raw: str) -> str:
    """
    Ensure the phone number is in E.164 format (starts with '+').

    Args:
        raw: Raw phone number string from the file.

    Returns:
        Normalised phone number string.

    Raises:
        ValueError: If the number is empty or contains non-digit/plus characters.
    """
    number = raw.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not number:
        raise ValueError("Empty phone number")
    if not number.startswith("+"):
        number = "+" + number
    # Allow only digits and leading '+'
    if not number[1:].isdigit():
        raise ValueError(f"Invalid phone number: {raw!r}")
    return number


def parse_contacts_csv(data: str | bytes) -> list[Contact]:
    """
    Parse a CSV file containing contacts.

    Expected columns (case-insensitive): ``phone`` (required), ``name`` (optional).
    If no header row is detected the first column is assumed to be phone numbers.

    Args:
        data: Raw CSV content as string or bytes.

    Returns:
        List of valid Contact objects.

    Raises:
        ContactParseError: If no valid contacts could be parsed.
    """
    if isinstance(data, bytes):
        data = data.decode("utf-8-sig")  # handle BOM

    contacts: list[Contact] = []
    skipped = 0

    # Peek at the first row to decide whether a header exists
    sniffer_reader = csv.reader(io.StringIO(data))
    first_row = next(sniffer_reader, [])
    first_row_lower = [c.lower().strip() for c in first_row]
    has_header = "phone" in first_row_lower

    if has_header:
        reader = csv.DictReader(io.StringIO(data))
        fieldnames = [f.lower().strip() for f in (reader.fieldnames or [])]
        phone_col = reader.fieldnames[fieldnames.index("phone")]
        name_col = None
        if "name" in fieldnames:
            name_col = reader.fieldnames[fieldnames.index("name")]

        for row in reader:
            raw_phone = row.get(phone_col, "").strip()
            try:
                phone = _normalise_phone(raw_phone)
            except ValueError:
                logger.warning("Skipping invalid phone number: %r", raw_phone)
                skipped += 1
                continue
            name = row.get(name_col, "").strip() if name_col else ""
            contacts.append(Contact(phone=phone, name=name))
    else:
        # No header: treat every row as data; first column is phone, second is name
        all_rows = [first_row] + list(sniffer_reader)
        for row_values in all_rows:
            if not row_values:
                continue
            try:
                phone = _normalise_phone(row_values[0])
            except ValueError:
                logger.warning("Skipping invalid phone number: %r", row_values[0])
                skipped += 1
                continue
            name = row_values[1].strip() if len(row_values) > 1 else ""
            contacts.append(Contact(phone=phone, name=name))

    if skipped:
        logger.info("Skipped %d invalid rows during CSV parsing", skipped)

    if not contacts:
        raise ContactParseError("No valid contacts found in CSV file")

    logger.info("Parsed %d contacts from CSV", len(contacts))
    return contacts


def parse_contacts_excel(data: bytes) -> list[Contact]:
    """
    Parse an Excel (.xlsx) file containing contacts.

    Expected columns (case-insensitive): ``phone`` (required), ``name`` (optional).
    If the first row does not look like a header the first column is treated as phones.

    Args:
        data: Raw bytes of the Excel file.

    Returns:
        List of valid Contact objects.

    Raises:
        ContactParseError: If no valid contacts could be parsed.
        ImportError: If openpyxl is not installed.
    """
    try:
        import openpyxl  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "openpyxl is required to parse Excel files. "
            "Install it with: pip install openpyxl"
        ) from exc

    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))

    if not rows:
        raise ContactParseError("Excel file is empty")

    contacts: list[Contact] = []
    skipped = 0
    start_row = 0

    # Detect header row
    first_row = [str(c).lower().strip() if c is not None else "" for c in rows[0]]
    has_header = "phone" in first_row
    phone_idx = first_row.index("phone") if has_header else 0
    name_idx = first_row.index("name") if (has_header and "name" in first_row) else None
    start_row = 1 if has_header else 0

    for row in rows[start_row:]:
        if not row or row[phone_idx] is None:
            skipped += 1
            continue
        raw_phone = str(row[phone_idx])
        try:
            phone = _normalise_phone(raw_phone)
        except ValueError:
            logger.warning("Skipping invalid phone number: %r", raw_phone)
            skipped += 1
            continue
        name = ""
        if name_idx is not None and len(row) > name_idx and row[name_idx] is not None:
            name = str(row[name_idx]).strip()
        contacts.append(Contact(phone=phone, name=name))

    workbook.close()

    if skipped:
        logger.info("Skipped %d invalid rows during Excel parsing", skipped)

    if not contacts:
        raise ContactParseError("No valid contacts found in Excel file")

    logger.info("Parsed %d contacts from Excel", len(contacts))
    return contacts


def parse_contacts_file(filename: str, data: bytes) -> list[Contact]:
    """
    Dispatch to the correct parser based on file extension.

    Args:
        filename: Original filename (used to detect format).
        data: Raw file bytes.

    Returns:
        List of valid Contact objects.

    Raises:
        ContactParseError: If the format is unsupported or parsing fails.
    """
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return parse_contacts_csv(data)
    elif ext == ".xlsx":
        return parse_contacts_excel(data)
    else:
        raise ContactParseError(
            f"Unsupported file format: {ext!r}. Please upload a .csv or .xlsx file."
        )
