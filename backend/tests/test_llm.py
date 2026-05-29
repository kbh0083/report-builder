import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch


class NovitaLlmAdapterTests(unittest.TestCase):
    def test_default_stage5_requirements_reject_template_layout_and_chart_mismatch(self):
        from report_engine.prompt_store import PromptStore

        prompt_store = PromptStore()
        system_prompt = prompt_store.read_text("05_verification_system.txt").lower()
        requirements = prompt_store.read_json("05_verification_requirements.json")

        combined = " ".join(requirements).lower()
        self.assertIn("template preview image", combined)
        self.assertIn("section placement", combined)
        self.assertIn("chart type", combined)
        self.assertIn("header", combined)
        self.assertIn("footer", combined)
        self.assertIn("logo", combined)
        self.assertIn("only authoritative data source", combined)
        self.assertIn("do not copy or require template preview text", combined)
        self.assertIn("section labels", combined)
        self.assertIn("sample table content", combined)
        self.assertIn("do not request removal of supplied stage 2 components", combined)
        self.assertIn("issue-scoped revisioninstruction", combined)
        self.assertIn("do not request a full html rewrite", combined)
        self.assertIn("layout, style, visual hierarchy", combined)
        self.assertIn("stage 2/html versus generated preview", combined)
        self.assertIn("visual structure or style", system_prompt)
        self.assertIn("sample content", system_prompt)
        self.assertIn("must not require", system_prompt)
        self.assertNotIn("do not fail solely because chart type", combined)

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

    def test_stage5_verification_sends_preview_image_and_html_as_multimodal_json(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.models import PageSettings, ReportVersion, TemplateContext, TemplateRevisionProfile
        from report_engine.prompt_store import PromptStore
        from report_engine.settings import LlmSettings

        session = FakeSession(FakeResponse('{"passed": true, "issues": []}'))
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
            root = Path(tmpdir)
            _write_prompt_file(root, "05_verification_system.txt", "# ko: 검증 지시\nReturn one JSON object.")
            _write_prompt_file(root, "05_verification_requirements.json", '// ko: 검증 요구사항\n["Check overlap."]\n')
            html_path = root / "report.html"
            preview_path = root / "preview.png"
            template_path = root / "template.png"
            html_path.write_text("<!doctype html><html><body><h1>Report</h1></body></html>", encoding="utf-8")
            preview_path.write_bytes(b"preview-bytes")
            template_path.write_bytes(b"template-bytes")
            version = ReportVersion(
                jobId="job_stage5",
                version=1,
                htmlPath=str(html_path),
                previewImagePath=str(preview_path),
                status="verifying",
                createdAt="2026-05-28T00:00:00+09:00",
            )
            template_context = TemplateContext(
                templateId="tpl_kb_monthly_guidebook",
                previewImage=str(template_path),
                page=PageSettings(size="A4", orientation="portrait"),
                name="국민은행 월간 가이드북",
            )

            result = NovitaLlmAdapter(
                settings,
                session=session,
                prompt_store=PromptStore(root),
            ).verify_report_version(version, template_context=template_context)

        self.assertEqual(result, {"passed": True, "issues": []})
        self.assertEqual(session.last_payload["response_format"], {"type": "json_object"})
        self.assertEqual(session.last_payload["messages"][0]["content"], "Return one JSON object.")
        user_content = session.last_payload["messages"][1]["content"]
        self.assertIsInstance(user_content, list)
        text_payload = json.loads(user_content[0]["text"])
        self.assertEqual(text_payload["task"], "stage5_verification")
        self.assertEqual(text_payload["reportVersion"]["jobId"], "job_stage5")
        self.assertEqual(text_payload["reportVersion"]["version"], 1)
        self.assertEqual(text_payload["template"]["templateId"], "tpl_kb_monthly_guidebook")
        self.assertEqual(text_payload["template"]["previewImage"], str(template_path))
        self.assertEqual(text_payload["reportHtml"], "<!doctype html><html><body><h1>Report</h1></body></html>")
        self.assertEqual(text_payload["requirements"], ["Check overlap."])
        self.assertEqual(user_content[1]["type"], "image_url")
        self.assertEqual(user_content[1]["label"], "generatedPreviewImage")
        self.assertTrue(user_content[1]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertEqual(user_content[2]["type"], "image_url")
        self.assertEqual(user_content[2]["label"], "templatePreviewImage")
        self.assertTrue(user_content[2]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_stage5_verification_retries_invalid_json_then_accepts_valid_result(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.models import ReportVersion
        from report_engine.prompt_store import PromptStore
        from report_engine.settings import LlmSettings

        session = SequenceSession([
            FakeResponse("not json"),
            FakeResponse(
                '{"passed": false, "issues": [{"type": "overlap", "severity": "major", "description": "Footer overlaps text."}], "revisionInstruction": "Increase bottom safe area."}'
            ),
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
            parseRetryAttempts=1,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_prompt_file(root, "05_verification_system.txt", "# ko: 검증 지시\nReturn one JSON object.")
            _write_prompt_file(root, "05_verification_requirements.json", '// ko: 검증 요구사항\n["Check overlap."]\n')
            html_path = root / "report.html"
            preview_path = root / "preview.png"
            html_path.write_text("<!doctype html><html><body>Report</body></html>", encoding="utf-8")
            preview_path.write_bytes(b"preview-bytes")
            version = ReportVersion(
                jobId="job_stage5",
                version=1,
                htmlPath=str(html_path),
                previewImagePath=str(preview_path),
                status="verifying",
                createdAt="2026-05-28T00:00:00+09:00",
            )

            result = NovitaLlmAdapter(
                settings,
                session=session,
                prompt_store=PromptStore(root),
            ).verify_report_version(version)

        self.assertEqual(session.post_count, 2)
        self.assertFalse(result["passed"])
        self.assertEqual(result["issues"][0]["type"], "overlap")
        self.assertEqual(result["revisionInstruction"], "Increase bottom safe area.")

    def test_stage5_verification_rejects_issue_without_required_schema_fields(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.models import ReportVersion
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
            parseRetryAttempts=0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_prompt_file(root, "05_verification_system.txt", "# ko: 검증 지시\nReturn one JSON object.")
            _write_prompt_file(root, "05_verification_requirements.json", '// ko: 검증 요구사항\n["Check overlap."]\n')
            html_path = root / "report.html"
            preview_path = root / "preview.png"
            html_path.write_text("<!doctype html><html><body>Report</body></html>", encoding="utf-8")
            preview_path.write_bytes(b"preview-bytes")
            version = ReportVersion(
                jobId="job_stage5",
                version=1,
                htmlPath=str(html_path),
                previewImagePath=str(preview_path),
                status="verifying",
                createdAt="2026-05-28T00:00:00+09:00",
            )

            with self.assertRaises(ReportEngineError) as caught:
                NovitaLlmAdapter(
                    settings,
                    session=FakeSession(FakeResponse('{"passed": false, "issues": [{"code": "overlap"}]}')),
                    prompt_store=PromptStore(root),
                ).verify_report_version(version)

        self.assertEqual(caught.exception.code, ErrorCode.LLM_INVALID_JSON)
        self.assertIn("missing required fields", str(caught.exception))

    def test_logs_stage5_image_metadata_without_base64_payload(self):
        from report_engine.artifact_logger import ArtifactLogger
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.llm_call_logger import LlmCallLogger
        from report_engine.models import PageSettings, ReportVersion, TemplateContext, TemplateRevisionProfile
        from report_engine.prompt_store import PromptStore
        from report_engine.settings import LlmSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_prompt_file(root, "05_verification_system.txt", "# ko: 검증 지시\nReturn one JSON object.")
            _write_prompt_file(root, "05_verification_requirements.json", '// ko: 검증 요구사항\n["Check overlap."]\n')
            html_path = root / "report.html"
            preview_path = root / "preview.png"
            template_path = root / "template.png"
            html_path.write_text("<!doctype html><html><body>Report</body></html>", encoding="utf-8")
            preview_path.write_bytes(b"preview-bytes")
            template_path.write_bytes(b"template-bytes")
            version = ReportVersion(
                jobId="job_stage5",
                version=1,
                htmlPath=str(html_path),
                previewImagePath=str(preview_path),
                status="verifying",
                createdAt="2026-05-28T00:00:00+09:00",
            )
            template_context = TemplateContext(
                templateId="tpl_woori_monthly_report",
                previewImage=str(template_path),
                page=PageSettings(size="A4", orientation="portrait"),
                revisionProfile=TemplateRevisionProfile(
                    revisionMode="minimal_patch",
                    preserveInitialGrid=True,
                    maxPreviewDimensionDriftRatio=0.15,
                    allowedRevisionTargets=["header", "footer"],
                    forbiddenCssTokens=["columns:", "writing-mode"],
                ),
            )
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
            )

            NovitaLlmAdapter(
                settings,
                session=FakeSession(FakeResponse('{"passed": true, "issues": []}')),
                llm_call_logger=llm_call_logger,
                prompt_store=PromptStore(root),
            ).verify_report_version(version, template_context=template_context)
            log_files = sorted((Path(tmpdir) / "job_test" / "05_verification" / "llm_calls").glob("*.json"))
            self.assertEqual(len(log_files), 1)
            payload = json.loads(log_files[0].read_text(encoding="utf-8"))

        combined = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("preview-bytes", combined)
        self.assertNotIn("data:image", combined)
        self.assertNotIn("secret-key-123", combined)
        generated_image_item = payload["request"]["messages"][1]["content"][1]
        template_image_item = payload["request"]["messages"][1]["content"][2]
        self.assertEqual(generated_image_item["label"], "generatedPreviewImage")
        self.assertEqual(generated_image_item["image_url"]["url"], "<image data redacted>")
        self.assertEqual(generated_image_item["image_url"]["mimeType"], "image/png")
        self.assertEqual(generated_image_item["image_url"]["base64Bytes"], 13)
        self.assertEqual(template_image_item["label"], "templatePreviewImage")
        self.assertEqual(template_image_item["image_url"]["url"], "<image data redacted>")
        self.assertEqual(template_image_item["image_url"]["mimeType"], "image/png")
        self.assertEqual(template_image_item["image_url"]["base64Bytes"], 14)
        text_payload = json.loads(payload["request"]["messages"][1]["content"][0]["text"])
        self.assertEqual(text_payload["template"]["revisionProfile"]["revisionMode"], "minimal_patch")
        self.assertTrue(text_payload["template"]["revisionProfile"]["preserveInitialGrid"])
        self.assertEqual(text_payload["template"]["revisionProfile"]["forbiddenCssTokens"], ["columns:", "writing-mode"])

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
