import json
import unittest
from collections import defaultdict
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent
DATA_DIR = BACKEND_ROOT / "data"

EXPECTED_DATASET_IDS = {
    "data_kodex_us_sp500_h",
    "data_kodex_us_sp500",
    "data_kodex_us_nasdaq100",
    "data_kodex_korea_dividend_growth_bond_mixed",
}
EXPECTED_TEMPLATE_IDS = {
    "tpl_kb_monthly_guidebook",
    "tpl_woori_monthly_report",
}
EXPECTED_COMPONENT_KEYS = [
    "performance_chart",
    "performance_summary",
    "top_holdings",
    "review",
    "outlook",
]


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


class DataCatalogTests(unittest.TestCase):
    def test_template_catalog_is_separate_and_paths_exist(self):
        catalog = load_json(DATA_DIR / "report_templates.json")

        self.assertEqual(catalog["schemaVersion"], "poc.etfReport.templates.v1")
        self.assertEqual(catalog["templateCount"], 2)
        self.assertEqual({item["templateId"] for item in catalog["templates"]}, EXPECTED_TEMPLATE_IDS)

        for template in catalog["templates"]:
            self.assertEqual(template["page"], {"size": "A4", "orientation": "portrait"})
            self.assertNotIn("sourceHtml", template)
            self.assertTrue(
                template["previewImage"].startswith("backend/data/report_template/"),
                template["previewImage"],
            )
            self.assertTrue((WORKSPACE_ROOT / template["previewImage"]).is_file())

    def test_datasets_have_dataset_ids_and_no_embedded_template(self):
        bundle = load_json(DATA_DIR / "etf_data.json")
        datasets = bundle["datasets"]

        self.assertEqual(bundle["datasetCount"], 4)
        self.assertEqual({item["datasetId"] for item in datasets}, EXPECTED_DATASET_IDS)

        for dataset in datasets:
            self.assertNotIn("template", dataset)
            self.assertNotIn("styleCandidates", dataset)
            self.assertEqual([snapshot["monthId"] for snapshot in dataset["monthlySnapshots"]], ["2026-01", "2026-02", "2026-03"])

    def test_legacy_dataset_samples_do_not_embed_style_candidates(self):
        for path in DATA_DIR.glob("*.dataset.sample.json"):
            with self.subTest(path=path.name):
                sample = load_json(path)
                self.assertNotIn("styleCandidates", sample)

    def test_stage2_source_catalog_uses_dataset_ids(self):
        catalog = load_json(DATA_DIR / "etf_stage2_component_sources.json")
        groups = defaultdict(list)

        self.assertEqual(catalog["componentSourceCount"], 60)
        self.assertEqual(catalog["componentKeys"], EXPECTED_COMPONENT_KEYS)

        for source in catalog["componentSources"]:
            dataset_ref = source["datasetRef"]
            self.assertIn("datasetId", dataset_ref)
            self.assertNotIn("templateId", dataset_ref)
            self.assertIn(dataset_ref["datasetId"], EXPECTED_DATASET_IDS)
            month_id = source["snapshotRef"]["monthId"]
            groups[(dataset_ref["datasetId"], month_id)].append(source["componentKey"])
            month_token = month_id.replace("-", "_")
            expected_id = f"ds_{dataset_ref['datasetId']}_{month_token}_{source['componentKey']}"
            self.assertEqual(source["dataSourceId"], expected_id)

        self.assertEqual(len(groups), 12)
        for keys in groups.values():
            self.assertEqual(keys, EXPECTED_COMPONENT_KEYS)

    def test_stage2_sample_components_use_dataset_ids(self):
        catalog = load_json(DATA_DIR / "etf_stage2_components.sample.json")
        groups = defaultdict(list)

        self.assertEqual(catalog["componentCount"], 60)

        for component in catalog["stage2Components"]:
            self.assertIn(component["datasetId"], EXPECTED_DATASET_IDS)
            self.assertIn(component["componentKey"], EXPECTED_COMPONENT_KEYS)
            month_token = component["monthId"].replace("-", "_")
            expected_component_id = f"comp_{component['datasetId']}_{month_token}_{component['componentKey']}"
            expected_data_source_id = f"ds_{component['datasetId']}_{month_token}_{component['componentKey']}"
            self.assertEqual(component["componentId"], expected_component_id)
            self.assertEqual(component["dataSourceId"], expected_data_source_id)
            self.assertIn(expected_component_id, component["html"])
            groups[(component["datasetId"], component["monthId"])].append(component["componentKey"])

        self.assertEqual(len(groups), 12)
        for keys in groups.values():
            self.assertEqual(keys, EXPECTED_COMPONENT_KEYS)


if __name__ == "__main__":
    unittest.main()
