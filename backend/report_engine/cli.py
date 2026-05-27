import argparse
import json
from collections.abc import Sequence

from .logging_flow import event_to_stdout_line, run_with_artifact_logging
from .models import ReportJobRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m report_engine",
        description="ETF report engine CLI",
        epilog="run options include --dataset-id, --template-id, --month-id, --component-mode, --layout-mode, --verification-mode, --max-iterations, --output-dir",
    )
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run", help="run a report generation job")
    run_parser.add_argument("--dataset-id", required=True)
    run_parser.add_argument("--template-id", required=True)
    run_parser.add_argument("--month-id", required=True)
    run_parser.add_argument("--component-mode", choices=["sample", "novita"], default="sample")
    run_parser.add_argument("--layout-mode", choices=["novita"], default="novita")
    run_parser.add_argument("--verification-mode", choices=["manual-pass", "novita"], default="manual-pass")
    run_parser.add_argument("--max-iterations", type=int, default=3)
    run_parser.add_argument("--output-dir", default="runs")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "run":
        request = ReportJobRequest(
            datasetId=args.dataset_id,
            templateId=args.template_id,
            monthId=args.month_id,
            componentMode=args.component_mode,
            layoutMode=args.layout_mode,
            verificationMode=args.verification_mode,
            maxIterations=args.max_iterations,
            outputDir=args.output_dir,
        )
        try:
            print(event_to_stdout_line(run_with_artifact_logging(request)))
            return 0
        except Exception as exc:
            print(json.dumps({"event": "job.failed", "detail": str(exc)}, ensure_ascii=False))
            return 1
    parser.print_help()
    return 0
