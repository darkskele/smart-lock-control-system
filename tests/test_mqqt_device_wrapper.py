import unittest
import os
from unittest.mock import patch, MagicMock
from simulator.smart_lock_device.mqtt_wrapper.mqtt_device_wrapper import MQTTDeviceWrapper


class TestMQTTDeviceWrapper(unittest.TestCase):

    @patch.dict(
        os.environ,
        {
            "DEVICE_ID": "dev123",
            "MQTT_HOST": "localhost",
            "PORT": "8883",
            "MQTT_USERNAME": "user",
            "MQTT_PASSWORD": "pass",
            "TLS_CA_CERT": "/tmp/fake.crt",
        },
    )
    @patch("os.path.exists", return_value=True)
    @patch("ssl.create_default_context")
    @patch("paho.mqtt.client.Client")
    def test_from_env_success(self, mock_client, mock_ssl_ctx, mock_exists):
        """
        Test that MQTTDeviceWrapper.from_env() correctly parses environment variables
        and constructs the wrapper using a mocked cert path and MQTT client.
        """
        mock_context = MagicMock()
        mock_ssl_ctx.return_value = mock_context

        wrapper = MQTTDeviceWrapper.from_env()

        assert wrapper.device_id == "dev123"
        mock_ssl_ctx.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_missing_vars_raises(self):
        """
        Test that missing required environment variables raise a RuntimeError.
        """
        with self.assertRaises(RuntimeError) as cm:
            MQTTDeviceWrapper.from_env()
        assert "Missing required environment variables" in str(cm.exception)

    @patch("os.path.exists", return_value=True)
    @patch("paho.mqtt.client.Client")
    @patch("ssl.create_default_context")
    def test_register_command_and_publisher(self, mock_ssl, mock_client, mock_exists):
        """
        Test that register_command() and register_publisher() store their callbacks properly.
        """
        wrapper = MQTTDeviceWrapper(
            device_id="dev1",
            broker="localhost",
            port=8883,
            username="user",
            password="pass",
            ca_cert_path="/tmp/fake.crt",
        )

        dummy_handler = MagicMock()
        wrapper.register_command("lock", dummy_handler)
        self.assertEqual(wrapper._command_handlers["lock"], dummy_handler)

        dummy_status = MagicMock(return_value={"locked": True})
        wrapper.register_publisher(dummy_status)
        self.assertEqual(wrapper._status_publisher, dummy_status)

    @patch("os.path.exists", return_value=True)
    @patch("paho.mqtt.client.Client")
    @patch("ssl.create_default_context")
    def test_on_connect_subscribes(self, mock_ssl, mock_client_class, mock_exists):
        """
        Test that _on_connect() correctly subscribes to the command and status request topics.
        """
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        wrapper = MQTTDeviceWrapper(
            device_id="dev2",
            broker="localhost",
            port=8883,
            username="user",
            password="pass",
            ca_cert_path="/tmp/fake.crt",
        )

        wrapper._on_connect(mock_client, None, None, rc=0)

        mock_client.subscribe.assert_any_call(wrapper.command_topic, qos=1)
        mock_client.subscribe.assert_any_call(wrapper.status_get_topic, qos=1)

    @patch("os.path.exists", return_value=True)
    @patch("paho.mqtt.client.Client")
    @patch("ssl.create_default_context")
    def test_publish_status(self, mock_ssl, mock_client_class, mock_exists):
        """
        Test that _publish_status() serializes the publisher's output and publishes it to MQTT.
        """
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        wrapper = MQTTDeviceWrapper(
            device_id="dev3",
            broker="localhost",
            port=8883,
            username="user",
            password="pass",
            ca_cert_path="/tmp/fake.crt",
        )

        # Register a dummy publisher that returns a known status
        wrapper.register_publisher(lambda: {"locked": False})
        wrapper._publish_status()

        args, kwargs = mock_client.publish.call_args
        assert args[0] == wrapper.status_topic
        assert '{"locked": false}' in args[1]

    @patch("os.path.exists", return_value=True)
    @patch("paho.mqtt.client.Client")
    @patch("ssl.create_default_context")
    def test_start_and_stop(self, mock_ssl, mock_client_class, mock_exists):
        """
        Test that start() and stop() correctly call MQTT connect, loop start/stop, and disconnect.
        """
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        wrapper = MQTTDeviceWrapper(
            device_id="dev4",
            broker="localhost",
            port=8883,
            username="user",
            password="pass",
            ca_cert_path="/tmp/fake.crt",
        )

        wrapper.start()
        mock_client.connect.assert_called_with("localhost", 8883)
        mock_client.loop_start.assert_called_once()

        wrapper.stop()
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
