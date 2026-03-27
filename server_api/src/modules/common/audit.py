def audit_log_placeholder(actor: str, action: str) -> dict:
    return {
        "actor": actor,
        "action": action,
        "message": "Audit logging skeleton. Connect DB writer later.",
    }
