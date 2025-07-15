import json
import os
import threading
import time
import queue
import logging
from typing import Optional, Tuple, List, Dict
import paho.mqtt.client as mqtt
from paho.mqtt.client import Client
from paho.mqtt.enums import CallbackAPIVersion

logger = logging.getLogger("MQTTServiceLayer")

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
        service_id: str = "ServiceLayer",
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
            tls_key (str, optional): Path to client key file for TLS.
            message_queue (queue.Queue, optional): A queue to place incoming parsed messages into.
        """
        # Internal data
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.tls_ca = tls_ca
        self._lock = threading.Lock()

        # Received message queue
        self._message_queue: queue.Queue = message_queue or queue.Queue()
        self._pending_subscriptions: List[Tuple[str, int]] = []

        # MQTT client and setup
        self.client = Client(
            protocol=mqtt.MQTTv5,
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=service_id,
        )
        self.client.reconnect_delay_set(min_delay=1, max_delay=RECONNECT_BACKOFF)
        if username and password:
            self.client.username_pw_set(username, password)
        if tls_ca:
            self.client.tls_set(ca_certs=tls_ca)

        # Callback setups
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # State data
        self._connected: bool = False
        self._set_connected(False)

        # Connection metrics
        self._last_message_received_time: Optional[float] = None
        self._metrics_lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "MQTTService":
        """
        Creates an instance of MQTTService using environment variables.

        This method loads connection parameters from the environment and constructs
        a fully configured MQTTService instance, ready for use in Dockerized or
        host-based deployments.

        Returns:
            MQTTService: An initialized MQTTService instance.

        Raises:
            KeyError: If required environment variables are missing.
            ValueError: If MQTT_PORT is not a valid integer.
        """
        return cls(
            broker_host=os.environ["MQTT_HOST"],
            broker_port=int(os.environ.get("MQTT_PORT", "8883")),
            username=os.environ["MQTT_USERNAME"],
            password=os.environ["MQTT_PASSWORD"],
            tls_ca=os.environ.get("MQTT_CA"),
            service_id=os.environ.get("DEVICE_ID", "lock_mgr"),
        )

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
        logger.info("[MQTT] Attempting connection!")
        try:
            # Connect to configure port
            self.client.connect(self.broker_host, self.broker_port)
            # Start the background thread
            self.client.loop_start()
        except Exception as e:
            logger.info(f"[MQTT] Initial connection failed: {e}")

    def stop(self) -> None:
        """
        Stop the background loop and disconnect from the broker.
        """
        # Disconnect and break loop
        logger.info("MQTT client disconnected")
        # Clean up internal threads, if any
        self.client.loop_stop()
        # Then disconnect
        self.client.disconnect()

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

    def _on_connect(
        self, client: mqtt.Client, userdata, flags, rc: int, properties=None
    ) -> None:
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

    def _on_disconnect(
        self, client: mqtt.Client, userdata, disconnect_flags, rc, properties=None
    ) -> None:
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
        logger.debug("[MQTT] Received message!")
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
