from database import query_db, execute_db


def send_notification(user_id, title, message, notif_type="info", link=None, conn=None):
    """
    Dispatch an in-app notification to a user.
    Types: 'info', 'warning', 'success', 'danger'.
    """
    query = """
        INSERT INTO notifications (user_id, title, message, type, link)
        VALUES (?, ?, ?, ?, ?)
    """
    return execute_db(
        query,
        (user_id, title, message, notif_type, link),
        commit=True if conn is None else False,
        conn=conn,
    )


def get_user_notifications(user_id, unread_only=False, limit=20):
    """Retrieve notifications for a user, ordered newest first."""
    if unread_only:
        query = """
            SELECT * FROM notifications
            WHERE user_id = ? AND is_read = 0
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """
    else:
        query = """
            SELECT * FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """
    return query_db(query, (user_id, limit))


def get_unread_count(user_id):
    """Get count of unread notifications for a user."""
    row = query_db(
        "SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,),
        one=True,
    )
    return row["cnt"] if row else 0


def mark_as_read(notification_id, user_id):
    """Mark a specific notification as read."""
    query = "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?"
    return execute_db(query, (notification_id, user_id))


def mark_all_read(user_id):
    """Mark all notifications as read for a given user."""
    query = "UPDATE notifications SET is_read = 1 WHERE user_id = ?"
    return execute_db(query, (user_id,))
