from apps.swipe_sessions.services.cleanup import delete_orphaned_sessions
from apps.users.exceptions import DeleteAccountError


def delete_account(user, password=None):
    if not user.is_guest:
        if not password:
            raise DeleteAccountError("Password is required to delete this account")
        if not user.check_password(password):
            raise DeleteAccountError("Incorrect password")

    session_ids = list(user.swipe_sessions.values_list("pk", flat=True))

    user.delete()

    if session_ids:
        delete_orphaned_sessions(session_ids=session_ids)
