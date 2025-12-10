from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

# Get the custom User model
User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Custom authentication backend to allow users
    to log in using their email address
    instead of their username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Overrides the default authenticate
        method to use email instead of username.
        Parameters:
            - request: the current HttpRequest (can be None).
            - username: will actually be the email address in this context.
            - password: the password provided by the user.
            - **kwargs: any additional keyword arguments (not used here).

        Returns:
            - User instance if authentication is successful.
            - None if authentication fails.
        """
        try:
            # Try to find a user with the provided email (case-insensitive)
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            # If no user exists with that email,
            # return None (authentication failed)
            return None
        else:
            # Check if the password is correct and
            # the user is allowed to authenticate
            if (
                user.check_password(password)
                and self.user_can_authenticate(user)
            ):
                return user

        return None
