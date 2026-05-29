"""UK DVLA driving licence number validator.

Format (16 chars, no spaces):
  Pos 1-5  : First 5 chars of surname, letters only, 9-padded
  Pos 6    : Tens digit of birth year's last 2 digits (e.g. 1985 → yy=85 → '8')
  Pos 7-8  : Month of birth (01-12 male; +50 for female → 51-62)
  Pos 9-10 : Day of birth
  Pos 11-12: Last 2 digits of birth year
  Pos 13-14: First two initials (9-padded)
  Pos 15   : Arbitrary digit
  Pos 16-17: Two check letters (computer-generated, not validated here)

Example: MORRI 9 07 05 57 SM 9 IJ → MORRI907055 7SM9IJ (spaces for readability only)
"""

import re
from datetime import date


def _encode_surname(last_name: str) -> str:
    letters = re.sub(r"[^A-Z]", "", last_name.upper())
    return (letters + "99999")[:5]


def _extract_dob(num: str) -> tuple[int, int, int] | None:
    """Returns (year, month, day) or None."""
    try:
        month_raw = int(num[6:8])
        month = month_raw - 50 if month_raw > 50 else month_raw
        if not (1 <= month <= 12):
            return None
        day = int(num[8:10])
        if not (1 <= day <= 31):
            return None
        yy = int(num[10:12])
        current_2digit = date.today().year % 100
        century = 1900 if yy > current_2digit else 2000
        year = century + yy
        return year, month, day
    except (ValueError, IndexError):
        return None


def validate_format(licence_number: str) -> bool:
    """Check the basic 16-char alphanumeric pattern."""
    num = re.sub(r"\s", "", licence_number.upper())
    return bool(re.match(r"^[A-Z9]{5}\d{6}[A-Z]{2}\d[A-Z]{2}$", num))


def validate_uk_licence(
    licence_number: str,
    last_name: str | None = None,
    date_of_birth: date | None = None,
) -> tuple[bool, str]:
    """
    Returns (is_valid, message).

    Validates:
    1. 16-char DVLA format
    2. Surname encoding matches last_name (if provided)
    3. Encoded DOB matches date_of_birth (if provided)
    """
    num = re.sub(r"\s", "", licence_number.upper())

    if not validate_format(num):
        return False, "Invalid UK driving licence format — must be 16 characters (e.g. MORRI9070557SM9IJ)"

    if last_name is not None:
        expected = _encode_surname(last_name)
        if num[:5] != expected:
            return False, "Surname does not match the licence number"

    if date_of_birth is not None:
        dob = _extract_dob(num)
        if dob is None:
            return False, "Could not read date of birth from licence number"
        y, m, d = dob
        if (date_of_birth.year, date_of_birth.month, date_of_birth.day) != (y, m, d):
            return False, "Date of birth does not match the licence number"

    return True, "OK"
