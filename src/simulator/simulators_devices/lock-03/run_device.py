import os
import logging
from simulator.smart_lock_device import SmartLock

logging.basicConfig(level=logging.DEBUG, format="[%(name)s] %(levelname)s: %(message)s")


if __name__ == "__main__":
    """
    Entry point for running the SmartLock03 device.
    """
    try:
        device_id = os.getenv("DEVICE_ID", "lock-03")
        SmartLock(firm_ware_ver="1.4.6", init_battery=13, lock_id=device_id).run()
    except Exception as ex:
        logging.getLogger("SmartLock03").exception(
            f"Unhandled exception in SmartLock03: {ex}"
        )
