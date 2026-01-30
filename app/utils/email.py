"""Email URL builders."""

def build_verify_url(frontend_base_url: str, token: str) -> str:
    return f"{frontend_base_url}/verify-email?token={token}"


def build_reset_url(frontend_base_url: str, token: str) -> str:
    return f"{frontend_base_url}/reset-password?token={token}"
