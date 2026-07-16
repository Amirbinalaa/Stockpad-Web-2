from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailOrUsernameBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in using either
    their username or email address.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        
        try:
            # Check if the "username" provided is actually an email or the username
            user = User.objects.get(Q(username__iexact=username) | Q(email__iexact=username))
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Fallback to the first one if somehow duplicates exist
            return User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()
        
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
