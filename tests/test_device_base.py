import unittest
from unittest.mock import patch, MagicMock
from simulator.smart_lock_device.base_device import DeviceBase


# Dummy subclass used to test DeviceBase behavior without triggering NotImplementedError
class DummyDevice(DeviceBase):
    def status(self):
        # Minimal status implementation for testing
        return {"locked": self.is_locked}


class TestDeviceBase(unittest.TestCase):

    @patch(
        "simulator.smart_lock_device.base_device.device_base.MQTTDeviceWrapper.from_env"
    )
    def setUp(self, mock_from_env):
        """
        Sets up the test environment by patching the MQTTDeviceWrapper dependency
        and creating a testable DummyDevice instance.
        """
        self.mock_wrapper = MagicMock()
        mock_from_env.return_value = self.mock_wrapper
        self.device = DummyDevice("test-device")

    def test_initial_state(self):
        """
        Verify that the device initializes with the correct ID and locked state.
        """
        self.assertEqual(self.device.device_id, "test-device")
        self.assertTrue(self.device.is_locked)
        self.assertEqual(self.device.state, {"locked": True})

    def test_lock_unlock(self):
        """
        Test that _lock() and _unlock() correctly modify the internal locked state.
        """
        self.device._unlock()
        self.assertFalse(self.device.is_locked)

        self.device._lock()
        self.assertTrue(self.device.is_locked)

    def test_status_returns_dict(self):
        """
        Test that the dummy `status()` implementation returns the correct structure.
        """
        self.device._unlock()
        status = self.device.status()
        self.assertEqual(status, {"locked": False})

    def test_setup_registers_handlers(self):
        """
        Verify that `setup()` registers lock/unlock command handlers and a status publisher.
        """
        self.device.setup()

        self.mock_wrapper.register_command.assert_any_call("lock", self.device._lock)
        self.mock_wrapper.register_command.assert_any_call(
            "unlock", self.device._unlock
        )
        self.mock_wrapper.register_publisher.assert_called_once_with(self.device.status)

    @patch(
        "simulator.smart_lock_device.base_device.device_base.MQTTDeviceWrapper.from_env"
    )
    def test_base_status_raises(self, mock_from_env):
        """
        Confirm that the base `DeviceBase.status()` method raises NotImplementedError
        when not overridden by a subclass.
        """
        mock_wrapper = MagicMock()
        mock_from_env.return_value = mock_wrapper

        base = DeviceBase("base-device")
        with self.assertRaises(NotImplementedError):
            base.status()


if __name__ == "__main__":
    unittest.main()
