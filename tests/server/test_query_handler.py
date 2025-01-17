import json
import logging
from unittest.mock import Mock, patch
from server.query_handler import handle_query
from tests.base_test import BaseTest


class TestHandleQuery(BaseTest):

    def setUp(self):
        super().setUp()
        # Create a mock RedisStore
        self.mock_redis = Mock()
        # mute all logging
        logging.getLogger().disabled = True

    def test_empty_query(self):
        response = handle_query("", self.mock_redis)
        self.assertEqual(response.status_code, 400)
        response_body = response.body.decode('utf-8')
        self.assertEqual(response_body, '{"message":"Frågan får inte vara tom."}')

    def test_query_more_than_80_chars(self):
        response = handle_query("a" * 81, self.mock_redis)
        self.assertEqual(response.status_code, 400)
        response_body = response.body.decode('utf-8')
        self.assertEqual(response_body, '{"message":"Frågan får vara max 80 tecken lång."}')

    @patch('server.query_handler.settings')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_cache_hit(self, mock_get_embedding_semantic_cache, mock_get_embedding_query_handler, mock_settings):
        mock_settings.configure_mock(semantic_cache_enabled=True)

        # Mock get_embedding (in both places it is imported)
        fake_embedding = [0.1, 0.2, 0.3]
        mock_get_embedding_semantic_cache.return_value = fake_embedding
        mock_get_embedding_query_handler.return_value = fake_embedding

        # Mock search_semantic_cache (redis_store)
        mock_doc = Mock()
        very_small_diff = 1.54972076416e-06  # = 0.00000154972076416
        mock_doc.configure_mock(reply="test reply", section_headers_as_json="[]", query="original test query", vector_score=very_small_diff)
        self.mock_redis.search_semantic_cache.return_value = Mock(docs=[mock_doc])

        response = handle_query("test query", self.mock_redis)

        self.assertEqual(response["message"], "test reply")
        self.assertEqual(response["from_cache"], "true")
        self.assertEqual(response["sectionHeaders"], [])
        self.assertEqual(response["original_query"], "original test query")

    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    @patch('server.query_handler.call_chat_completions')
    @patch('server.query_handler.settings')
    @patch('server.query_handler.add_to_cache')
    @patch('server.query_handler.num_tokens_from_string')
    def test_call_to_open_ai(self, mock_num_tokens_from_string, mock_add_to_cache, mock_settings, mock_call_chat_completions, mock_get_embedding_semantic_cache, mock_get_embedding_query_handler):

        # Mock num_tokens_from_string to return 2000
        mock_num_tokens_from_string.return_value = 2000

        # Mock the OpenAI API response
        mocked_open_ai_response = "mocked open ai response"
        mock_call_chat_completions.return_value = mocked_open_ai_response

        # Configure mock settings
        mock_settings.configure_mock(semantic_cache_enabled=True,
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score=0.9,
                                     get_locale=Mock(return_value={"server_texts": {"not_similar_enough_to_context": "not similar enough to context", "errors": {"something_went_wrong": "something_went_wrong"}}}))

        # Mock return value for get_embedding
        fake_embedding = [0.1, 0.2, 0.3]
        mock_get_embedding_semantic_cache.return_value = fake_embedding
        mock_get_embedding_query_handler.return_value = fake_embedding

        # Mock search_semantic_cache in redis_store
        mock_doc = Mock()
        large_diff = 0.5
        mock_doc.configure_mock(reply="test reply", section_headers_as_json="[]", query="original test query", vector_score=large_diff)  # <-- large diff = no hit
        self.mock_redis = Mock()
        self.mock_redis.search_semantic_cache.return_value = Mock(docs=[mock_doc])

        # Mock search_sections in redis_store
        mock_section = Mock()
        very_small_diff = 1.54972076416e-06  # = 0.00000154972076416
        mock_section.configure_mock(header="test section header", body="b" * 2000, anchor_url="", num_of_tokens="2000", vector_score=very_small_diff)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section])

        # Call the query handler
        response = handle_query("test query", self.mock_redis)
        print(response["message"])

        # Assertions
        self.assertEqual(response["message"], "mocked open ai response")
        self.assertEqual(response["sectionHeaders"], ['test section header'])
        self.assertIsNotNone(response["interaction_id"])

        # Ensure add_to_cache is called correctly
        mock_add_to_cache.assert_called_with("test query", "mocked open ai response", json.dumps(['test section header']), self.mock_redis)

    @patch('server.query_handler.add_to_cache')
    @patch('server.query_handler.settings')
    @patch('server.query_handler.call_chat_completions')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_call_to_open_ai_without_semantic_cache(self, mock_get_embedding_semantic_cache, mock_get_embedding_query_handler, mock_call_chat_completions, mock_settings, mock_add_to_cache):

        mocked_open_ai_response = "mocked open ai response"
        mock_call_chat_completions.return_value = mocked_open_ai_response

        mock_settings.configure_mock(semantic_cache_enabled=False,  # <--- disabling semantic cache
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score=0.9)

        # Mock get_embedding (in both places it is imported)
        fake_embedding = [0.1, 0.2, 0.3]
        mock_get_embedding_semantic_cache.return_value = fake_embedding
        mock_get_embedding_query_handler.return_value = fake_embedding

        # Mock search_sections (redis_store)
        # returning mocked section with 2000 tokens and a very small diff (close hit)
        mock_section = Mock()
        very_small_diff = 1.54972076416e-06  # = 0.00000154972076416
        mock_section.configure_mock(header="test section header", body="b" * 2000, anchor_url="", num_of_tokens="2000", vector_score=very_small_diff)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section])

        # call query handler
        response = handle_query("test query", self.mock_redis)

        # assert that we moved passed the semantic cache (no hit close enough)
        # and that we were able to build a context and send a request to open ai
        # and that we got a response from the open ai client
        assert (response["message"] == "mocked open ai response")
        assert (response["sectionHeaders"] == ['test section header'])
        assert (response["interaction_id"] is not None)

        # finally since semantic_cache_enabled is False we should not have called add_to_cache or redis.search_semantic_cache
        mock_add_to_cache.assert_not_called()
        self.mock_redis.search_semantic_cache.assert_not_called()

    @patch('server.query_handler.settings')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_not_enough_context(self, mock_get_embedding_semantic_cache, mock_get_embedding_query_handler, mock_settings):

        mock_settings.configure_mock(semantic_cache_enabled=True,
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score=0.9,
                                     get_locale=Mock(return_value={"server_texts": {"not_similar_enough_to_context": "not similar enough to context"}}))

        # Mock get_embedding (in both places it is imported)
        fake_embedding = [0.1, 0.2, 0.3]
        mock_get_embedding_semantic_cache.return_value = fake_embedding
        mock_get_embedding_query_handler.return_value = fake_embedding

        # Mock search_semantic_cache (redis_store)
        # returning mocked doc
        mock_doc = Mock()
        large_diff = 0.5
        mock_doc.configure_mock(reply="test reply", section_headers_as_json="[]", query="original test query", vector_score=large_diff)  # <--- large diff = no hit
        self.mock_redis.search_semantic_cache.return_value = Mock(docs=[mock_doc])

        # Mock search_sections (redis_store)
        # returning mocked section with 2000 tokens and a very small diff (close hit)
        # BUT to small a context... num_of_tokens..
        mock_section = Mock()
        very_small_diff = 1.54972076416e-06  # = 0.00000154972076416
        mock_section.configure_mock(header="test section header", body="bb", num_of_tokens="2", vector_score=very_small_diff)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section])

        # call query handler
        response = handle_query("test query", self.mock_redis)
        # assert that we moved passed the semantic cache (no hit close enough)
        # and that we respond properly when we are unable to build a context with enough tokens
        assert (response["message"] == "not similar enough to context")
        assert (response["interaction_id"] is not None)

    @patch('server.query_handler.settings')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_no_relevant_sections(self, mock_get_embedding_semantic_cache, mock_get_embedding_query_handler, mock_settings):

        mock_settings.configure_mock(semantic_cache_enabled=True,
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score=0.9,
                                     get_locale=Mock(return_value={"server_texts": {"not_similar_enough_to_context": "not similar enough to context"}}))

        # Mock get_embedding (in both places it is imported)
        fake_embedding = [0.1, 0.2, 0.3]
        mock_get_embedding_semantic_cache.return_value = fake_embedding
        mock_get_embedding_query_handler.return_value = fake_embedding

        # Mock search_semantic_cache (redis_store)
        # returning mocked doc
        mock_doc = Mock()
        large_diff = 0.5
        mock_doc.configure_mock(reply="test reply", section_headers_as_json="[]", query="original test query", vector_score=large_diff)  # <--- large diff = no hit
        self.mock_redis.search_semantic_cache.return_value = Mock(docs=[mock_doc])

        # Mock search_sections (redis_store)
        # returning No mocked section (none found)
        self.mock_redis.search_sections.return_value = None

        # call query handler
        response = handle_query("test query", self.mock_redis)
        # assert that we moved passed the semantic cache (no hit close enough)
        # and that we respond properly when we are unable to build a context with enough tokens
        assert (response["message"] == "not similar enough to context")
        assert (response["interaction_id"] is not None)

    @patch('server.query_handler.add_to_cache')
    @patch('server.query_handler.settings')
    @patch('server.query_handler.call_chat_completions')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_call_to_open_ai_raise_exception(self, mock_get_embedding_semantic_cache, mock_get_embedding_query_handler, mock_call_chat_completions, mock_settings, mock_add_to_cache):
        # Mock open ai response raising exception
        mock_call_chat_completions.side_effect = Exception("mocked exception")

        mock_settings.configure_mock(semantic_cache_enabled=False,
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score=0.9,
                                     get_locale=Mock(return_value={"server_texts": {"errors": {"something_went_wrong": "something_went_wrong"}}}))

        # Mock get_embedding (in both places it is imported)
        fake_embedding = [0.1, 0.2, 0.3]
        mock_get_embedding_semantic_cache.return_value = fake_embedding
        mock_get_embedding_query_handler.return_value = fake_embedding

        # Mock search_sections (redis_store)
        # returning mocked section with 2000 tokens and a very small diff (close hit)
        mock_section = Mock()
        very_small_diff = 1.54972076416e-06  # = 0.00000154972076416
        mock_section.configure_mock(header="test section header", body="b" * 2000, num_of_tokens="2000", vector_score=very_small_diff)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section])

        # call query handler
        response = handle_query("test query", self.mock_redis)

        expected_error_message_on_open_ai_exception = "something_went_wrong"
        assert (response["message"] == expected_error_message_on_open_ai_exception)

        # finally since semantic_cache_enabled is False we should have NOT called add_to_cache
        mock_add_to_cache.assert_not_called()

    @patch('server.query_handler.add_to_cache')
    @patch('server.query_handler.settings')
    @patch('server.query_handler.call_chat_completions')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_call_to_open_ai_timeout(self, mock_get_embedding_semantic_cache, mock_get_embedding_query_handler, mock_call_chat_completions, mock_settings, mock_add_to_cache):

        # Mock open ai response raising exception
        mock_call_chat_completions.side_effect = TimeoutError("open ai to slow today...")

        mock_settings.configure_mock(semantic_cache_enabled=False,
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score=0.9,
                                     get_locale=Mock(return_value={"server_texts": {"errors": {"openai_timeout": "OpenAI har väldigt långa svarstider just nu, var god försök igen senare.", "something_went_wrong": "something_went_wrong"}}}))

        # Mock get_embedding (in both places it is imported)
        fake_embedding = [0.1, 0.2, 0.3]
        mock_get_embedding_semantic_cache.return_value = fake_embedding
        mock_get_embedding_query_handler.return_value = fake_embedding

        # Mock search_sections (redis_store)
        # returning mocked section with 2000 tokens and a very small diff (close hit)
        mock_section = Mock()
        very_small_diff = 1.54972076416e-06  # = 0.00000154972076416
        mock_section.configure_mock(header="test section header", body="b" * 2000, num_of_tokens="2000", vector_score=very_small_diff)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section])

        # call query handler
        response = handle_query("test query", self.mock_redis)
        data = json.loads(response.body)

        expected_error_message_on_openai_timeout = "OpenAI har väldigt långa svarstider just nu, var god försök igen senare."
        assert (data["message"] == expected_error_message_on_openai_timeout)

        # finally since semantic_cache_enabled is False we should have NOT called add_to_cache
        mock_add_to_cache.assert_not_called()
