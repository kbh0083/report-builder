import unittest
import tempfile
import json
from pathlib import Path
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
        from report_engine.prompt_store import PromptStore
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

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_root = Path(tmpdir)
            _write_prompt_file(prompt_root, "02_components_system.txt", "Custom stage2 system: single JSON object with data-component-id.")
            _write_prompt_file(prompt_root, "03_layout_system.txt", "unused")
            NovitaLlmAdapter(settings, session=session, prompt_store=PromptStore(prompt_root)).generate_stage2_component(
                {
                    "componentId": "comp_x",
                    "componentKey": "review",
                }
            )

        system_message = session.last_payload["messages"][0]["content"]
        self.assertEqual(system_message, "Custom stage2 system: single JSON object with data-component-id.")
        self.assertIn("data-component-id", system_message)

    def test_stage3_prompt_requires_raw_html_and_document_local_css(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.prompt_store import PromptStore
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse("<!doctype html><html><head><style>body { margin: 0; }</style></head><body></body></html>"))
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

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_root = Path(tmpdir)
            _write_prompt_file(prompt_root, "02_components_system.txt", "unused")
            _write_prompt_file(
                prompt_root,
                "03_layout_system.txt",
                (
                    "Custom stage3 system: raw HTML only, <!doctype html>, document-local CSS in <style>, "
                    "normal document flow, position:absolute, template preview image, visual reference only. "
                    "Use supplied Stage 2 components as the only source for report data. "
                    "Do not render charts using SVG."
                ),
            )
            NovitaLlmAdapter(settings, session=session, prompt_store=PromptStore(prompt_root)).generate_stage3_layout({"components": []})

        system_message = session.last_payload["messages"][0]["content"]
        self.assertTrue(system_message.startswith("Custom stage3 system:"))
        self.assertIn("raw HTML only", system_message)
        self.assertIn("<!doctype html>", system_message)
        self.assertIn("normal document flow", system_message)
        self.assertIn("position:absolute", system_message)
        self.assertIn("template preview image", system_message)
        self.assertIn("visual reference only", system_message)
        self.assertIn("Use supplied Stage 2 components as the only source for report data", system_message)
        self.assertIn("document-local CSS", system_message)
        self.assertIn("<style>", system_message)
        self.assertIn("Do not render charts using SVG", system_message)
        self.assertNotIn("Do not create SVG", system_message)

    def test_missing_prompt_file_raises_config_invalid(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.prompt_store import PromptStore
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

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ReportEngineError) as caught:
                NovitaLlmAdapter(
                    settings,
                    session=FakeSession(FakeResponse("{}")),
                    prompt_store=PromptStore(Path(tmpdir)),
                ).generate_stage2_component({"componentKey": "review"})

        self.assertEqual(caught.exception.code, ErrorCode.CONFIG_INVALID)
        self.assertIn("02_components_system.txt", str(caught.exception))

    def test_empty_system_prompt_file_raises_config_invalid(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.prompt_store import PromptStore
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

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_root = Path(tmpdir)
            _write_prompt_file(prompt_root, "02_components_system.txt", "   \n")
            with self.assertRaises(ReportEngineError) as caught:
                NovitaLlmAdapter(
                    settings,
                    session=FakeSession(FakeResponse("{}")),
                    prompt_store=PromptStore(prompt_root),
                ).generate_stage2_component({"componentKey": "review"})

        self.assertEqual(caught.exception.code, ErrorCode.CONFIG_INVALID)
        self.assertIn("empty", str(caught.exception).lower())

    def test_stage3_sends_template_image_as_multimodal_content(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse("<!doctype html><html><head><style>body { margin: 0; }</style></head><body></body></html>"))
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

        NovitaLlmAdapter(settings, session=session).generate_stage3_layout(
            {"components": []},
            template_image_data_url="data:image/png;base64,dGVtcGxhdGU=",
        )

        user_content = session.last_payload["messages"][1]["content"]
        self.assertIsInstance(user_content, list)
        self.assertEqual(user_content[0]["type"], "text")
        self.assertIn("promptInput", user_content[0]["text"])
        self.assertEqual(user_content[1]["type"], "image_url")
        self.assertEqual(user_content[1]["image_url"]["url"], "data:image/png;base64,dGVtcGxhdGU=")

    def test_stage3_correction_prompt_can_include_template_image_payload(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse("<!doctype html><html><head><style>body { margin: 0; }</style></head><body></body></html>"))
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
        image_data_url = "data:image/png;base64,dGVtcGxhdGU="

        NovitaLlmAdapter(settings, session=session).generate_stage3_layout(
            {
                "components": [],
                "correction": {
                    "attempt": 1,
                    "previousError": "LAYOUT_GENERATION_INVALID: missing CSS",
                    "requirements": ["Return a corrected single HTML document."],
                    "rejectedHtml": "<!doctype html><html><body>bad</body></html>",
                },
            },
            template_image_data_url=image_data_url,
        )

        user_content = session.last_payload["messages"][1]["content"]
        self.assertIsInstance(user_content, list)
        text_payload = json.loads(user_content[0]["text"])
        self.assertEqual(text_payload["promptInput"]["correction"]["attempt"], 1)
        self.assertIn("LAYOUT_GENERATION_INVALID", text_payload["promptInput"]["correction"]["previousError"])
        self.assertIn("rejectedHtml", text_payload["promptInput"]["correction"])
        self.assertEqual(user_content[1]["image_url"]["url"], image_data_url)

    def test_logs_stage3_image_metadata_without_base64_payload(self):
        from report_engine.artifact_logger import ArtifactLogger
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.llm_call_logger import LlmCallLogger
        from report_engine.settings import LlmSettings

        image_data_url = "data:image/png;base64,dGVtcGxhdGU="
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_logger = ArtifactLogger(tmpdir, "job_test", secrets=["secret-key-123"])
            llm_call_logger = LlmCallLogger(artifact_logger)
            session = FakeSession(FakeResponse("<!doctype html><html><head><style>body { margin: 0; }</style></head><body></body></html>"))
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

            NovitaLlmAdapter(settings, session=session, llm_call_logger=llm_call_logger).generate_stage3_layout(
                {"components": []},
                template_image_data_url=image_data_url,
            )

            log_files = sorted((Path(tmpdir) / "job_test" / "03_layout" / "llm_calls").glob("*.json"))
            self.assertEqual(len(log_files), 1)
            payload = json.loads(log_files[0].read_text(encoding="utf-8"))

        combined = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(image_data_url, combined)
        self.assertNotIn("dGVtcGxhdGU=", combined)
        self.assertEqual(payload["request"]["messages"][1]["content"][1]["image_url"]["url"], "<image data redacted>")
        self.assertEqual(payload["request"]["messages"][1]["content"][1]["image_url"]["mimeType"], "image/png")
        self.assertEqual(payload["request"]["messages"][1]["content"][1]["image_url"]["base64Bytes"], 8)

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

    def test_logs_prompt_response_token_usage_and_duration(self):
        from report_engine.artifact_logger import ArtifactLogger
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.llm_call_logger import LlmCallLogger
        from report_engine.settings import LlmSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_logger = ArtifactLogger(tmpdir, "job_test", secrets=["secret-key-123"])
            llm_call_logger = LlmCallLogger(artifact_logger)
            session = FakeSession(
                FakeResponse(
                    '{"html": "<section data-component-id=\\"x\\"></section>", "chartSpec": null, "styled": false}',
                    usage={"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
                )
            )
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

            NovitaLlmAdapter(settings, session=session, llm_call_logger=llm_call_logger).generate_stage2_component(
                {
                    "componentId": "x",
                    "componentKey": "review",
                }
            )

            log_files = sorted((Path(tmpdir) / "job_test" / "02_components" / "llm_calls").glob("*.json"))
            self.assertEqual(len(log_files), 1)
            payload = json.loads(log_files[0].read_text(encoding="utf-8"))

        self.assertEqual(payload["stage"], "02_components")
        self.assertEqual(payload["task"], "stage2_component")
        self.assertEqual(payload["status"], "completed")
        self.assertGreaterEqual(payload["durationMs"], 0)
        self.assertEqual(payload["tokenUsage"], {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18})
        self.assertIn("messages", payload["request"])
        self.assertIn("single JSON object", payload["request"]["messages"][0]["content"])
        self.assertEqual(payload["response"]["content"], '{"html": "<section data-component-id=\\"x\\"></section>", "chartSpec": null, "styled": false}')
        combined = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("secret-key-123", combined)
        self.assertNotIn("Authorization", combined)
        self.assertNotIn("apiKey", combined)

    def test_logs_failed_invalid_json_with_prompt_and_error_metadata(self):
        from report_engine.artifact_logger import ArtifactLogger
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.llm_call_logger import LlmCallLogger
        from report_engine.settings import LlmSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_logger = ArtifactLogger(tmpdir, "job_test", secrets=["secret-key-123"])
            llm_call_logger = LlmCallLogger(artifact_logger)
            session = FakeSession(FakeResponse("not json"))
            settings = LlmSettings(
                model="qwen/test",
                baseUrl="https://api.novita.ai/openai",
                apiKey="secret-key-123",
                temperature=0.0,
                maxTokens=4096,
                timeoutSeconds=120,
                chunkSizeChars=12000,
                stageBatchSize=12,
                parseRetryAttempts=0,
            )

            with self.assertRaises(ReportEngineError) as caught:
                NovitaLlmAdapter(settings, session=session, llm_call_logger=llm_call_logger).generate_stage2_component(
                    {
                        "componentId": "x",
                        "componentKey": "review",
                    }
                )

            log_files = sorted((Path(tmpdir) / "job_test" / "02_components" / "llm_calls").glob("*.json"))
            self.assertEqual(len(log_files), 1)
            payload = json.loads(log_files[0].read_text(encoding="utf-8"))

        self.assertEqual(caught.exception.code, ErrorCode.LLM_INVALID_JSON)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["error"]["errorCode"], "LLM_INVALID_JSON")
        self.assertEqual(payload["error"]["errorType"], "ReportEngineError")
        self.assertGreaterEqual(payload["durationMs"], 0)
        self.assertIn("messages", payload["request"])
        self.assertEqual(payload["response"]["content"], "not json")

    def test_logs_raw_response_body_when_response_envelope_is_invalid(self):
        from report_engine.artifact_logger import ArtifactLogger
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.llm_call_logger import LlmCallLogger
        from report_engine.settings import LlmSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_logger = ArtifactLogger(tmpdir, "job_test", secrets=["secret-key-123"])
            llm_call_logger = LlmCallLogger(artifact_logger)
            settings = LlmSettings(
                model="qwen/test",
                baseUrl="https://api.novita.ai/openai",
                apiKey="secret-key-123",
                temperature=0.0,
                maxTokens=4096,
                timeoutSeconds=120,
                chunkSizeChars=12000,
                stageBatchSize=12,
                retryAttempts=0,
            )

            with self.assertRaises(ReportEngineError) as caught:
                NovitaLlmAdapter(
                    settings,
                    session=FakeSession(InvalidEnvelopeResponse("raw envelope output")),
                    llm_call_logger=llm_call_logger,
                ).generate_stage3_layout({"components": []})

            log_files = sorted((Path(tmpdir) / "job_test" / "03_layout" / "llm_calls").glob("*.json"))
            self.assertEqual(len(log_files), 1)
            payload = json.loads(log_files[0].read_text(encoding="utf-8"))

        self.assertEqual(caught.exception.code, ErrorCode.LLM_INVALID_JSON)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["error"]["errorCode"], "LLM_INVALID_JSON")
        self.assertEqual(payload["response"]["content"], "raw envelope output")


class FakeResponse:
    def __init__(self, content, status_code=200, usage=None, finish_reason="stop"):
        self.content = content
        self.status_code = status_code
        self.text = content
        self.usage = usage
        self.finish_reason = finish_reason

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")
        return None

    def json(self):
        payload = {"choices": [{"message": {"content": self.content}, "finish_reason": self.finish_reason}]}
        if self.usage is not None:
            payload["usage"] = self.usage
        return payload


class InvalidEnvelopeResponse:
    def __init__(self, text):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"unexpected": "shape"}


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


def _write_prompt_file(prompt_root: Path, filename: str, content: str) -> None:
    prompt_root.mkdir(parents=True, exist_ok=True)
    (prompt_root / filename).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
