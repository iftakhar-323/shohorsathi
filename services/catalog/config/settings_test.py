from shohor_common.testing import jwt_keypair

from .settings import *  # noqa: F401,F403
from .settings import SIMPLE_JWT

_private, _public = jwt_keypair()
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": _private, "VERIFYING_KEY": _public}
