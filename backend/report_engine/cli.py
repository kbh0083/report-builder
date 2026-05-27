import argparse
from collections.abc import Sequence

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
        ReportJobRequest(
            datasetId=args.dataset_id,
            templateId=args.template_id,
            monthId=args.month_id,
            componentMode=args.component_mode,
            layoutMode=args.layout_mode,
            verificationMode=args.verification_mode,
            maxIterations=args.max_iterations,
            outputDir=args.output_dir,
        )
        parser.exit(2, "report_engine run is implemented in later tasks beyond Task 5 scope.\n")
    parser.print_help()
    return 0
