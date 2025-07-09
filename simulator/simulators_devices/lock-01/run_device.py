from simulator.base_device.device_base import DeviceBase
import logging

logging.basicConfig(level=logging.DEBUG, format="[%(name)s] %(levelname)s: %(message)s")

class SmartLock01(DeviceBase):
    """
    Simulated Smart Lock device that extends the base MQTT device.
    """

    def __init__(self):
        """
        Initializes the SmartLock device with a unique device ID.
        The base class handles MQTT setup and default command registration.
        """
        super().__init__(device_id="lock-01")

    def status(self):
        """
        Returns the current status of the smart lock.

        Returns:
            dict: A dictionary representing the device's current status.
        """
        return {
            "state": "locked" if self.state["locked"] else "unlocked",
            "battery_percent": 87,
            "firmware_version": "1.0.1"
        }


if __name__ == "__main__":
    """
    Entry point for running the SmartLock01 device.
    """
    try:
        SmartLock01().run()
    except Exception as ex:
        logging.getLogger("SmartLock01").exception(f"Unhandled exception in SmartLock01: {ex}")
