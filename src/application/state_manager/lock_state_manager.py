import threading
import time
import logging
from typing import Callable, Dict, Optional, List, Any
from application.service_layer import MQTTService

logger = logging.getLogger("LockManager")


class LockManager:
    """Manages the state, communication, and command lifecycle of multiple smart locks over MQTT.

    Responsibilities:
    - Subscribes to device status topics on initialization
    - Maintains the latest known status per lock
    - Sends lock/unlock/query commands and waits for responses
    - Notifies with callbacks on state change
    - Periodically polls lock status
    - Handles error and timeout conditions
    """

    def __init__(
        self, mqtt_service: MQTTService, lock_ids: List[str], poll_interval: float = 2.0
    ):
        """Initializes the LockManager and subscribes to all lock status topics.

        Args:
            mqtt_service: An instance of MQTTService layer to use for broker communication.
            lock_ids: A list of lock device IDs to manage.
            poll_interval: Polling frequency in seconds.
        """
        # MQTT service and lock stuff
        self._mqtt_service = mqtt_service
        self._lock_ids = lock_ids
        self._poll_interval = poll_interval

        # Device state and callbacks
        self._device_states: Dict[str, Dict[str, Any]] = {}
        self._callbacks: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self._callbacks_lock = threading.Lock()
        self._locks: Dict[str, threading.Condition] = {}
        self._state_lock = threading.Lock()

        # Thread control
        self._running = False
        self._main_thread = threading.Thread(target=self._process_messages, daemon=True)
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)

        # Subscribe to each lock's status topic and initialize internal state
        for lock_id in lock_ids:
            self._register_lock(lock_id)

    def _register_lock(self, lock_id: str) -> None:
        """Subscribes to the MQTT status topic for a lock and sets default state.

        Args:
            lock_id: The ID of the lock to register.
        """
        # Subscribe
        topic = f"devices/{lock_id}/status"
        self._mqtt_service.subscribe(topic, qos=1)
        logger.info(f"Subscribed to lock: {topic}")

        # Update lock state safely
        with self._state_lock:
            self._device_states[lock_id] = {
                "state": "unknown",
                "battery_percent": None,
                "firmware_version": None,
                "last_updated": None,
                "connected": False,
                "error": None,
            }
            self._locks[lock_id] = threading.Condition()

    def start(self) -> None:
        """
        Starts the LockManager's background threads for MQTT message processing and device polling.

        Raises:
            RuntimeError: If threads fail to start (rare, indicates threading system issues).
        """
        if self._running:
            logger.debug("LockManager already running, ignoring second start()")
            return
        # Start thread
        self._running = True
        self._main_thread.start()
        # Start status polling
        self._poll_thread.start()
        logger.info("LockManager started")

    def stop(self) -> None:
        """
        Gracefully stops the LockManager's background threads.
        Threads are joined with a timeout to avoid indefinite blocking.

        Note:
            This method should be called before program exit to ensure clean shutdown
            of background operations.
        """
        # Stop main thread
        self._running = False

        # Unblock get_message by publishing a dummy message to a known topic
        for lock_id in self._lock_ids:
            self._mqtt_service.publish(f"devices/{lock_id}/status", {"state": "noop"})

        # Wait for threads
        self._main_thread.join(timeout=2.0)
        self._poll_thread.join(timeout=2.0)

        logger.info("LockManager stopped")

    def _poll_loop(self) -> None:
        """
        Background thread function that periodically sends status queries to all managed locks.
        This enables periodic health checks and state synchronization for all devices.
        """
        while self._running:
            # Query status
            for lock_id in self._lock_ids:
                self.query_status(lock_id)
            # Check for stale devices
            self._check_stale_devices(max_age=10.0)
            time.sleep(self._poll_interval)

    def _check_stale_devices(self, max_age: float = 10.0) -> None:
        """
        Marks devices as disconnected if they haven't reported status within a given time window.

        Args:
            max_age: Maximum allowed age in seconds since last update before a device is considered stale.
        """
        # Check initial time for stale check
        now = time.time()
        with self._state_lock:
            # Check last updated for all devices
            for lock_id, state in self._device_states.items():
                last = state.get("last_updated")
                if last is None:
                    continue
                age = now - last
                if age > max_age and state.get("connected", True):
                    # Set connected state
                    logger.warning(
                        f"[{lock_id}] Device stale — no update in {age:.1f}s"
                    )
                    state["connected"] = False
                    state["error"] = "stale"

    def register_callback(
        self, lock_id: str, callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Registers a callback to be called on state change for a lock.

        Args:
            lock_id: The lock to observe.
            callback: A function to call with the new state.
        """
        with self._callbacks_lock:
            if lock_id not in self._callbacks:
                self._callbacks[lock_id] = []
        # Append to list of callbacks
        self._callbacks[lock_id].append(callback)

    @property
    def status(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns a thread-safe snapshot of all device states.

        Returns:
            A dictionary of lock_id to its current state dict.
        """
        with self._state_lock:
            return {k: dict(v) for k, v in self._device_states.items()}

    def get_status(self, lock_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns the current state of a specific lock.

        Args:
            lock_id: The ID of the lock.

        Returns:
            A shallow copy of the lock's last known state, or None if not found.
        """
        with self._state_lock:
            # Safe convert to appease pylance
            state = self._device_states.get(lock_id)
            return dict(state) if isinstance(state, dict) else None

    def get_mqtt_metrics(self) -> Dict[str, Optional[float]]:
        """
        Returns MQTT connection health metrics.

        Returns:
            A dictionary of connection stats.
        """
        # Checks thread safe properties in service layer
        return {
            "connected": self._mqtt_service.connected,
            "last_reconnect_attempt_time": self._mqtt_service.last_reconnect_attempt_time,
            "reconnect_attempts": self._mqtt_service.reconnect_attempts,
            "last_message_received_time": self._mqtt_service.last_message_received_time,
        }

    def _send_command_and_wait(
        self, lock_id: str, action: str, timeout: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        """
        Sends a control command to a lock and waits for its response.

        Args:
            lock_id: The lock to control.
            action: The command action (\"lock\" or \"unlock\").
            timeout: Seconds to wait for a response.

        Returns:
            A dictionary containing the updated lock status or error state.
        """
        # Format topic and payload
        topic = f"devices/{lock_id}/command"
        payload = {"action": action}
        return self._publish_and_wait(lock_id, topic, payload, timeout)

    def lock(self, lock_id: str) -> Optional[Dict[str, Any]]:
        """
        Sends a lock command to the specified device and waits for a response.

        This method publishes a lock command to the device's MQTT command topic
        and blocks until a status response is received or a timeout occurs. It returns
        the device's latest known state, including any error or timeout information.

        Args:
            lock_id: The unique identifier of the lock device to control.

        Returns:
            A dictionary containing the updated device state, or None if the device
            is unknown. If the device fails to respond in time, the state will include
            {"connected": False, "error": "timeout"}.
        """
        return self._send_command_and_wait(lock_id, "lock")

    def unlock(self, lock_id: str) -> Optional[Dict[str, Any]]:
        """
        Sends an unlock command to the specified device and waits for a response.

        This method publishes an unlock command to the device's MQTT command topic
        and blocks until a status response is received or a timeout occurs. It returns
        the device's latest known state, including any error or timeout information.

        Args:
            lock_id: The unique identifier of the lock device to control.

        Returns:
            A dictionary containing the updated device state, or None if the device
            is unknown. If the device fails to respond in time, the state will include
            {"connected": False, "error": "timeout"}.
        """
        return self._send_command_and_wait(lock_id, "unlock")

    def _publish_and_wait(
        self, lock_id: str, topic: str, payload: Dict[str, Any], timeout: float
    ) -> Optional[Dict[str, Any]]:
        """
        Publishes a command or query to a specific lock and waits for its response.

        This method sends a message to the device over MQTT and blocks until a corresponding
        status update is received or the timeout period elapses. It uses a per-device condition
        variable to synchronize the response with the background message processor.

        Args:
            lock_id: The ID of the target lock device.
            topic: The MQTT topic to publish the message to.
            payload: The command or query payload to send.
            timeout: The maximum time in seconds to wait for a response.

        Returns:
            A shallow copy of the lock's latest known state, or None if the lock is unknown.
            If a timeout occurs, the returned state will include {"connected": False, "error": "timeout"}.
        """
        # Publish to topic
        self._mqtt_service.publish(topic, payload)
        cond = self._locks[lock_id]
        # Wait for lock notify
        with cond:
            success = cond.wait(timeout=timeout)

        # Log error
        if not success:
            logger.warning(f"[{lock_id}] Timeout waiting for response to {payload}")
            with self._state_lock:
                if lock_id in self._device_states:
                    self._device_states[lock_id]["connected"] = False
                    self._device_states[lock_id]["error"] = "timeout"
                    self._device_states[lock_id]["last_updated"] = time.time()

        # Return status
        return self.get_status(lock_id)

    def query_status(
        self, lock_id: str, timeout: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        """
        Sends a status query to the device and waits for the response.

        Args:
            lock_id: Lock ID to query.
            timeout: Seconds to wait for reply.

        Returns:
            A dictionary with updated device status, or includes an error/timeout if no response.
        """
        # Queries go to status/get topic
        topic = f"devices/{lock_id}/status/get"
        payload = {"action": "get_status"}
        # Return result
        return self._publish_and_wait(lock_id, topic, payload, timeout)

    def _process_messages(self) -> None:
        """
        Background thread function that continuously processes incoming MQTT messages.

        Messages not matching the expected topic pattern (e.g., devices/{lock_id}/status)
        are ignored with an warning.

        Notes:
            - The method assumes that messages are dictionaries with "topic" and "payload" keys.
            - Payload validation ensures safe processing and guards against malformed input.
        """
        # Loop while running
        while self._running:
            # Check for message in service layer
            if self._mqtt_service.has_message():
                # Timeout block wait for service to return message
                msg = self._mqtt_service.get_message(timeout=1.0)
                if not msg:
                    # Should not get here
                    logger.warning(
                        "Service did not return new message despite stating it has a message!"
                    )
                    continue

                # Split the topic to process
                topic = msg["topic"]
                parts = topic.split("/")
                # Make sure topic is valid
                if len(parts) != 3 or parts[0] != "devices" or parts[2] != "status":
                    logger.debug(f"Ignored irrelevant topic: {topic}")
                    continue

                # Get lock id and validate
                lock_id = parts[1]
                payload = self._validate_payload(msg.get("payload"))
                if payload is None:
                    logger.warning(f"[{lock_id}] Invalid payload format or type")
                    continue

                # Handle returned status
                if "error" in payload:
                    self._handle_error(lock_id, payload["error"])
                else:
                    self._handle_status(lock_id, payload)

    def _validate_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        """
        Validates the structure of an incoming MQTT payload.

        Ensures the payload is a dictionary with only string keys.
        This prevents malformed data from being processed by status or error handlers.

        Args:
            payload: The raw payload object to validate.

        Returns:
            The original payload if valid, or None if invalid.
        """
        # Payload must be dict
        if not isinstance(payload, dict):
            return None
        # Should have string keys
        if not all(isinstance(k, str) for k in payload.keys()):
            return None
        return payload

    def _handle_error(self, lock_id: str, error: str) -> None:
        """
        Processes an error message reported by a device.

        Updates the internal state of the device with the error message, sets it as connected,
        and updates the last_updated timestamp. Notifies any thread waiting on the device's
        condition variable.

        Args:
            lock_id: The ID of the device reporting the error.
            error: The error message received from the device.
        """
        # Log error and change device state
        logger.warning(f"[{lock_id}] Error from device: {error}")
        with self._state_lock:
            self._device_states[lock_id]["error"] = error
            self._device_states[lock_id]["connected"] = True
            self._device_states[lock_id]["last_updated"] = time.time()

        # Notify condition of response
        cond = self._locks.get(lock_id)
        if cond:
            with cond:
                cond.notify_all()

    def _handle_status(self, lock_id: str, payload: Dict[str, Any]) -> None:
        """
        Processes a valid status update from a device.

        Args:
            lock_id: The ID of the device sending the status update.
            payload: A dictionary containing status fields such as 'state', 'battery_percent',
                    and 'firmware_version'.
        """
        # Configure the state
        new_state = {
            "state": payload.get("state"),
            "battery_percent": payload.get("battery_percent"),
            "firmware_version": payload.get("firmware_version"),
            "last_updated": time.time(),
            "connected": True,
            "error": None,
        }

        # Update device
        with self._state_lock:
            self._device_states[lock_id] = new_state

        # Notify condition
        cond = self._locks.get(lock_id)
        if cond:
            with cond:
                cond.notify_all()

        # Trigger callback
        with self._callbacks_lock:
            callbacks = list(self._callbacks.get(lock_id, []))
        for cb in callbacks:
            # Safe handler
            def safe_cb(cb=cb, state=dict(new_state)):
                try:
                    cb(state)
                except Exception as e:
                    logger.warning(f"Callback error for {lock_id}: {e}")

            # Call in new thread
            threading.Thread(target=safe_cb, daemon=True).start()
