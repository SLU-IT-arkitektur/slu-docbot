import json
import logging
import unittest
from unittest.mock import Mock, patch
from server.query_handler import handle_query


class TestHandleQuery(unittest.TestCase):

    def setUp(self):
        print(f'{__name__} :: {self._testMethodName}')
        # Create a mock RedisStore
        self.mock_redis = Mock()
    
        # mute all logging
        logging.getLogger().disabled = True

    def test_empty_query(self):
        response = handle_query("", self.mock_redis)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.body, b'{"message":"Please enter a query"}')

    def test_query_more_than_80_chars(self):
        response = handle_query("a" * 81, self.mock_redis)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.body, b'{"message":"Max 80 tecken"}')

    @patch('server.query_handler.settings')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_cache_hit(self, mock_get_embedding_semantic_cache,mock_get_embedding_query_handler, mock_settings):
        # Configure the mock settings to enable semantic cache
        mock_settings.configure_mock(semantic_cache_enabled=True)

        # Mock get_embedding (in both places it is imported)
        # returning mocked embedding
        mock_get_embedding_semantic_cache.return_value = [0.1, 0.2, 0.3]
        mock_get_embedding_query_handler.return_value = [0.1, 0.2, 0.3]

        # Mock search_semantic_cache (redis_store)
        mock_doc = Mock()
        very_small_diff = 1.54972076416e-06 # = 0.00000154972076416
        mock_doc.configure_mock(reply="test reply", section_headers_as_json="[]", query="original test query", vector_score=very_small_diff)
        self.mock_redis.search_semantic_cache.return_value = Mock(docs=[mock_doc])

        response = handle_query("test query", self.mock_redis)

        self.assertEqual(response["message"], "test reply")
        self.assertEqual(response["from_cache"], "true")
        self.assertEqual(response["sectionHeaders"], [])
        self.assertEqual(response["original_query"], "original test query")
        
    
    @patch('server.query_handler.add_to_cache')
    @patch('server.query_handler.settings')
    @patch('server.query_handler.call_chat_completions')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_call_to_open_ai(self,mock_get_embedding_semantic_cache,mock_get_embedding_query_handler, mock_call_chat_completions, mock_settings, mock_add_to_cache):
        
        # Mock open ai response
        # returning mocked_open_ai_response
        mocked_open_ai_response = {
            "choices": [
                {
                    "message": {
                        "content": "mocked open ai response"
                    }
                }
            ]
        }
        mock_call_chat_completions.return_value = mocked_open_ai_response
        # Configure the mock settings to enable semantic cache, prompt instructions and min similarity score
        mock_settings.configure_mock(semantic_cache_enabled=True, 
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score = 0.9)
        
        # Mock get_embedding (in both places it is imported)
        # returning mocked embedding
        mock_get_embedding_semantic_cache.return_value = [0.1, 0.2, 0.3]
        mock_get_embedding_query_handler.return_value = [0.1, 0.2, 0.3]

        # Mock search_semantic_cache (redis_store)
        # returning mocked doc
        mock_doc = Mock()
        large_diff = 0.5 
        mock_doc.configure_mock(reply="test reply", section_headers_as_json="[]", query="original test query", vector_score=large_diff)
        self.mock_redis.search_semantic_cache.return_value = Mock(docs=[mock_doc])

        # Mock search_sections (redis_store)
        # returning mocked section with 2000 tokens and a very small diff (close hit)
        mock_section = Mock()
        very_small_diff = 1.54972076416e-06 # = 0.00000154972076416
        mock_section.configure_mock(header="test section header", body="b" * 2000, num_of_tokens="2000", vector_score=very_small_diff)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section])

        # call query handler
        response = handle_query("test query", self.mock_redis)

        # assert that we moved passed the semantic cache (no hit close enought)
        # and that we were able to build a context and send a request to open ai
        # and that we got a response from the open ai client
        assert(response["message"] == "mocked open ai response")
        assert(response["sectionHeaders"] == ['test section header'])
        assert(response["interaction_id"] is not None)

        # finally since semantic_cache_enabled is true we should have called add_to_cache
        mock_add_to_cache.assert_called_with("test query", "mocked open ai response", json.dumps(['test section header']), self.mock_redis)


    @patch('server.query_handler.add_to_cache')
    @patch('server.query_handler.settings')
    @patch('server.query_handler.call_chat_completions')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_call_to_open_ai_without_semantic_cache(self,mock_get_embedding_semantic_cache,mock_get_embedding_query_handler, mock_call_chat_completions, mock_settings, mock_add_to_cache):
        
        # Mock open ai response
        # returning mocked_open_ai_response
        mocked_open_ai_response = {
            "choices": [
                {
                    "message": {
                        "content": "mocked open ai response"
                    }
                }
            ]
        }
        mock_call_chat_completions.return_value = mocked_open_ai_response
        # Configure the mock settings to enable semantic cache, prompt instructions and min similarity score

        mock_settings.configure_mock(semantic_cache_enabled=False,  # <--- disabling semantic cache
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score = 0.9)
        
        # Mock get_embedding (in both places it is imported)
        # returning mocked embedding
        mock_get_embedding_semantic_cache.return_value = [0.1, 0.2, 0.3]
        mock_get_embedding_query_handler.return_value = [0.1, 0.2, 0.3]

        # Mock search_sections (redis_store)
        # returning mocked section with 2000 tokens and a very small diff (close hit)
        mock_section = Mock()
        very_small_diff = 1.54972076416e-06 # = 0.00000154972076416
        mock_section.configure_mock(header="test section header", body="b" * 2000, num_of_tokens="2000", vector_score=very_small_diff)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section])

        # call query handler
        response = handle_query("test query", self.mock_redis)

        # assert that we moved passed the semantic cache (no hit close enought)
        # and that we were able to build a context and send a request to open ai
        # and that we got a response from the open ai client
        assert(response["message"] == "mocked open ai response")
        assert(response["sectionHeaders"] == ['test section header'])
        assert(response["interaction_id"] is not None)



        # finally since semantic_cache_enabled is False we should not have called add_to_cache or redis.search_semantic_cache
        mock_add_to_cache.assert_not_called()
        self.mock_redis.search_semantic_cache.assert_not_called()


    @patch('server.query_handler.settings')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_not_enough_context(self, mock_get_embedding_semantic_cache,mock_get_embedding_query_handler, mock_settings):
        # Configure the mock settings to enable semantic cache, prompt instructions and min similarity score
        mock_settings.configure_mock(semantic_cache_enabled=True, 
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score = 0.9)
        
        # Mock get_embedding (in both places it is imported)
        # returning mocked embedding
        mock_get_embedding_semantic_cache.return_value = [0.1, 0.2, 0.3]
        mock_get_embedding_query_handler.return_value = [0.1, 0.2, 0.3]


        # Mock search_semantic_cache (redis_store)
        # returning mocked doc
        mock_doc = Mock()
        large_diff = 0.5 
        mock_doc.configure_mock(reply="test reply", section_headers_as_json="[]", query="original test query", vector_score=large_diff)
        self.mock_redis.search_semantic_cache.return_value = Mock(docs=[mock_doc])

        # Mock search_sections (redis_store)
        # returning mocked section with 2000 tokens and a very small diff (close hit)
        # BUT to small a context... num_of_tokens..
        mock_section = Mock()
        very_small_diff = 1.54972076416e-06 # = 0.00000154972076416
        mock_section.configure_mock(header="test section header", body="bb", num_of_tokens="2", vector_score=very_small_diff)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section])

        # call query handler
        response = handle_query("test query", self.mock_redis)

        # assert that we moved passed the semantic cache (no hit close enough)
        # and that we response properly when we are unable to build a context (to small section)
        assert(response["message"] == "Jag hittar inget svar på din fråga i Utbildningshandboken")
        assert(response["interaction_id"] is not None)



    @patch('server.query_handler.settings')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_no_relevant_sections(self,mock_get_embedding_semantic_cache,mock_get_embedding_query_handler, mock_settings):
        # Configure the mock settings to enable semantic cache, prompt instructions and min similarity score
        mock_settings.configure_mock(semantic_cache_enabled=True, 
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score = 0.9)
        
        # Mock get_embedding (in both places it is imported)
        # returning mocked embedding
        mock_get_embedding_semantic_cache.return_value = [0.1, 0.2, 0.3]
        mock_get_embedding_query_handler.return_value = [0.1, 0.2, 0.3]


        # Mock search_semantic_cache (redis_store)
        # returning mocked doc
        mock_doc = Mock()
        large_diff = 0.5 
        mock_doc.configure_mock(reply="test reply", section_headers_as_json="[]", query="original test query", vector_score=large_diff)
        self.mock_redis.search_semantic_cache.return_value = Mock(docs=[mock_doc])

        # Mock search_sections (redis_store)
        # returning No mocked section (none found)
        self.mock_redis.search_sections.return_value = None

        # call query handler
        response = handle_query("test query", self.mock_redis)

        # assert that we moved passed the semantic cache (no hit close enough)
        # and that we response properly when we are unable to build a context (to small section)
        assert(response["message"] == "Jag hittar inget svar på din fråga i Utbildningshandboken")
        assert(response["interaction_id"] is not None)


    @patch('server.query_handler.add_to_cache')
    @patch('server.query_handler.settings')
    @patch('server.query_handler.call_chat_completions')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_call_to_open_ai_raise_exception(self,mock_get_embedding_semantic_cache,mock_get_embedding_query_handler, mock_call_chat_completions, mock_settings, mock_add_to_cache):
        
        # Mock open ai response raising exception
        mock_call_chat_completions.side_effect = Exception("mocked exception")

        # Configure the mock settings to enable semantic cache, prompt instructions and min similarity score
        mock_settings.configure_mock(semantic_cache_enabled=True, 
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score = 0.9)
        
        # Mock get_embedding (in both places it is imported)
        # returning mocked embedding
        mock_get_embedding_semantic_cache.return_value = [0.1, 0.2, 0.3]
        mock_get_embedding_query_handler.return_value = [0.1, 0.2, 0.3]

        # Mock search_semantic_cache (redis_store)
        # returning mocked doc
        mock_doc = Mock()
        large_diff = 0.5 
        mock_doc.configure_mock(reply="test reply", section_headers_as_json="[]", query="original test query", vector_score=large_diff)
        self.mock_redis.search_semantic_cache.return_value = Mock(docs=[mock_doc])

        # Mock search_sections (redis_store)
        # returning mocked section with 2000 tokens and a very small diff (close hit)
        mock_section = Mock()
        very_small_diff = 1.54972076416e-06 # = 0.00000154972076416
        mock_section.configure_mock(header="test section header", body="b" * 2000, num_of_tokens="2000", vector_score=very_small_diff)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section])

        # call query handler
        response = handle_query("test query", self.mock_redis)

        # assert that we moved passed the semantic cache (no hit close enought)
        # and that we were able to build a context and send a request to open ai
        # and that we got a response from the open ai client
        assert(response["message"] == "Något gick fel :(")
      
        # finally since semantic_cache_enabled is true we should have called add_to_cache
        mock_add_to_cache.assert_not_called()

    @patch('server.query_handler.add_to_cache')
    @patch('server.query_handler.settings')
    @patch('server.query_handler.call_chat_completions')
    @patch('server.query_handler.get_embedding')
    @patch('server.semantic_cache.get_embedding')
    def test_call_to_open_ai_timeout(self,mock_get_embedding_semantic_cache,mock_get_embedding_query_handler, mock_call_chat_completions, mock_settings, mock_add_to_cache):
        
        # Mock open ai response raising exception
        mock_call_chat_completions.side_effect = TimeoutError("open ai to slow today...")

        # Configure the mock settings to enable semantic cache, prompt instructions and min similarity score
        mock_settings.configure_mock(semantic_cache_enabled=True, 
                                     prompt_instructions="test prompt instructions",
                                     sections_min_similarity_score = 0.9)
        
        # Mock get_embedding (in both places it is imported)
        # returning mocked embedding
        mock_get_embedding_semantic_cache.return_value = [0.1, 0.2, 0.3]
        mock_get_embedding_query_handler.return_value = [0.1, 0.2, 0.3]

        # Mock search_semantic_cache (redis_store)
        # returning mocked doc
        mock_doc = Mock()
        large_diff = 0.5 
        mock_doc.configure_mock(reply="test reply", section_headers_as_json="[]", query="original test query", vector_score=large_diff)
        self.mock_redis.search_semantic_cache.return_value = Mock(docs=[mock_doc])

        # Mock search_sections (redis_store)
        # returning mocked section with 2000 tokens and a very small diff (close hit)
        mock_section = Mock()
        very_small_diff = 1.54972076416e-06 # = 0.00000154972076416
        mock_section.configure_mock(header="test section header", body="b" * 2000, num_of_tokens="2000", vector_score=very_small_diff)
        self.mock_redis.search_sections.return_value = Mock(docs=[mock_section])

        # call query handler
        response = handle_query("test query", self.mock_redis)
        data = json.loads(response.body)
        # assert that we moved passed the semantic cache (no hit close enought)
        # and that we were able to build a context and send a request to open ai
        # and that we got a response from the open ai client
        assert(data["message"] == "OpenAI har väldigt långa svarstider just nu, var god försök igen senare.")
      
        # finally since semantic_cache_enabled is true we should have called add_to_cache
        mock_add_to_cache.assert_not_called()