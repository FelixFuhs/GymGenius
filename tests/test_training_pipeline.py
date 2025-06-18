import unittest
from unittest.mock import patch

from engine.app import app


class TestTrainingPipelineEnqueue(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("engine.tasks.queue.enqueue")
    def test_job_is_enqueued(self, mock_enqueue):
        response = self.client.post("/v1/system/trigger-training-pipeline", json={})
        self.assertEqual(response.status_code, 200)
        mock_enqueue.assert_called_once()

    @patch("engine.tasks.queue.enqueue")
    def test_job_has_retry_strategy(self, mock_enqueue):
        response = self.client.post("/v1/system/trigger-training-pipeline", json={})
        self.assertEqual(response.status_code, 200)
        retry = mock_enqueue.call_args.kwargs.get("retry")
        from rq import Retry

        self.assertIsInstance(retry, Retry)
        self.assertEqual(retry.max, 3)


if __name__ == "__main__":
    unittest.main()
