import os
import json
import logging
import ssl
import paho.mqtt.client as mqtt
from typing import Callable, Optional, Dict

logger = logging.getLogger("MQTTDeviceWrapper")


class MQTTDeviceWrapper:
    """
    A generic MQTT device wrapper that manages subscription to device-specific
    command and status topics, handles commands, and publishes device status.
    Suitable for simulating or implementing IoT devices like smart locks.

    By default, the "get_status" command is registered and handled automatically.

    Topics used:
    - devices/{deviceId}/command
    - devices/{deviceId}/status/get
    - devices/{deviceId}/status
    """

    def __init__(
        self,
        device_id: str,
        broker: str,
        port: int,
        username: str,
        password: str,
        ca_cert_path: str,
    ) -> None:
        """
        Initializes the MQTTDeviceWrapper.

        By default, registers the "get_status" command to allow status retrieval.

        Args:
            device_id (str): Unique identifier for the device.
            broker (str): Address of the MQTT broker.
            port (int): Port number to connect to on the broker.
            username (str): MQTT username for authentication.
            password (str): MQTT password for authentication.
            ca_cert_path (str): Path to CA certificate for TLS encryption.
        """
        if not os.path.exists(ca_cert_path):
            raise FileNotFoundError(f"Missing CA cert: {ca_cert_path}")

        # Set internals
        self.device_id: str = device_id
        self.command_topic: str = f"devices/{device_id}/command"
        self.status_get_topic: str = f"devices/{device_id}/status/get"
        self.status_topic: str = f"devices/{device_id}/status"
        self.broker: str = broker
        self.port: int = port

        # Instantiate callback maps
        self._command_handlers: Dict[str, Callable[[], None]] = {}
        self._status_publisher: Optional[Callable[[], dict]] = None

        # Give python control of verification
        context = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH, cafile=ca_cert_path
        )
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        # Setup client
        self.client = mqtt.Client(client_id=device_id)
        self.client.tls_set_context(context)
        self.client.username_pw_set(username, password)
        self.client.enable_logger(logger)

        # Set up mqtt callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        # For get status requests
        self.register_command("get_status", self._publish_status)

    @classmethod
    def from_env(cls) -> "MQTTDeviceWrapper":
        """
        Instantiates the wrapper using environment variables.

        Required environment variables:
        - DEVICE_ID
        - MQTT_HOST
        - PORT
        - MQTT_USERNAME
        - MQTT_PASSWORD
        - TLS_CA_CERT

        Returns:
            MQTTDeviceWrapper: Configured device wrapper instance.

        Raises:
            RuntimeError: If any required environment variables are missing.
        """
        required_vars = [
            "DEVICE_ID",
            "MQTT_HOST",
            "PORT",
            "MQTT_USERNAME",
            "MQTT_PASSWORD",
            "TLS_CA_CERT",
        ]
        # Make sure necessary variables are available
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        # Call constructor with env variables
        return cls(
            device_id=os.environ["DEVICE_ID"],
            broker=os.environ["MQTT_HOST"],
            port=int(os.environ["PORT"]),
            username=os.environ["MQTT_USERNAME"],
            password=os.environ["MQTT_PASSWORD"],
            ca_cert_path=os.environ["TLS_CA_CERT"],
        )

    def _on_connect(self, client: mqtt.Client, userdata, flags, rc: int) -> None:
        """
        MQTT connection callback. Subscribes to command and status request topics.

        Args:
            client (mqtt.Client): The MQTT client instance.
            userdata: User data (unused).
            flags: Response flags from the broker.
            rc (int): Connection result.
        """
        # Raise broken connect
        if rc != 0:
            raise ConnectionError(
                f"[{self.device_id}] Connection failed with code {rc}"
            )
        logger.info(f"[{self.device_id}] Connected successfully")

        # Subscribe to the command status get topic
        client.subscribe(self.command_topic, qos=1)
        client.subscribe(self.status_get_topic, qos=1)
        logger.debug(
            f"[{self.device_id}] Subscribed to:\n - {self.command_topic}\n - {self.status_get_topic}"
        )

    def _on_disconnect(self, client: mqtt.Client, userdata, rc: int) -> None:
        """
        MQTT disconnection callback.

        Called when the client disconnects from the broker. Logs the disconnection
        reason code for monitoring and debugging purposes.

        Args:
            client (mqtt.Client): The MQTT client instance.
            userdata: User-defined data of any type (not used here).
            rc (int): Disconnection result code. A value of 0 indicates a clean disconnection;
                    non-zero values indicate unexpected disconnects or errors.
        """
        logger.warning(f"[{self.device_id}] Disconnected with code {rc}")

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        """
        MQTT message callback. Handles command or status request messages.

        Args:
            client (mqtt.Client): The MQTT client instance.
            userdata: User data (unused).
            msg (mqtt.MQTTMessage): Incoming MQTT message.
        """
        try:
            # Parse payload
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            action = payload.get("action")

            # Status update
            if topic == self.status_get_topic:
                logger.debug(f"[{self.device_id}] Received status request")
                # Missing action in get status
                if not action:
                    logger.warning(
                        f"[{self.device_id}] No 'action' in get status payload"
                    )
                    # Application is probably waiting for a response
                    self._publish_status(error="missing action")
                    return
                self._publish_status()
                return

            # Command requested
            if topic == self.command_topic:
                # Missing action in commmand
                if not action:
                    logger.warning(f"[{self.device_id}] No 'action' in command payload")
                    # Application is probably waiting for a response
                    self._publish_status(error="missing action")
                    return

                # Check map for callback
                handler = self._command_handlers.get(action)
                if handler:
                    logger.debug(f"[{self.device_id}] Handling action: {action}")
                    handler()
                    # Publish status in response
                    self._publish_status()
                else:
                    logger.warning(
                        f"[{self.device_id}] No handler for action: {action}"
                    )
                    # Respond with missing command error
                    self._publish_status(error=f"unhandled command: {action}")
        except Exception as e:
            logger.error(f"[{self.device_id}] Failed to handle message: {e}")
            self._publish_status(error=f"exception: {str(e)}")

    def register_command(self, action: str, handler: Callable[[], None]) -> None:
        """
        Registers a command handler for a specific action.

        Args:
            action (str): The name of the action to handle.
            handler (Callable[[], None]): A function to call when the action is received.
        """
        # Add to map
        self._command_handlers[action] = handler
        logger.info(f"[{self.device_id}] Registered handler for action '{action}'")

    def register_publisher(self, publisher_fn: Callable[[], dict]) -> None:
        """
        Registers a function to publish the device's current status.

        Args:
            publisher_fn (Callable[[], dict]): Function that returns a status dictionary.
        """
        # Single status callback
        self._status_publisher = publisher_fn
        logger.info(f"[{self.device_id}] Status publisher registered")

    def _publish_status(self, qos: int = 1, error: Optional[str] = None) -> None:
        """
        Publishes a status or error payload to the device's status topic.

        Args:
            qos (int, optional): Quality of Service level. Defaults to 1.
            error (str, optional): If provided, publishes an error message instead of status.
        """
        try:
            if error:
                # Error publish
                payload = json.dumps({"error": error})
            elif not self._status_publisher:
                payload = json.dumps({"error": "status callback not registered"})
            else:
                # Get status from call back
                status = self._status_publisher()
                payload = json.dumps(status)
            # Publish
            self.client.publish(self.status_topic, payload, qos=qos)
            logger.debug(
                f"[{self.device_id}] Published status with QoS {qos}: {payload}"
            )
        except Exception as e:
            # Fatal error, no response to app
            logger.error(f"[{self.device_id}] Failed to publish status: {e}")

    def start(self) -> None:
        """
        Connects to the MQTT broker and starts the event loop.

        Raises:
            ConnectionError: If connection to the broker fails.
        """
        try:
            # Start client and loop
            self.client.connect(self.broker, self.port)
            self.client.loop_start()
            logger.info(f"[{self.device_id}] MQTT loop started")
        except Exception as e:
            raise ConnectionError(f"[{self.device_id}] MQTT connection failed: {e}")

    def stop(self) -> None:
        """
        Stops the MQTT loop and disconnects from the broker.
        """
        # Safe disconnect
        self.client.loop_stop()
        self.client.disconnect()
        logger.info(f"[{self.device_id}] Disconnected cleanly")
