from simulator.smart_lock_device.base_device import DeviceBase


class SmartLock(DeviceBase):
    """
    Simulated Smart Lock device that extends the base MQTT device.
    """

    def __init__(self, lock_id: str, firm_ware_ver: str, init_battery: int):
        """
        Initializes the SmartLock device with a unique device ID.
        The base class handles MQTT setup and default command registration.
        """
        # Init base and set internals
        super().__init__(device_id=lock_id)
        self._battery = init_battery
        self._firmware_ver = firm_ware_ver

    def status(self):
        """
        Returns the current status of the smart lock.

        Returns:
            dict: A dictionary representing the device's current status.
        """
        return {
            "state": "locked" if self.state["locked"] else "unlocked",
            "battery_percent": self._battery,
            "firmware_version": self._firmware_ver,
        }
