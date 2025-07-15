import pytest
import time
from unittest.mock import MagicMock, patch
from application.state_manager.lock_state_manager import LockManager


@pytest.fixture
def mock_mqtt():
    # Mock for MQTT layer
    service = MagicMock()
    service.publish = MagicMock()
    service.subscribe = MagicMock()
    service.get_message = MagicMock()
    service.connected = True
    service.last_reconnect_attempt_time = 123.0
    service.reconnect_attempts = 0
    service.last_message_received_time = 456.0
    return service


def test_register_lock_subscribes_and_sets_state(mock_mqtt):
    # Initialise lock manager with one lock
    manager = LockManager(mock_mqtt, lock_ids=["lock1"])
    # Set state
    state = manager.get_status("lock1")
    # Returns default
    assert state["state"] == "unknown"
    # Check call right
    mock_mqtt.subscribe.assert_called_with("devices/lock1/status", qos=1)


def test_register_callback_adds_function(mock_mqtt):
    manager = LockManager(mock_mqtt, lock_ids=["lock1"])
    cb = MagicMock()
    # Set callback
    manager.register_callback("lock1", cb)
    assert cb in manager._callbacks["lock1"]


def test_handle_status_updates_state_and_triggers_callback(mock_mqtt):
    manager = LockManager(mock_mqtt, lock_ids=["lock1"])
    cb = MagicMock()
    manager.register_callback("lock1", cb)

    # Dummy payload
    payload = {"state": "locked", "battery_percent": 95, "firmware_version": "v1"}
    with patch("time.time", return_value=999.0):
        manager._handle_status("lock1", payload)

    # Get state back
    state = manager.get_status("lock1")
    assert state["state"] == "locked"
    assert state["battery_percent"] == 95
    assert state["last_updated"] == 999.0
    time.sleep(0.1)  # allow thread to fire
    # Check call back was called
    cb.assert_called_once()


def test_check_stale_marks_disconnected(mock_mqtt):
    manager = LockManager(mock_mqtt, lock_ids=["lock1"])
    with patch("time.time", side_effect=[1000.0, 980.0]):  # now, last_updated
        manager._device_states["lock1"]["last_updated"] = 980.0
        manager._device_states["lock1"]["connected"] = True
        manager._check_stale_devices(max_age=10.0)

    # Check state is disconnected
    assert not manager._device_states["lock1"]["connected"]
    assert manager._device_states["lock1"]["error"] == "stale"


def test_publish_and_wait_triggers_timeout(mock_mqtt):
    manager = LockManager(mock_mqtt, lock_ids=["lock1"])
    cond = manager._locks["lock1"]

    def timeout_wait(*args, **kwargs):
        return False

    cond.wait = timeout_wait

    # publish to topic
    with patch.object(cond, "wait", return_value=False):
        result = manager._publish_and_wait(
            "lock1", "some/topic", {"action": "x"}, timeout=0.1
        )

    assert result["connected"] is False
    assert result["error"] == "timeout"
