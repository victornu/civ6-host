"""Read-only operator check for prepared capture files."""

import json

from .capture_package import CapturePackageError, read_package



def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Verify a prepared capture and its installed engine without loading Civ6.")
    parser.add_argument("--manifest", required=True, help="Absolute path to the prepared manifest.json")
    parser.add_argument("--sha256", required=True, help="Expected manifest digest from preparation")
    parser.add_argument("--candidate-profile", choices=("xp1-lan", "xp2-lan"),
                        help="Explicit private expansion profile, when required by the package")
    args = parser.parse_args(argv)
    reference = {"path": args.manifest, "sha256": args.sha256}
    try:
        manifest, _, files = read_package(reference, _candidate_profile=args.candidate_profile)
    except CapturePackageError as exc:
        parser.exit(1, f"Prepared capture verification failed: {exc}\n")
    print(json.dumps({
        "schema": "civ6-host.capture-file-verification.v1",
        "status": "verified_files",
        "package_sha256": args.sha256,
        "input_profile": manifest["input_profile"],
        "origin_manifest_sha256": manifest["origin_manifest_sha256"],
        "gamecore_sha256": manifest["engine"]["sha256"],
        "file_count": len(files),
        "total_bytes": sum(record["bytes"] for record in manifest["files"].values()),
        "native_session_admitted": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
