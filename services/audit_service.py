from flask import request
from database import query_db, execute_db


def log_action(user_id, action, entity_type, entity_id=None, details=None, ip_address=None, conn=None):
    """
    Record an administrative or critical user action in audit_logs.
    Captures user, action, entity, details, IP address, and timestamp.
    """
    if ip_address is None:
        try:
            ip_address = request.remote_addr if request else "127.0.0.1"
        except RuntimeError:
            ip_address = "127.0.0.1"

    query = """
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    return execute_db(
        query,
        (user_id, action, entity_type, str(entity_id) if entity_id is not None else None, details, ip_address),
        commit=True if conn is None else False,
        conn=conn,
    )


def get_recent_logs(limit=100):
    """Retrieve recent audit logs with user information."""
    query = """
        SELECT a.id, a.user_id, u.name AS user_name, u.email AS user_email, u.role AS user_role,
               a.action, a.entity_type, a.entity_id, a.details, a.ip_address, a.created_at
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC, a.id DESC
        LIMIT ?
    """
    return query_db(query, (limit,))
