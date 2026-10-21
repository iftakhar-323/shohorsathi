from shohor_common.testing import overrides

from .settings import *  # noqa: F401,F403
from .settings import SIMPLE_JWT

globals().update(overrides(SIMPLE_JWT))
