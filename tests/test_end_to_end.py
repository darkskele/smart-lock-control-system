import time
import random
import logging
import os
from application.service_layer import MQTTService
from application.state_manager import LockManager

# Get log level from config
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level, format="[%(name)s] %(levelname)s: %(message)s")

def end_to_end_stress_test(total_operations: int = 1000):
    lock_ids = [f"lock-0{i}" for i in range(1, 5)]  # Assume 4 locks
    manager = LockManager(MQTTService.from_env(), lock_ids)
    manager.start()
    print("Starting correctness test...")
    time.sleep(3)

    # Pre-generate random lock-operation pairs
    ops = [(random.choice(lock_ids), random.choice(["lock", "unlock"]))
           for _ in range(total_operations)]

    # Count failures
    failures = 0
    success = 0
    recent_log = []

    try:
        for lock_id, action in ops:
            try:
                # Perform lock/unlock
                if action == "lock":
                    result = manager.lock(lock_id)
                    expected = "locked"
                else:
                    result = manager.unlock(lock_id)
                    expected = "unlocked"

                assert result, f"{lock_id} did not respond to {action}"
                assert result["state"] == expected, f"{lock_id} expected {expected}, got {result['state']}"

                # Log success
                success += 1
                recent_log.append(f"{lock_id}: {action} -> status OK")
            except AssertionError as e:
                failures += 1
                recent_log.append(f"FAIL: {lock_id}: {action} FAILED — {e}")
            except Exception as e:
                failures += 1
                recent_log.append(f"FAIL: {lock_id}: {action} EXCEPTION — {e}")

    finally:
        # Collate results
        manager.stop()
        print("Test complete")
        print(f"Total operations: {total_operations}")
        print(f"Success: {success}")
        print(f"Failures: {failures}")

        if failures:
            print("\nRecent failures:")
            for line in recent_log:
                if line.startswith("FAIL:"):
                    print(line)

        print("\nRecent activity:")
        for line in recent_log[-30:]:
            print(line)

if __name__ == "__main__":
    end_to_end_stress_test()