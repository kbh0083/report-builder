import unittest
from unittest.mock import patch


class NovitaLlmAdapterTests(unittest.TestCase):
    def test_posts_openai_compatible_request_without_streaming(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse('{"html": "<section data-component-id=\\"x\\"></section>", "chartSpec": null, "styled": false}'))
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        result = NovitaLlmAdapter(settings, session=session).generate_stage2_component({"componentKey": "review"})

        self.assertEqual(result["styled"], False)
        self.assertEqual(session.last_url, "https://api.novita.ai/openai/v1/chat/completions")
        self.assertEqual(session.last_headers["Authorization"], "Bearer secret-key-123")
        self.assertEqual(session.last_payload["model"], "qwen/test")
        self.assertEqual(session.last_payload["temperature"], 0.0)
        self.assertEqual(session.last_payload["top_p"], 1.0)
        self.assertEqual(session.last_payload["max_tokens"], 4096)
        self.assertEqual(session.last_payload["stream"], False)
        self.assertEqual(session.last_payload["enable_thinking"], False)
        self.assertEqual(session.last_payload["separate_reasoning"], True)
        self.assertEqual(session.last_timeout, 120)

    def test_retries_timeout_then_returns_success(self):
        import requests

        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = SequenceSession([
            requests.exceptions.ReadTimeout("secret-key-123"),
            FakeResponse('{"html": "<section data-component-id=\\"x\\"></section>", "chartSpec": null, "styled": false}'),
        ])
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        result = NovitaLlmAdapter(settings, session=session).generate_stage2_component({"componentKey": "review"})

        self.assertEqual(result["html"], '<section data-component-id="x"></section>')
        self.assertEqual(session.post_count, 2)

    def test_retries_http_429_then_returns_success(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = SequenceSession([
            FakeResponse('{"error": "rate limited"}', status_code=429),
            FakeResponse('{"html": "<section data-component-id=\\"x\\"></section>", "chartSpec": null, "styled": false}'),
        ])
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        result = NovitaLlmAdapter(settings, session=session).generate_stage2_component({"componentKey": "review"})

        self.assertEqual(result["html"], '<section data-component-id="x"></section>')
        self.assertEqual(session.post_count, 2)

    def test_timeout_error_does_not_include_api_key(self):
        import requests

        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        with self.assertRaises(ReportEngineError) as caught:
            NovitaLlmAdapter(settings, session=RaisingSession(requests.exceptions.Timeout("secret-key-123"))).generate_stage2_component({})

        self.assertEqual(caught.exception.code, ErrorCode.LLM_TIMEOUT)
        self.assertNotIn("secret-key-123", str(caught.exception))

    def test_invalid_json_error_does_not_include_api_key(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        with self.assertRaises(ReportEngineError) as caught:
            NovitaLlmAdapter(settings, session=FakeSession(FakeResponse("not json"))).generate_stage2_component({})

        self.assertEqual(caught.exception.code, ErrorCode.LLM_INVALID_JSON)
        self.assertNotIn("secret-key-123", str(caught.exception))

    def test_stage2_accepts_single_object_wrapped_in_array(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse('[{"html": "<section data-component-id=\\"x\\"></section>", "chartSpec": null, "styled": false}]'))
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        result = NovitaLlmAdapter(settings, session=session).generate_stage2_component({"componentKey": "review"})

        self.assertEqual(result["html"], '<section data-component-id="x"></section>')
        self.assertEqual(result["styled"], False)

    def test_stage2_accepts_markdown_fenced_json_object(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse('```json\n{"html": "<section data-component-id=\\"x\\"></section>", "chartSpec": null, "styled": false}\n```'))
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        result = NovitaLlmAdapter(settings, session=session).generate_stage2_component({"componentKey": "review"})

        self.assertEqual(result["html"], '<section data-component-id="x"></section>')
        self.assertEqual(result["chartSpec"], None)

    def test_stage2_accepts_double_encoded_json_object(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse('"{\\"html\\": \\"<section data-component-id=\\\\\\"x\\\\\\"></section>\\", \\"chartSpec\\": null, \\"styled\\": false}"'))
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        result = NovitaLlmAdapter(settings, session=session).generate_stage2_component({"componentKey": "review"})

        self.assertEqual(result["html"], '<section data-component-id="x"></section>')
        self.assertEqual(result["styled"], False)

    def test_stage2_accepts_json_string_with_embedded_object(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse(
            '"Here is the JSON object:\\n{\\"html\\": \\"<section data-component-id=\\\\\\"x\\\\\\"></section>\\", \\"chartSpec\\": null, \\"styled\\": false}"'
        ))
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        result = NovitaLlmAdapter(settings, session=session).generate_stage2_component({"componentKey": "review"})

        self.assertEqual(result["html"], '<section data-component-id="x"></section>')
        self.assertEqual(result["chartSpec"], None)

    def test_stage2_accepts_array_with_single_html_object_and_note_object(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse(
            '[{"note": "generated component"}, {"html": "<section data-component-id=\\"x\\"></section>", "chartSpec": null, "styled": false}]'
        ))
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        result = NovitaLlmAdapter(settings, session=session).generate_stage2_component({"componentKey": "review"})

        self.assertEqual(result["html"], '<section data-component-id="x"></section>')
        self.assertEqual(result["styled"], False)

    def test_stage2_retries_invalid_json_then_accepts_valid_json(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = SequenceSession([
            FakeResponse("not json"),
            FakeResponse('{"html": "<section data-component-id=\\"x\\"></section>", "chartSpec": null, "styled": false}'),
        ])
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        result = NovitaLlmAdapter(settings, session=session).generate_stage2_component({"componentKey": "review"})

        self.assertEqual(result["html"], '<section data-component-id="x"></section>')
        self.assertEqual(session.post_count, 2)

    def test_stage2_prompt_requires_one_json_object(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse('{"html": "<section data-component-id=\\"x\\"></section>", "chartSpec": null, "styled": false}'))
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        NovitaLlmAdapter(settings, session=session).generate_stage2_component(
            {
                "componentId": "comp_x",
                "componentKey": "review",
            }
        )

        system_message = session.last_payload["messages"][0]["content"]
        self.assertIn("single JSON object", system_message)
        self.assertIn("Do not return an array", system_message)
        self.assertIn("data-component-id", system_message)

    def test_stage3_prompt_requires_raw_html_only(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse("<!doctype html><html><body></body></html>"))
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        NovitaLlmAdapter(settings, session=session).generate_stage3_layout({"components": []})

        system_message = session.last_payload["messages"][0]["content"]
        self.assertIn("raw HTML only", system_message)
        self.assertIn("Do not wrap", system_message)
        self.assertIn("<!doctype html>", system_message)
        self.assertIn("normal document flow", system_message)
        self.assertIn("position:absolute", system_message)

    def test_default_adapter_uses_fresh_session_per_request_for_parallel_safety(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        sessions = [
            FakeSession(FakeResponse('{"html": "<section data-component-id=\\"x\\"></section>", "chartSpec": null, "styled": false}')),
            FakeSession(FakeResponse('{"html": "<section data-component-id=\\"y\\"></section>", "chartSpec": null, "styled": false}')),
        ]
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=12,
        )

        with patch("report_engine.llm.requests.Session", side_effect=sessions) as session_factory:
            adapter = NovitaLlmAdapter(settings)
            adapter.generate_stage2_component({"componentKey": "review"})
            adapter.generate_stage2_component({"componentKey": "outlook"})

        self.assertEqual(session_factory.call_count, 2)
        self.assertTrue(all(session.closed for session in sessions))


class FakeResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code
        self.text = content

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")
        return None

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.closed = False

    def post(self, url, headers, json, timeout):
        self.last_url = url
        self.last_headers = headers
        self.last_payload = json
        self.last_timeout = timeout
        return self.response

    def close(self):
        self.closed = True


class SequenceSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.post_count = 0

    def post(self, url, headers, json, timeout):
        self.post_count += 1
        self.last_url = url
        self.last_headers = headers
        self.last_payload = json
        self.last_timeout = timeout
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class RaisingSession:
    def __init__(self, exception):
        self.exception = exception

    def post(self, url, headers, json, timeout):
        raise self.exception


if __name__ == "__main__":
    unittest.main()
