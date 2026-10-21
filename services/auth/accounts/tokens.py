from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken


class ShohorRefreshToken(RefreshToken):
    """Adds the claims other services rely on. Access tokens derived from it inherit them."""

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token["role"] = user.role
        token["name"] = user.full_name
        return token


class LoginSerializer(TokenObtainPairSerializer):
    token_class = ShohorRefreshToken


def token_pair(user):
    refresh = ShohorRefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}
