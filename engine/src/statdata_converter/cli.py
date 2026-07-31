from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from .service import ConversionService


def _json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("Options must be a JSON object.")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="statdata-converter",
        description="Convert statistical data locally with a fidelity report.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capabilities = subparsers.add_parser(
        "capabilities",
        help="Show format capabilities available in this engine build.",
    )
    capabilities.add_argument("--json", action="store_true")

    bridge_diagnostics = subparsers.add_parser(
        "bridge-diagnostics",
        help="Show installed bridge and local vendor-runtime status.",
    )
    bridge_diagnostics.add_argument("--json", action="store_true")

    bridge_install = subparsers.add_parser(
        "bridge-install",
        help="Install a trusted local bridge bundle.",
    )
    bridge_install.add_argument("manifest")
    bridge_install.add_argument("--json", action="store_true")

    certification_audit = subparsers.add_parser(
        "certification-audit",
        help="Audit a vendor certification evidence package.",
    )
    certification_audit.add_argument("manifest")
    certification_audit.add_argument("--json", action="store_true")

    subparsers.add_parser(
        "serve",
        help="Run the newline-delimited JSON protocol used by the desktop app.",
    )

    convert = subparsers.add_parser("convert", help="Convert one dataset.")
    convert.add_argument("input")
    convert.add_argument("output")
    convert.add_argument("--input-format")
    convert.add_argument("--output-format")
    convert.add_argument("--input-options", type=_json_object, default={})
    convert.add_argument("--output-options", type=_json_object, default={})
    convert.add_argument("--report")
    convert.add_argument(
        "--json",
        action="store_true",
        help="Print only the machine-readable result.",
    )

    validate = subparsers.add_parser(
        "validate",
        help="Round-trip one dataset through a target format and compare it.",
    )
    validate.add_argument("input")
    validate.add_argument("target_format")
    validate.add_argument("--input-format")
    validate.add_argument("--input-options", type=_json_object, default={})
    validate.add_argument("--output-options", type=_json_object, default={})
    validate.add_argument(
        "--artifacts",
        help="Directory for the round-trip file and validation reports.",
    )
    validate.add_argument("--json", action="store_true")
    return parser


def _serve(service: ConversionService) -> int:
    for line in sys.stdin:
        request: Any = None
        try:
            request = json.loads(line)
            request_id = request.get("id")
            method = request.get("method")
            parameters = request.get("params") or {}
            if method == "capabilities":
                result = service.capabilities()
            elif method == "bridge_diagnostics":
                result = service.bridge_diagnostics()
            elif method == "install_bridge":
                result = service.install_bridge(parameters["manifest_path"])
            elif method == "audit_certification":
                result = service.audit_certification(
                    parameters["manifest_path"]
                )
            elif method == "convert":
                result = service.convert(
                    parameters["input_path"],
                    parameters["output_path"],
                    input_format=parameters.get("input_format"),
                    output_format=parameters.get("output_format"),
                    input_options=parameters.get("input_options"),
                    output_options=parameters.get("output_options"),
                    report_path=parameters.get("report_path"),
                )
            elif method == "validate":
                result = service.validate(
                    parameters["input_path"],
                    parameters["target_format"],
                    artifact_directory=parameters.get("artifact_directory"),
                    input_format=parameters.get("input_format"),
                    input_options=parameters.get("input_options"),
                    output_options=parameters.get("output_options"),
                )
            else:
                raise ValueError(f"Unknown engine method: {method}")
            response = {"id": request_id, "result": result}
        except Exception as exc:
            response = {
                "id": request.get("id") if isinstance(request, dict) else None,
                "error": str(exc),
            }
        print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = ConversionService()
    try:
        if args.command == "serve":
            return _serve(service)
        if args.command == "capabilities":
            result = service.capabilities()
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                for item in result["formats"]:
                    read = "read" if item["can_read"] else "—"
                    write = "write" if item["can_write"] else "—"
                    print(
                        f"{item['family']:<14} {item['label']:<30} "
                        f"{read:<5} {write:<5} {item['availability']}"
                    )
            return 0

        if args.command == "bridge-diagnostics":
            result = service.bridge_diagnostics()
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                summary = result["summary"]
                print(f"Installed bridges: {summary['installed']}")
                print(f"Ready bridges:     {summary['ready']}")
                print(
                    "Vendor runtimes:   "
                    f"{summary['vendor_runtimes_detected']} detected"
                )
                print(f"Bridge folder:     {result['bridge_directory']}")
            return 0

        if args.command == "bridge-install":
            result = service.install_bridge(args.manifest)
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(f"Installed: {result['name']}")
                print(f"Location:  {result['manifest_path']}")
                print(
                    "Runtime:   "
                    + (
                        "ready"
                        if result["bridge"]["available"]
                        else "installed, vendor runtime not ready"
                    )
                )
            return 0

        if args.command == "certification-audit":
            result = service.audit_certification(args.manifest)
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(f"Evidence audit: {result['status']}")
                print(f"Format:         {result['format_id']}")
                print(f"Direction:      {result['direction']}")
                print(f"Claim:          {result['claim']}")
                print(
                    "Issues:         "
                    f"{result['summary']['errors']} error(s), "
                    f"{result['summary']['warnings']} warning(s)"
                )
            return 0 if result["status"] == "passed" else 1

        if args.command == "validate":
            result = service.validate(
                args.input,
                args.target_format,
                artifact_directory=args.artifacts,
                input_format=args.input_format,
                input_options=args.input_options,
                output_options=args.output_options,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                verdict = (
                    "passed"
                    if result["data_equivalent"]
                    else "failed"
                )
                print(f"Round trip: {verdict}")
                print(f"Artifact:   {result['artifact_path'] or 'not created'}")
                print(f"Validation: {result['validation_path']}")
                print(
                    "Fidelity:   "
                    f"{result['summary']['data_issues']} data issue(s), "
                    f"{result['summary']['metadata_issues']} metadata issue(s)"
                )
            return 0 if result["status"] == "passed" else 1

        result = service.convert(
            args.input,
            args.output,
            input_format=args.input_format,
            output_format=args.output_format,
            input_options=args.input_options,
            output_options=args.output_options,
            report_path=args.report,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            summary = result["report"]["summary"]
            print(f"Converted: {result['output_path']}")
            print(f"Report:    {result['report_path']}")
            print(
                "Fidelity:  "
                f"{summary['warning']} warning(s), {summary['error']} error(s)"
            )
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
