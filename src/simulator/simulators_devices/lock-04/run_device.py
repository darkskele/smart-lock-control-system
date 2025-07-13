import os
import logging
from simulator.smart_lock_device import SmartLock

logging.basicConfig(level=logging.DEBUG, format="[%(name)s] %(levelname)s: %(message)s")


if __name__ == "__main__":
    """
    Entry point for running the SmartLock04 device.
    """
    try:
        device_id = os.getenv("DEVICE_ID", "lock-04")
        SmartLock(firm_ware_ver="9.4.2", init_battery=99, lock_id=device_id).run()
    except Exception as ex:
        logging.getLogger("SmartLock04").exception(
            f"Unhandled exception in SmartLock04: {ex}"
        )
