"""DVLA Vehicle Enquiry Service (VES) integration.

Docs: https://developer-portal.driver-vehicle-licensing.api.gov.uk/apis/vehicle-enquiry-service
Key stays server-side — never sent to any client.
"""

import logging
import urllib.error
import urllib.request
import json

logger = logging.getLogger(__name__)

_VES_URL = "https://driver-vehicle-licensing.api.gov.uk/vehicle-enquiry/v1/vehicles"


class DVLALookupError(Exception):
    """DVLA API is unreachable or returned an unexpected error."""


class DVLANotFoundError(Exception):
    """Registration number not found in DVLA records."""


def lookup_vehicle(registration_number: str, api_key: str) -> dict:
    """Call the DVLA VES API and return the raw vehicle record.

    Returns a dict with at minimum: make, colour, yearOfManufacture, motStatus, taxStatus.
    Raises DVLANotFoundError for 404, DVLALookupError for all other failures.
    """
    reg = registration_number.replace(" ", "").upper()
    payload = json.dumps({"registrationNumber": reg}).encode()
    req = urllib.request.Request(
        _VES_URL,
        data=payload,
        method="POST",
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise DVLANotFoundError(f"Registration {reg} not found") from exc
        body = ""
        try:
            body = exc.read().decode()
        except Exception:
            pass
        logger.error("DVLA VES error %s: %s", exc.code, body)
        raise DVLALookupError(f"DVLA API returned {exc.code}") from exc
    except Exception as exc:
        logger.error("DVLA VES unreachable: %s", exc)
        raise DVLALookupError("DVLA API unreachable") from exc


def verify_plate(
    registration_number: str,
    api_key: str,
    saved_make: str | None = None,
    saved_colour: str | None = None,
) -> dict:
    """Full verification flow. Returns a structured result dict.

    Keys: verified, make, colour, year_of_manufacture, mot_status, tax_status,
          mismatch_warnings, error (only on failure).
    """
    reg = registration_number.replace(" ", "").upper()
    try:
        data = lookup_vehicle(reg, api_key)
    except DVLANotFoundError:
        return {"verified": False, "error": "Registration not found"}
    except DVLALookupError:
        return {"verified": False, "error": "Vehicle lookup temporarily unavailable"}

    dvla_make = (data.get("make") or "").upper()
    dvla_colour = (data.get("colour") or "").upper()

    mismatch_warnings: list[str] = []
    if saved_make and dvla_make and saved_make.upper() != dvla_make:
        mismatch_warnings.append("make_mismatch")
    if saved_colour and dvla_colour and saved_colour.upper() != dvla_colour:
        mismatch_warnings.append("colour_mismatch")

    return {
        "verified": True,
        "make": dvla_make or None,
        "colour": dvla_colour or None,
        "year_of_manufacture": data.get("yearOfManufacture"),
        "mot_status": data.get("motStatus"),
        "tax_status": data.get("taxStatus"),
        "mismatch_warnings": mismatch_warnings,
    }
