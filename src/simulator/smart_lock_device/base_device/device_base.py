import os
import time
import logging
import threading
from typing import Dict
from simulator.smart_lock_device.mqtt_wrapper.mqtt_device_wrapper import (
    MQTTDeviceWrapper,
)

logger = logging.getLogger("MQTTDeviceBase")


class DeviceBase:
    """
    Base class for all simulated MQTT devices.

    This class sets up MQTT connectivity, provides default `lock` and `unlock` command handlers,
    and allows subclasses to implement their own `status()` reporting logic.
    """

    def __init__(self, device_id: str):
        """
        Initializes the device with a given ID and sets up MQTT communication.

        Args:
            device_id (str): Unique identifier for this device. Used in MQTT topic paths.
        """
        # Set environment device id
        os.environ["DEVICE_ID"] = device_id
        self.device_id: str = device_id
        # Set state internals, minimum lock
        self.state: Dict[str, bool] = {"locked": True}
        self._state_lock = threading.Lock()
        # Create wrapper
        self.device: MQTTDeviceWrapper = MQTTDeviceWrapper.from_env()

    def setup(self) -> None:
        """
        Registers the default command handlers (`lock`, `unlock`) and status publisher with MQTT.

        Subclasses can override this method to register additional commands or customize behavior.
        """
        # Register minimum commands
        self.device.register_command("lock", self._lock)
        self.device.register_command("unlock", self._unlock)
        # Set publisher
        self.device.register_publisher(self.status)
        logger.info(f"[{self.device_id}] Default handlers registered.")

    def _lock(self) -> None:
        """
        Default handler for the 'lock' command.

        Sets internal state and logs the operation.
        """
        with self._state_lock:
            self.state["locked"] = True
        logger.debug(f"[{self.device_id}] Locked")

    def _unlock(self) -> None:
        """
        Default handler for the 'unlock' command.

        Sets internal state and logs the operation.
        """
        with self._state_lock:
            self.state["locked"] = False
        logger.debug(f"[{self.device_id}] Unlocked")

    @property
    def is_locked(self) -> bool:
        """
        Indicates whether the device is currently in the locked state.

        Returns:
            bool: True if the device is locked, False if it is unlocked.
        """
        return self.state["locked"]

    def status(self) -> Dict:
        """
        Publishes current device status.

        This method should be overridden in subclasses. The default implementation
        raises NotImplementedError to ensure each device defines its own telemetry.

        Returns:
            dict: Dictionary containing device status.

        Raises:
            NotImplementedError: If subclass does not override this method.
        """
        # Must be defined by derived classes
        raise NotImplementedError(
            f"[{self.device_id}] You must override `status()` in your device subclass."
        )

    def run(self) -> None:
        """
        Starts the device by registering commands and connecting to the MQTT broker.

        This method should be called from the device's `main()` or `__main__` block.
        """
        # Start device
        logger.info(f"[{self.device_id}] Starting device")
        self.setup()
        self.device.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info(f"[{self.device_id}] Shutting down...")
            self.device.stop()
