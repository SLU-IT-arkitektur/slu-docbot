import datetime
import json
import logging
import unittest
from unittest.mock import Mock, patch
from server.feedback_handler import handle_feedback


class TestHandleFeedback(unittest.TestCase):

    def setUp(self):
        print(f'{__name__} :: {self._testMethodName}')
        # Create a mock RedisStore
        self.mock_redis = Mock()
        # mute all logging
        logging.getLogger().disabled = True

    def test_handle_feedback_bad_input(self):
        feedback = "not a thumb"
        response = handle_feedback(feedback, "interaction_id", self.mock_redis)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.body), {"message": "Please enter thumbsup or thumbsdown"})

    def test_handle_feedback_case_insensitive(self):
        feedback = "ThUmBsUp"
        self.mock_redis.get_interaction.return_value = {"interaction_id": "interaction_id", "feedback": "thumbsup"}
        response = handle_feedback(feedback, "interaction_id", self.mock_redis)
        self.assertEqual(response, {"message": "Tack för din feedback!"})

    def test_handle_feedback_interaction_not_found(self):
        self.mock_redis.get_interaction.return_value = None
        response = handle_feedback("thumbsup", "interaction_id", self.mock_redis)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.body), {"message": "Interaction not found"})
    
    def test_handle_feedback_happy_path(self):
        feedback = "thumbsup"
        self.mock_redis.get_interaction.return_value = {"interaction_id": "interaction_id", "feedback": feedback}
        response = handle_feedback(feedback, "interaction_id", self.mock_redis)
        self.assertEqual(response, {"message": "Tack för din feedback!"})
        self.mock_redis.update_interaction.assert_called_once_with({"interaction_id": "interaction_id", "feedback": feedback}, 'interaction_id', datetime.timedelta(days=90))
