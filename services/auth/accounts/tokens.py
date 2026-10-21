from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken


class ShohorRefreshToken(RefreshToken):
    """Adds the claims other services rely on. Access tokens derived from it inherit them."""

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token["role"] = user.role
        token["name"] = user.full_name
        token["phone"] = user.phone
        return token


class LoginSerializer(TokenObtainPairSerializer):
    token_class = ShohorRefreshToken


class RefreshSerializer(serializers.Serializer):
    """Issues a fresh pair from the current user row, so a role change (e.g. provider approval) shows up
    on the next refresh instead of only after the old refresh token expires."""

    refresh = serializers.CharField()

    def validate(self, attrs):
        from .models import User

        try:
            old = RefreshToken(attrs["refresh"])
        except TokenError as e:
            raise InvalidToken(e.args[0])
        user = User.objects.filter(pk=old["user_id"], is_active=True).first()
        if user is None:
            raise InvalidToken("User is inactive or deleted.")
        old.blacklist()
        return token_pair(user)


def token_pair(user):
    refresh = ShohorRefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}
