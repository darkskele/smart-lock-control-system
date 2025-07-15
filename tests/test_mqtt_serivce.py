import unittest
from unittest.mock import MagicMock, patch
from application.service_layer.mqtt_service_layer import MQTTService
import queue
import json


class TestMQTTService(unittest.TestCase):
    def setUp(self):
        # Set up a shared message queue and instance of MQTTService
        self.msg_queue = queue.Queue()
        self.service = MQTTService("test-broker", 8883, message_queue=self.msg_queue)

    @patch("application.service_layer.mqtt_service_layer.mqtt.Client")
    def test_initial_connection(self, mock_client_class):
        """
        Verify that MQTTService correctly attempts to connect to the broker.
        """
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Must instantiate inside patch scope so the mock applies
        service = MQTTService("test-broker", 8883)
        service.client = mock_client  # Bypass the real thread loop
        service.start()

        mock_client.connect.assert_called_with("test-broker", 8883)

    def test_publish_connected(self):
        """
        If the client is connected, it should publish JSON messages to the broker.
        """
        self.service._set_connected(True)
        self.service.client.publish = MagicMock()

        self.service.publish("devices/test/command", {"action": "lock"})

        self.service.client.publish.assert_called_once()
        topic, payload = self.service.client.publish.call_args[0]
        self.assertEqual(topic, "devices/test/command")
        self.assertEqual(json.loads(payload), {"action": "lock"})

    def test_publish_not_connected(self):
        """
        If not connected, publish should be skipped and no calls made.
        """
        self.service._set_connected(False)
        self.service.client.publish = MagicMock()

        self.service.publish("devices/test/command", {"action": "lock"})

        self.service.client.publish.assert_not_called()

    def test_subscribe_when_connected(self):
        """
        If connected, subscription should happen immediately via the client.
        """
        self.service._set_connected(True)
        self.service.client.subscribe = MagicMock()

        self.service.subscribe("devices/+/status", qos=1)

        self.service.client.subscribe.assert_called_once_with("devices/+/status", 1)

    def test_subscribe_when_disconnected(self):
        """
        If not connected, the subscription should be queued for later.
        """
        self.service._set_connected(False)

        self.service.subscribe("devices/+/status", qos=1)

        self.assertIn(("devices/+/status", 1), self.service._pending_subscriptions)

    def test_on_message_valid_json(self):
        """
        A valid JSON message should be decoded and pushed to the queue.
        """
        msg = MagicMock()
        msg.topic = "devices/test/status"
        msg.payload = b'{"state": "locked"}'
        msg.qos = 0
        msg.retain = False

        self.service._on_message(None, None, msg)
        result = self.msg_queue.get_nowait()

        self.assertEqual(result["topic"], "devices/test/status")
        self.assertEqual(result["payload"], {"state": "locked"})

    def test_on_message_invalid_json(self):
        """
        If payload is invalid JSON, no message should be queued.
        """
        msg = MagicMock()
        msg.topic = "devices/test/status"
        msg.payload = b"{this is not json"
        msg.qos = 0
        msg.retain = False

        self.service._on_message(None, None, msg)

        self.assertTrue(self.msg_queue.empty())

    def test_has_message_true(self):
        """
        Test that `has_message()` returns True when a message is in the queue.
        """
        self.service._message_queue.put({"test": "data"})
        self.assertTrue(self.service.has_message())

    def test_has_message_false(self):
        """
        Test that `has_message()` returns False when the queue is empty.
        """
        self.assertFalse(self.service.has_message())

    def test_get_message_returns_value(self):
        """
        Test that `get_message()` returns the expected message from the queue.
        """
        message = {"foo": "bar"}
        self.service._message_queue.put(message)
        result = self.service.get_message(timeout=0.1)
        self.assertEqual(result, message)

    def test_get_message_returns_none_on_timeout(self):
        """
        Test that `get_message()` returns None if no message is available within timeout.
        """
        result = self.service.get_message(timeout=0.1)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
