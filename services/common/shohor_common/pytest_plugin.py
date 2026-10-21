"""Loaded by every service's conftest.py: resets captured events between tests."""
import pytest

from shohor_common import events


@pytest.fixture(autouse=True)
def captured_events():
    events.sent.clear()
    yield events.sent
    events.sent.clear()
