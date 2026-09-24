#!/usr/bin/env python3
"""Eval Harness deterministico e privacy-first per GF-AOS."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import tomllib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = 1
MAX_TEXT_BYTES = 1024 * 1024


class HarnessError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def repository_provenance(repo: Path) -> tuple[bool, str]:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=repo, check=True, capture_output=True, text=True, timeout=10,
    )
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repo, check=True, capture_output=True, timeout=10,
    ).stdout
    source = hashlib.sha256()
    for raw in sorted(item for item in listed.split(b"\0") if item):
        relative = raw.decode("utf-8")
        path = repo / relative
        if path.is_symlink() or not path.is_file():
            raise HarnessError("Sorgente repository non valida")
        source.update(raw)
        source.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                source.update(chunk)
        source.update(b"\0")
    return not bool(status.stdout.strip()), source.hexdigest()


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def safe_repo(raw: str | None) -> Path:
    path = Path(raw).expanduser() if raw else Path(__file__).parents[3]
    if path.is_symlink():
        raise HarnessError("Repository non valida")
    resolved = path.resolve()
    if not (resolved / "plugins" / "gf-aos-professional-studio").is_dir():
        raise HarnessError("Repository GF-AOS non valida")
    return resolved


def safe_output(raw: str, repo: Path) -> Path:
    lexical = Path(raw).expanduser()
    if lexical.exists() and lexical.is_symlink():
        raise HarnessError("Directory output non valida")
    output = lexical.resolve()
    repo = repo.resolve()
    if output == repo or repo in output.parents:
        raise HarnessError("Il report eval deve restare fuori dalla repository")
    lexical.mkdir(parents=True, exist_ok=True)
    return output


def text_files(root: Path, pattern: str) -> list[Path]:
    files = sorted(root.glob(pattern))
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise HarnessError("File governato non valido")
    return files


def check_eval_specs(repo: Path) -> dict[str, Any]:
    root = repo / "plugins" / "gf-aos-professional-studio" / "evals"
    files = text_files(root, "*/*.md")
    failures = 0
    for path in files:
        if path.stat().st_size > MAX_TEXT_BYTES:
            failures += 1
            continue
        content = path.read_text(encoding="utf-8")
        lines = [line for line in content.splitlines() if line.strip().startswith("-")]
        title_ok = content.startswith("# Eval")
        expected_ok = "Esito atteso" in content or len(lines) >= 4
        if not (title_ok and expected_ok):
            failures += 1
    return {"specs": len(files), "failures": failures}


def check_skills(repo: Path) -> dict[str, Any]:
    root = repo / "plugins" / "gf-aos-professional-studio" / "skills"
    files = text_files(root, "*/SKILL.md")
    failures = 0
    for path in files:
        content = path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        if len(parts) != 3 or "name:" not in parts[1] or "description:" not in parts[1]:
            failures += 1
    return {"skills": len(files), "failures": failures}


def check_structured_files(repo: Path) -> dict[str, Any]:
    json_count = 0
    toml_count = 0
    failures = 0
    for path in sorted(repo.rglob("*.json")):
        if ".git" in path.parts:
            continue
        json_count += 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            failures += 1
    for path in sorted(repo.rglob("*.toml")):
        if ".git" in path.parts:
            continue
        toml_count += 1
        try:
            tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            failures += 1
    return {"json": json_count, "toml": toml_count, "failures": failures}


def check_python(repo: Path) -> dict[str, Any]:
    root = repo / "plugins" / "gf-aos-professional-studio"
    files = text_files(root, "scripts/*.py") + text_files(root, "tests/*.py")
    failures = 0
    for path in files:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (OSError, UnicodeError, SyntaxError):
            failures += 1
    return {"python_files": len(files), "failures": failures}


def check_tests(repo: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s",
         "plugins/gf-aos-professional-studio/tests", "-p", "test_*.py", "-q"],
        cwd=repo, env=env, check=False, capture_output=True, text=True, timeout=180,
    )
    combined = f"{result.stdout}\n{result.stderr}"
    marker = "Ran "
    tests = 0
    for line in combined.splitlines():
        if marker in line and " tests" in line:
            try:
                tests = int(line.split(marker, 1)[1].split(" tests", 1)[0])
            except ValueError:
                tests = 0
    return {
        "tests": tests,
        "return_code": result.returncode,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "failures": 0 if result.returncode == 0 else 1,
    }


def execute_check(code: str, check: Callable[[Path], dict[str, Any]], repo: Path) -> dict[str, Any]:
    started = time.monotonic()
    try:
        metrics = check(repo)
        status = "PASS" if metrics.get("failures", 0) == 0 else "BLOCKED"
    except (HarnessError, OSError, UnicodeError, ValueError, TypeError, subprocess.SubprocessError):
        metrics = {"failures": 1}
        status = "BLOCKED"
    return {
        "code": code,
        "status": status,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "metrics": metrics,
    }


def render(report: dict[str, Any]) -> str:
    lines = [
        "# GF-AOS Eval Harness Report",
        "",
        f"- Esito: **{report['status']}**",
        f"- Data operativa: `{report['as_of']}`",
        f"- Generato UTC: `{report['generated_at']}`",
        f"- Commit: `{report['commit_sha']}`",
        f"- Worktree pulita: `{str(report['worktree_clean']).lower()}`",
        f"- Sorgenti SHA-256: `{report['source_sha256']}`",
        "- Il report non autorizza invio, pubblicazione, deposito o modifica delle fonti.",
        "",
        "| Controllo | Esito | Metriche |",
        "| --- | --- | --- |",
    ]
    for item in report["checks"]:
        metrics = ", ".join(f"{key}={value}" for key, value in sorted(item["metrics"].items()))
        lines.append(f"| `{item['code']}` | `{item['status']}` | {metrics} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GF-AOS deterministic eval harness")
    parser.add_argument("--repo")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--skip-regression", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        date.fromisoformat(args.as_of)
        repo = safe_repo(args.repo)
        output = safe_output(args.output_dir, repo)
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        worktree_clean, source_sha256 = repository_provenance(repo)
        checks = [
            execute_check("EVAL_SPECS", check_eval_specs, repo),
            execute_check("SKILL_SCHEMA", check_skills, repo),
            execute_check("STRUCTURED_FILES", check_structured_files, repo),
            execute_check("PYTHON_SYNTAX", check_python, repo),
        ]
        if not args.skip_regression:
            checks.append(execute_check("REGRESSION", check_tests, repo))
        status = "PASS" if all(item["status"] == "PASS" for item in checks) else "BLOCKED"
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "as_of": args.as_of,
            "generated_at": now_iso(),
            "commit_sha": commit,
            "worktree_clean": worktree_clean,
            "source_sha256": source_sha256,
            "checks": checks,
            "professional_approval_claimed": False,
            "external_execution_claimed": False,
        }
        json_path = output / "EVAL_REPORT.json"
        md_path = output / "EVAL_REPORT.md"
        atomic_text(json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        atomic_text(md_path, render(report))
        print(f"GF-AOS eval harness: {status}; checks={len(checks)}")
        return 0 if status == "PASS" else 2
    except (HarnessError, OSError, UnicodeError, ValueError, subprocess.SubprocessError):
        print("ERRORE: eval harness non completato", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
