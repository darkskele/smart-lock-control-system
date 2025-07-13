import os
import logging
from simulator.smart_lock_device import SmartLock

logging.basicConfig(level=logging.DEBUG, format="[%(name)s] %(levelname)s: %(message)s")

if __name__ == "__main__":
    """
    Entry point for running the SmartLock02 device.
    """
    try:
        device_id = os.getenv("DEVICE_ID", "lock-02")
        SmartLock(firm_ware_ver="3.20.4", init_battery=34, lock_id=device_id).run()
    except Exception as ex:
        logging.getLogger("SmartLock02").exception(
            f"Unhandled exception in SmartLock02: {ex}"
        )
