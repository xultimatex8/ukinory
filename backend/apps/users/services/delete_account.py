from apps.users.exceptions import DeleteAccountError


def delete_account(user, password=None):
    if not user.is_guest:
        if not password:
            raise DeleteAccountError("Password is required to delete this account")
        if not user.check_password(password):
            raise DeleteAccountError("Incorrect password")

    user.delete()
