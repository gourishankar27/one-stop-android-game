"""Check foundation deliverables and links, without claiming a compiler build."""

from __future__ import annotations

import ast
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlparse
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
HEADINGS = (
    "Objective",
    "Why this phase exists",
    "Dependencies",
    "In scope",
    "Explicitly out of scope",
    "Architecture considerations",
    "Files likely to be created or modified",
    "Data models / APIs involved",
    "Implementation tasks",
    "Testing requirements",
    "Manual verification",
    "Completion criteria",
    "Documentation updates",
    "Handoff notes for next phase",
)


def check() -> list[str]:
    errors: list[str] = []
    required = [
        "AGENTS.md",
        "README.md",
        ".gitignore",
        ".editorconfig",
        ".gitattributes",
        "docs/PRODUCT.md",
        "docs/GAME_DESIGN.md",
        "docs/ARCHITECTURE.md",
        "docs/NETWORK_PROTOCOL.md",
        "docs/GAME_STATE.md",
        "docs/UI_UX.md",
        "docs/TESTING.md",
        "docs/DECISIONS.md",
        "docs/TOOLCHAIN.md",
        "docs/FOUNDATION_VALIDATION.md",
        "plans/plans.md",
        "plans/START_HERE.md",
        "server/pyproject.toml",
        "server/uv.lock",
        "android/settings.gradle.kts",
        "android/app/build.gradle.kts",
        "android/gradlew",
        "android/gradlew.bat",
        "android/gradle/wrapper/gradle-wrapper.jar",
    ]
    for item in required:
        if not (ROOT / item).is_file():
            errors.append(f"Missing {item}")
    phases = sorted((ROOT / "plans").glob("phase-*.md"))
    if len(phases) != 19:
        errors.append(f"Expected 19 phase files; found {len(phases)}")
    for number in range(19):
        matches = [p for p in phases if p.name.startswith(f"phase-{number:02}-")]
        if len(matches) != 1:
            errors.append(f"Phase {number:02} must have exactly one file")
    for path in phases:
        body = path.read_text(encoding="utf-8")
        for title in HEADINGS:
            if f"## {title}\n" not in body:
                errors.append(f"{path.name}: missing section {title}")
        if len(body.split()) < 300:
            errors.append(f"{path.name}: phase brief is too thin for review")
    docs = [ROOT / "README.md", ROOT / "AGENTS.md"]
    docs += list((ROOT / "docs").glob("*.md"))
    docs += list((ROOT / "plans").glob("*.md"))
    docs += [ROOT / "server/README.md", ROOT / "android/README.md"]
    for path in docs:
        if not path.is_file():
            continue
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            parsed = urlparse(target)
            if parsed.scheme or target.startswith("#"):
                continue
            if not (path.parent / unquote(parsed.path)).exists():
                errors.append(f"{path.relative_to(ROOT)}: broken link {target}")
    try:
        metadata = tomllib.loads((ROOT / "server/pyproject.toml").read_text())
        if metadata["project"]["requires-python"] != ">=3.12":
            errors.append("Unexpected Python baseline")
        ET.parse(ROOT / "android/app/src/main/AndroidManifest.xml")
        ET.parse(ROOT / "android/app/src/main/res/values/strings.xml")
        with ZipFile(ROOT / "android/gradle/wrapper/gradle-wrapper.jar") as archive:
            if "org/gradle/wrapper/GradleWrapperMain.class" not in archive.namelist():
                errors.append("Wrapper JAR is missing its main class")
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        errors.append(str(error))
    forbidden = {"fastapi", "pydantic", "asyncio", "socket", "time", "httpx", "uvicorn"}
    for path in (ROOT / "server/src/one_job/domain").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module.split(".")[0]]
            if forbidden.intersection(modules):
                errors.append(f"Domain boundary import in {path.relative_to(ROOT)}")
    return errors


if __name__ == "__main__":
    failures = check()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        raise SystemExit(1)
    print("Repository checks passed: 19 phase briefs, links, package/XML and wrapper structure.")
