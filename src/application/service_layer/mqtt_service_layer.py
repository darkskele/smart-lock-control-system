import json
import threading
import time
import queue
import logging
from typing import Optional, Tuple, List, Dict
import paho.mqtt.client as mqtt
from paho.mqtt.client import Client
from paho.mqtt.enums import CallbackAPIVersion

logger = logging.getLogger("MQTTServiceLayer")

MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_BACKOFF = 5  # seconds


class MQTTService:
    """
    Handles MQTT connection, message publishing, topic subscriptions, and dispatches parsed
    messages into a thread-safe queue for external consumption.
    """

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 8883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        tls_ca: Optional[str] = None,
        tls_cert: Optional[str] = None,
        tls_key: Optional[str] = None,
        message_queue: Optional[queue.Queue] = None,
    ) -> None:
        """
        Initialize the MQTT service.

        Args:
            broker_host (str): Hostname or IP of the MQTT broker.
            broker_port (int, optional): Port number to connect to (default is 1883).
            username (str, optional): Username for broker authentication.
            password (str, optional): Password for broker authentication.
            tls_ca (str, optional): Path to CA certificate file for TLS.
            tls_cert (str, optional): Path to client certificate file for TLS.
            tls_key (str, optional): Path to client key file for TLS.
            message_queue (queue.Queue, optional): A queue to place incoming parsed messages into.
        """
        # Internal data
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.tls_ca = tls_ca
        self.tls_cert = tls_cert
        self.tls_key = tls_key
        self._lock = threading.Lock()

        # Received message queue
        self._message_queue: queue.Queue = message_queue or queue.Queue()
        self._pending_subscriptions: List[Tuple[str, int]] = []

        # MQTT client and setup
        self.client = Client(
            protocol=mqtt.MQTTv5, callback_api_version=CallbackAPIVersion.VERSION2
        )
        if username and password:
            self.client.username_pw_set(username, password)
        if tls_ca:
            self.client.tls_set(ca_certs=tls_ca, certfile=tls_cert, keyfile=tls_key)

        # Callback setups
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # State data
        self._connected: bool = False
        self._set_connected(True)
        self._should_run: bool = True
        self._loop_thread = threading.Thread(target=self._loop, daemon=True)

        # Connection metrics
        self._last_reconnect_attempt_time: Optional[float] = None
        self._reconnect_attempts: int = 0
        self._last_message_received_time: Optional[float] = None
        self._metrics_lock = threading.Lock()

    @property
    def connected(self) -> bool:
        """
        Thread-safe read-only property indicating connection status.

        Returns:
            bool: True if the MQTT client is connected to the broker, False otherwise.
        """
        with self._lock:
            return self._connected

    @property
    def last_reconnect_attempt_time(self) -> Optional[float]:
        """
        Get the timestamp of the last reconnect attempt.

        Returns:
            Optional[float]: The Unix timestamp (in seconds) of the most recent reconnect attempt,
                            or None if no reconnect has been attempted yet.
        """
        with self._metrics_lock:
            return self._last_reconnect_attempt_time

    @property
    def reconnect_attempts(self) -> int:
        """
        Get the number of consecutive failed reconnect attempts.

        Returns:
            int: The number of times the client has attempted to reconnect
                since the last successful connection. This resets to 0 upon a successful connect.
        """
        with self._metrics_lock:
            return self._reconnect_attempts

    @property
    def last_message_received_time(self) -> Optional[float]:
        """
        Get the timestamp of the most recently received MQTT message.

        Returns:
            Optional[float]: The Unix timestamp (in seconds) of the last message received,
                            or None if no message has been received yet.
        """
        with self._metrics_lock:
            return self._last_message_received_time

    def _set_connected(self, value: bool = True) -> None:
        """
        Thread-safe internal setter for the connected state.

        Args:
            value (bool): New connection status.
        """
        with self._lock:
            self._connected = value

    def start(self) -> None:
        """
        Start the MQTT connection and run the background loop.
        """
        try:
            # Connect to configure port
            self.client.connect(self.broker_host, self.broker_port)
        except Exception as e:
            logger.info(f"[MQTT] Initial connection failed: {e}")
        # Start loop
        self._loop_thread.start()

    def stop(self) -> None:
        """
        Stop the background loop and disconnect from the broker.
        """
        # Disconnect and break loop
        logger.info("MQTT client disconnected")
        self._should_run = False
        self.client.disconnect()
        # Clean up internal threads, if any
        self.client.loop_stop()
        # Wait for the loop to fully exit
        self._loop_thread.join()

    def publish(self, topic: str, message_dict: Dict) -> None:
        """
        Publish a message to the given topic.

        Args:
            topic (str): MQTT topic to publish to.
            message_dict (dict): Dictionary to be serialized as JSON payload.
        """
        # Only publish to valid connections
        if self.connected:
            try:
                # Payload to json
                payload = json.dumps(message_dict)
                self.client.publish(topic, payload)
            except Exception as e:
                logger.info(f"[MQTT] Failed to publish to {topic}: {e}")
        else:
            logger.info("[MQTT] Cannot publish — not connected")

    def subscribe(self, topic: str, qos: int = 0) -> None:
        """
        Subscribe to an MQTT topic.

        Args:
            topic (str): Topic to subscribe to.
            qos (int, optional): Quality of Service level (0, 1, or 2). Defaults to 0.
        Raises:
            ValueError: If QoS code is not correct.
        """
        if qos not in (0, 1, 2):
            raise ValueError("QoS must be 0, 1, or 2")
        # Can only subscribe when connected
        if self.connected:
            self.client.subscribe(topic, qos)
            logger.info(f"[MQTT] Subscribed to topic: {topic}")
        else:
            # Queue subscription for after connection to broker
            self._pending_subscriptions.append((topic, qos))
            logger.info(f"[MQTT] Queued subscription (not yet connected): {topic}")

    def has_message(self) -> bool:
        """
        Returns True if there is at least one message in the queue.
        """
        return not self._message_queue.empty()

    def get_message(self, timeout: Optional[float] = None) -> Optional[Dict]:
        """
        Safely retrieve the next message from the queue, or return None.

        Args:
            timeout (float, optional): Time to wait (in seconds) before giving up.

        Returns:
            dict or None: The next message, or None if timeout expires.
        """
        try:
            return self._message_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _on_connect(self, client: mqtt.Client, userdata, flags, rc: int) -> None:
        """
        Callback triggered on successful connection to the broker.
        """
        self._set_connected(True)
        logger.info(f"[MQTT] Connected with code {rc}")

        # Subscribe to queued subscriptions
        for topic, qos in self._pending_subscriptions:
            client.subscribe(topic, qos)
            logger.info(f"[MQTT] Subscribed (deferred): {topic}")
        self._pending_subscriptions.clear()

    def _on_disconnect(self, client: mqtt.Client, userdata, rc: int) -> None:
        """
        Callback triggered on disconnection from the broker.
        """
        self._set_connected(False)
        logger.info(f"[MQTT] Disconnected with code {rc}")

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        """
        Callback triggered when a message is received from the broker.

        Args:
            msg (MQTTMessage): Incoming MQTT message.
        """
        decoded_payload = msg.payload.decode("utf-8", errors="replace")
        try:
            # Payload to dict
            payload_dict = json.loads(decoded_payload)
            # Store alongside topic it was received on and raw message
            self._message_queue.put(
                {
                    "topic": msg.topic,
                    "payload": payload_dict,
                    "raw": msg.payload,
                    "qos": msg.qos,
                    "retain": msg.retain,
                }
            )
            # Log receive time
            with self._metrics_lock:
                self._last_message_received_time = time.time()
        except json.JSONDecodeError:
            logger.warning(
                f"[MQTT] Invalid JSON payload on topic '{msg.topic}': {decoded_payload}"
            )
        except Exception as e:
            logger.info(f"[MQTT] Error parsing message on topic '{msg.topic}': {e}")

    def _loop(self) -> None:
        """
        Runs the MQTT loop to process network traffic and automatically attempts reconnects,
        with shutdown and backoff control.
        """
        reconnect_attempts = 0

        while self._should_run:
            try:
                # Run one iteration of the MQTT loop (blocking up to 1s)
                self.client.loop(timeout=1.0)

                if not self.connected:
                    if reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                        logger.info("[MQTT] Max reconnect attempts reached. Stopping.")
                        break

                    logger.info(
                        f"[MQTT] Attempting reconnect ({reconnect_attempts + 1}/{MAX_RECONNECT_ATTEMPTS})..."
                    )
                    time.sleep(RECONNECT_BACKOFF)

                    # Exit cleanly if we're shutting down
                    if not self._should_run:
                        break

                    try:
                        # Set connection metrics
                        with self._metrics_lock:
                            self._last_reconnect_attempt_time = time.time()
                            self._reconnect_attempts += 1
                        # Attempt to reconnect
                        self.client.reconnect()
                    except Exception as e:
                        logger.info(f"[MQTT] Reconnect failed: {e}")

                else:
                    with self._metrics_lock:
                        self._reconnect_attempts = 0  # Reset on successful loop

            except Exception as e:
                logger.info(f"[MQTT] Loop error: {e}")
                time.sleep(5)

        # Safe disconnect on exit
        if self.connected:
            try:
                self.client.disconnect()
            except Exception:
                pass
