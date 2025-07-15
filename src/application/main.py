import os
import time
import logging
from typing import Optional
from application.service_layer import MQTTService
from application.state_manager import LockManager

# Get log level from config
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level, format="[%(name)s] %(levelname)s: %(message)s")


def build_lock_manager() -> LockManager:
    # Use environment variables or defaults
    mqtt_service = MQTTService.from_env()
    lock_ids = [f"lock-0{i}" for i in range(1, 5)]  # lock-01 to lock-04
    manager = LockManager(mqtt_service, lock_ids)
    manager.start()
    time.sleep(5)  # allow subscriptions and polling to kick in
    return manager


def interactive_loop(initial_manager: Optional[LockManager]) -> None:
    print(
        "Smart Lock CLI — type 'help' for commands, 'exit' to stop manager, 'start' to restart, 'quit' to exit."
    )
    manager: Optional[LockManager] = initial_manager

    # Loop until broken
    while True:
        try:
            # Take user input
            cmd = input("> ").strip()
            if not cmd:
                continue

            # Stop manager and exit CLI
            if cmd == "quit":
                print("Quitting CLI.")
                if manager:
                    manager.stop()
                break

            # Print options
            if cmd == "help":
                print("Commands:")
                print("  lock <id>     — Lock device lock-0X")
                print("  unlock <id>   — Unlock device lock-0X")
                print("  query <id>    — Query device status lock-0X")
                print("  status        — Show status of all locks")
                print("  metrics       — Show MQTT connection metrics")
                print("  exit          — Stop the manager (but keep CLI open)")
                print("  start         — Start/restart the manager if stopped")
                print("  quit          — Exit CLI entirely")
                continue

            # Close manager
            if cmd == "exit":
                if manager:
                    # Stop the manager
                    manager.stop()
                    manager = None
                    print(
                        "LockManager stopped. Type 'start' to restart or 'quit' to exit."
                    )
                else:
                    # Don't double close
                    print("LockManager already stopped.")
                continue

            # Start manager
            if cmd == "start":
                if manager:
                    print("LockManager is already running.")
                else:
                    manager = build_lock_manager()
                    print("LockManager started.")
                continue

            if manager is None:
                print("LockManager is stopped. Use 'start' to restart it.")
                continue

            # Command for locks
            parts = cmd.split()
            command = parts[0]

            if command in {"lock", "unlock", "query"}:
                # Requires lock id
                if len(parts) != 2 or not parts[1].isdigit():
                    print("Usage: lock|unlock|query <id>")
                    continue
                lock_id = f"lock-0{int(parts[1])}"
                # Thread safe check for available locks
                if lock_id not in manager.status:
                    print(f"No such lock: {lock_id}")
                    continue
                # Commands for locks
                if command == "lock":
                    result = manager.lock(lock_id)
                elif command == "unlock":
                    result = manager.unlock(lock_id)
                else:
                    result = manager.query_status(lock_id)
                print(f"{lock_id}: {result}")

            # Check current status (not asked for, last updated status)
            elif command == "status":
                for lid, state in manager.status.items():
                    print(f"{lid}: {state}")

            # Get service layer metrics
            elif command == "metrics":
                print(manager.get_mqtt_metrics())

            else:
                print(f"Unknown command: {command}")

        # Keyboard interrupt to exit CLI
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received. Shutting down.")
            if manager:
                manager.stop()
            break

        except Exception as e:
            print(f"Error: {e}")


def main():
    # Build manager
    manager = build_lock_manager()
    try:
        # Loop CLI
        interactive_loop(manager)
    finally:
        manager.stop()


if __name__ == "__main__":
    main()
