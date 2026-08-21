"""UK number plate format validation."""

import re

# Covers all common UK formats (spaces stripped before matching):
# Modern post-2001:   AB12CDE
# Prefix 1983-2001:   A123BCD
# Suffix 1963-1983:   ABC123D
# Northern Ireland:   ABC1234 / ABC123
_UK_PLATE = re.compile(
    r'^('
    r'[A-Z]{2}[0-9]{2}[A-Z]{3}'   # modern
    r'|[A-Z][0-9]{1,3}[A-Z]{3}'   # prefix
    r'|[A-Z]{3}[0-9]{1,3}[A-Z]'   # suffix
    r'|[A-Z]{2,3}[0-9]{1,4}'      # Northern Ireland
    r'|[0-9]{1,4}[A-Z]{2,3}'      # NI reversed
    r')$',
    re.IGNORECASE,
)


def validate_plate(registration_number: str) -> dict:
    """Return verified=True if the registration matches a known UK plate format."""
    reg = registration_number.replace(" ", "").upper()
    if not reg:
        return {"verified": False, "error": "Registration number is required"}
    if len(reg) > 8:
        return {"verified": False, "error": "Registration number too long"}
    if not _UK_PLATE.match(reg):
        return {"verified": False, "error": "Invalid UK registration number format"}
    return {"verified": True, "registration_number": reg}
