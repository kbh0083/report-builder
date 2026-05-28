import tempfile
import unittest
from pathlib import Path


PROMPT_ROOT = Path(__file__).resolve().parents[1] / "report_engine" / "prompt"


class PromptStoreTests(unittest.TestCase):
    def test_read_text_ignores_hash_comment_lines(self):
        from report_engine.prompt_store import PromptStore

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "prompt.txt").write_text(
                "# ko: 첫 번째 지시문의 한국어 번역입니다.\n"
                "First instruction.\n"
                "\n"
                "  # ko: 두 번째 지시문의 한국어 번역입니다.\n"
                "Second instruction.\n",
                encoding="utf-8",
            )

            content = PromptStore(root).read_text("prompt.txt")

        self.assertEqual(content, "First instruction.\nSecond instruction.")

    def test_read_json_accepts_jsonc_comments_without_stripping_string_urls(self):
        from report_engine.prompt_store import PromptStore

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "prompt.json").write_text(
                "[\n"
                "  // ko: 첫 번째 지시문의 한국어 번역입니다.\n"
                '  "Use https://example.com only inside string values.",\n'
                "  // ko: 두 번째 지시문의 한국어 번역입니다.\n"
                '  "Keep // markers when they are inside strings."\n'
                "]\n",
                encoding="utf-8",
            )

            content = PromptStore(root).read_json("prompt.json")

        self.assertEqual(
            content,
            [
                "Use https://example.com only inside string values.",
                "Keep // markers when they are inside strings.",
            ],
        )

    def test_repository_prompt_korean_comments_are_top_blocks_only(self):
        for path in sorted(PROMPT_ROOT.glob("*")):
            if path.suffix not in {".txt", ".json"}:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            marker = "# ko:" if path.suffix == ".txt" else "// ko:"
            seen_prompt_body = False
            ko_comment_count = 0
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith(marker):
                    ko_comment_count += 1
                    self.assertFalse(
                        seen_prompt_body,
                        f"Korean prompt comments must stay in a top block: {path.name}",
                    )
                    continue
                seen_prompt_body = True
            self.assertGreater(ko_comment_count, 0, f"Korean translation comment is missing: {path.name}")


if __name__ == "__main__":
    unittest.main()
