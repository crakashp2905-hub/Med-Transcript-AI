"""Storage lifecycle decisions for live recording prefixes."""


def decide(*, expired, recovery_authorized, retained_copy, user_discarded):
    if user_discarded:
        return {"action": "delete", "recoverable": False, "reason": "user_discard"}
    if expired and not recovery_authorized:
        return {"action": "expire", "recoverable": False, "reason": "safe_expiry"}
    if recovery_authorized and retained_copy:
        return {
            "action": "retain",
            "recoverable": True,
            "reason": "authorized_recovery",
        }
    return {
        "action": "retain",
        "recoverable": bool(retained_copy),
        "reason": "active_or_unresolved",
    }
