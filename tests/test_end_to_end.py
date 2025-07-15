import time
from application.state_manager import LockManager
from application.service_layer import MQTTService


def end_to_end_test():
    lock_ids = [f"lock-0{i}" for i in range(1, 5)]
    manager = LockManager(MQTTService.from_env(), lock_ids)
    manager.start()
    time.sleep(3)

    for lock_id in lock_ids:
        print(f"--- Testing {lock_id} ---")
        status = manager.query_status(lock_id)
        assert status and status["connected"], f"{lock_id} did not respond."
        assert status["state"] in {
            "locked",
            "unlocked",
        }, f"{lock_id} bad state: {status['state']}"

        assert manager.lock(lock_id)["state"] == "locked", f"{lock_id} failed to lock"
        assert (
            manager.unlock(lock_id)["state"] == "unlocked"
        ), f"{lock_id} failed to unlock"

    print("All locks passed end-to-end test.")
    manager.stop()


if __name__ == "__main__":
    end_to_end_test()
