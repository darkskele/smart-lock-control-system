import os
import logging
from simulator.smart_lock_device import SmartLock

logging.basicConfig(level=logging.DEBUG, format="[%(name)s] %(levelname)s: %(message)s")


if __name__ == "__main__":
    """
    Entry point for running the SmartLock device.
    """
    try:
        device_id = os.getenv("DEVICE_ID", "lock-01")
        SmartLock(firm_ware_ver="1.0.3", init_battery=89, lock_id=device_id).run()
    except Exception as ex:
        logging.getLogger("SmartLock01").exception(
            f"Unhandled exception in SmartLock01: {ex}"
        )
