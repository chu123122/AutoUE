from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


GENERATED_ROOT = Path("TypeScript")
DEFAULT_REPORT = Path("flow") / "aidev-stage-report.json"


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _iter_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return (p for p in root.rglob("*") if p.is_file())


def _generated_ts_cleanup_targets(aidev_ts_root: Path) -> list[Path]:
    """Return only AutoUE generated-code targets, never arbitrary user TS."""
    candidates: list[Path] = []
    if aidev_ts_root.exists():
        candidates.extend(aidev_ts_root.glob("AutoUEGenerated*.ts"))
        generated = aidev_ts_root / "content" / "generated"
        if generated.exists():
            candidates.extend(generated.glob("AutoUE*.ts"))
            interactive = generated / "interactive"
            if interactive.exists():
                candidates.extend(interactive.glob("*Interactable.ts"))
    safe: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if _inside(resolved, aidev_ts_root) and resolved.is_file():
            safe.append(resolved)
    return sorted(set(safe))


def _unlink_file(path: Path) -> None:
    try:
        path.unlink()
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)
        path.unlink()


@dataclass
class StageConfig:
    bundle: Path
    aidev_root: Path
    apply: bool
    run_tsc: bool
    report_path: Path


def stage_generated_ts_bundle(config: StageConfig) -> dict[str, Any]:
    bundle = config.bundle.resolve()
    source_ts = (bundle / GENERATED_ROOT).resolve()
    aidev_root = config.aidev_root.resolve()
    dest_ts = (aidev_root / "TypeScript").resolve()
    report_path = (bundle / config.report_path).resolve() if not config.report_path.is_absolute() else config.report_path.resolve()

    if not _inside(source_ts, bundle):
        raise RuntimeError(f"source TypeScript path escapes bundle: {source_ts}")
    if not source_ts.exists():
        raise FileNotFoundError(f"bundle TypeScript dir does not exist: {source_ts}")
    if not aidev_root.exists():
        raise FileNotFoundError(f"AIDev root does not exist: {aidev_root}")

    backup_root = bundle / "flow" / "aidev-stage-backups" / _now_stamp()
    cleanup_targets = _generated_ts_cleanup_targets(dest_ts)
    source_files = sorted(_iter_files(source_ts))
    copied: list[dict[str, Any]] = []
    removed: list[str] = []
    backed_up: list[str] = []

    if config.apply:
        backup_root.mkdir(parents=True, exist_ok=True)
        dest_ts.mkdir(parents=True, exist_ok=True)

    for target in cleanup_targets:
        rel = _rel(target, dest_ts)
        removed.append(rel)
        if config.apply:
            backup_target = backup_root / rel
            backup_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(backup_target))
            backed_up.append(rel)

    for src in source_files:
        rel = _rel(src, source_ts)
        dst = (dest_ts / rel).resolve()
        if not _inside(dst, dest_ts):
            raise RuntimeError(f"destination path escapes AIDev TypeScript dir: {rel}")
        record: dict[str, Any] = {"path": rel, "source_hash": _sha256(src)}
        if config.apply:
            if dst.exists():
                backup_target = backup_root / rel
                backup_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, backup_target)
                if rel not in backed_up:
                    backed_up.append(rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            record["dest_hash"] = _sha256(dst)
            record["same_hash"] = record["source_hash"] == record["dest_hash"]
        copied.append(record)

    tsc_result: dict[str, Any] | None = None
    if config.apply and config.run_tsc:
        tsc = aidev_root / "node_modules" / ".bin" / ("tsc.cmd" if sys.platform.startswith("win") else "tsc")
        if not tsc.exists():
            raise FileNotFoundError(f"AIDev tsc not found: {tsc}")
        proc = subprocess.run(
            [str(tsc), "-p", str(aidev_root / "tsconfig.json")],
            cwd=str(aidev_root),
            text=True,
            capture_output=True,
        )
        tsc_result = {
            "command": [str(tsc), "-p", str(aidev_root / "tsconfig.json")],
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
        if proc.returncode != 0:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report = {
                "schema_version": "autoue-aidev-stage-report/v1",
                "status": "failed",
                "reason": "tsc_failed",
                "bundle": str(bundle),
                "aidev_root": str(aidev_root),
                "apply": config.apply,
                "removed": removed,
                "backed_up": backed_up,
                "copied": copied,
                "backup_root": str(backup_root) if config.apply else None,
                "tsc": tsc_result,
            }
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            raise RuntimeError(f"AIDev tsc failed, report written: {report_path}")

    status = "staged" if config.apply else "dry_run"
    if config.apply and any(not item.get("same_hash", True) for item in copied):
        status = "failed"
    report = {
        "schema_version": "autoue-aidev-stage-report/v1",
        "status": status,
        "bundle": str(bundle),
        "source_ts": str(source_ts),
        "aidev_root": str(aidev_root),
        "dest_ts": str(dest_ts),
        "apply": config.apply,
        "run_tsc": config.run_tsc,
        "removed": removed,
        "backed_up": backed_up,
        "copied": copied,
        "backup_root": str(backup_root) if config.apply else None,
        "tsc": tsc_result,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if status == "failed":
        raise RuntimeError(f"AIDev stage hash mismatch, report written: {report_path}")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage generated AutoUE TypeScript bundle into an AIDev project.")
    parser.add_argument("--bundle", required=True, help="Workflow bundle root containing TypeScript/.")
    parser.add_argument("--aidev-root", required=True, help="AIDev project root, e.g. D:/UE5.7.4/AIDev")
    parser.add_argument("--apply", action="store_true", help="Actually clean/copy files. Without this, only writes a dry-run report.")
    parser.add_argument("--run-tsc", action="store_true", help="Run AIDev tsc after staging.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT).replace("\\", "/"), help="Report path, relative to bundle by default.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = stage_generated_ts_bundle(
        StageConfig(
            bundle=Path(args.bundle),
            aidev_root=Path(args.aidev_root),
            apply=bool(args.apply),
            run_tsc=bool(args.run_tsc),
            report_path=Path(args.report),
        )
    )
    print(json.dumps({"result": "pass", "status": report["status"], "report": str(Path(args.bundle) / args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
