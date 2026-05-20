#!/usr/bin/env python3
"""figma-prd 스킬 — 합성 단계.

extract.summary.json + 노드별 texts.md / analysis.{mode}.md / 이미지 자료를
모드별 PRD 템플릿에 채워 최종 prd.md(또는 prd.{mode}.md)를 만든다.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parent.parent  # skills/figma-prd/
TEMPLATE_DIR = SKILL_DIR / "templates"

# extract.py가 수집한 page_info dict의 키 → PRD에 표시할 한글 라벨.
PAGE_INFO_LABEL_MAP = {
    "project": "프로젝트",
    "date": "작성일",
    "author": "작성자",
    "screen": "화면",
    "screen id": "화면ID",
}
PAGE_INFO_KEY_ORDER = ("project", "date", "author", "screen", "screen id")


def render_page_info(page_info: dict[str, str]) -> str:
    if not page_info:
        return ""
    parts: list[str] = []
    for key in PAGE_INFO_KEY_ORDER:
        if key in page_info:
            label = PAGE_INFO_LABEL_MAP.get(key, key)
            value = page_info[key] or "-"
            parts.append(f"{label}={value}")
    for key, value in page_info.items():
        if key not in PAGE_INFO_LABEL_MAP:
            parts.append(f"{key}={value or '-'}")
    return " · ".join(parts)


_INVALID_FILENAME_RE = re.compile(r'[\\/:*?"<>|]')


def auto_title(summary: dict[str, Any]) -> str:
    """PRD 파일명·헤더용 짧은 제목 자동 도출.

    1순위: ``context``의 첫 마침표/줄바꿈 전 부분
    2순위: 첫 노드 라벨 (+ 추가 노드 수)
    3순위: ``"PRD"`` 고정
    """
    context = (summary.get("context") or "").strip()
    if context:
        first = re.split(r"[.\n]", context, maxsplit=1)[0].strip()
        if first:
            return first
    nodes = summary.get("nodes") or []
    if nodes:
        label = (nodes[0].get("label") or "").strip()
        if label:
            extra = len(nodes) - 1
            return f"{label} 외 {extra}건" if extra > 0 else label
    return "PRD"


def sanitize_filename(name: str) -> str:
    sanitized = _INVALID_FILENAME_RE.sub("_", name)
    sanitized = re.sub(r"\s+", " ", sanitized).strip(" .")
    return sanitized or "PRD"


def output_filename(title: str, mode: str) -> str:
    return f"{sanitize_filename(title)} ({mode}).md"


def find_project_root(start: Path) -> Path:
    """git working tree 루트를 반환. git이 아니면 ``start`` 그대로."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return start


def discover_config(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    cwd = Path.cwd()
    candidates: list[Path] = [cwd / "figma-prd.config.json"]
    root = find_project_root(cwd)
    if root.resolve() != cwd.resolve():
        candidates.append(root / "figma-prd.config.json")
    for c in candidates:
        if c.exists():
            return c.resolve()
    tried = "\n  ".join(str(c) for c in candidates)
    raise SystemExit(
        "ERROR: figma-prd.config.json을 찾을 수 없습니다. "
        "--config 로 명시하거나 프로젝트 루트에 두세요.\n  시도한 경로:\n  "
        + tried
    )


def resolve_output_dir(cfg: dict[str, Any], config_path: Path) -> Path:
    raw = cfg.get("output_dir")
    config_dir = config_path.parent.resolve()
    if raw:
        p = Path(raw)
        return p.resolve() if p.is_absolute() else (config_dir / p).resolve()
    project_root = find_project_root(config_dir)
    return (project_root / "docs" / "prd-out").resolve()


def safe_node_id(node_id: str) -> str:
    return node_id.replace(":", "-")


def figma_node_url(file_key: str, node_id: str) -> str:
    return f"https://www.figma.com/design/{file_key}?node-id={safe_node_id(node_id)}&m=dev"


def relpath(target: Path, base: Path) -> str:
    try:
        return str(target.relative_to(base))
    except ValueError:
        return str(target)


def collect_glossary_terms(texts_paths: list[Path]) -> list[tuple[str, int]]:
    # 대문자 약어/식별자/하이픈+숫자 패턴 (예: UMS, AES-256, SHA-256, WEB_LGN_009, UMS-API-001)
    pattern = re.compile(r"\b(?:[A-Z][A-Z0-9_]{2,}(?:-[A-Z0-9]+)*|[A-Z]+-\d+)\b")
    counter: Counter[str] = Counter()
    for p in texts_paths:
        if not p.exists():
            continue
        for match in pattern.findall(p.read_text(encoding="utf-8")):
            counter[match] += 1
    return [(term, count) for term, count in counter.most_common() if count >= 2]


def render_node_section(
    index: int,
    file_key: str,
    node_entry: dict[str, Any],
    mode: str,
    output_root: Path,
) -> tuple[str, str]:
    node_id = node_entry["node_id"]
    label = node_entry["label"]
    node_dir = Path(node_entry["node_dir"])

    anchor = f"node-{safe_node_id(node_id)}"

    lines: list[str] = [
        f'## {index}. {label} <a id="{anchor}"></a>',
        "",
        f"- **노드 ID**: `{node_id}`",
        f"- **Figma 노드 URL**: {figma_node_url(file_key, node_id)}",
        f"- **로컬 경로**: `{relpath(node_dir, output_root)}/`",
    ]
    page_info_line = render_page_info(node_entry.get("page_info") or {})
    if page_info_line:
        lines.append(f"- **페이지 메타**: {page_info_line}")
    excl_ids = node_entry.get("exclude_node_ids") or []
    excl_notes = node_entry.get("exclude_notes") or []
    if excl_ids or excl_notes:
        lines.append("- **제외 처리**:")
        for eid in excl_ids:
            lines.append(f"  - `{eid}` (트리 가지치기)")
        for note in excl_notes:
            lines.append(f"  - {note}")
    lines.append("")

    # 1) 원문 (texts.md)
    lines.append(f"### {index}.1 원문 정책·설명 (Figma `characters`)")
    lines.append("")
    texts_md = node_dir / "texts.md"
    if texts_md.exists():
        lines.append(texts_md.read_text(encoding="utf-8").rstrip())
    else:
        lines.append("_texts.md 없음._")
    lines.append("")

    # 2) 시각 자료
    lines.append(f"### {index}.2 시각 자료")
    lines.append("")
    screenshot = node_dir / "screenshot.png"
    if screenshot.exists():
        lines.append(f"![{label} screenshot]({relpath(screenshot, output_root)})")
        lines.append("")
    images_dir = node_dir / "images"
    if images_dir.exists():
        for img in sorted(images_dir.glob("*.png")):
            lines.append(f"![image {img.stem}]({relpath(img, output_root)})")
            lines.append("")

    # 3) 분석 결과
    lines.append(f"### {index}.3 {mode} 요구사항 (분석)")
    lines.append("")
    analysis_path = node_dir / f"analysis.{mode}.md"
    if analysis_path.exists():
        lines.append(analysis_path.read_text(encoding="utf-8").rstrip())
    else:
        lines.append(
            f"_{analysis_path.name} 없음 — 분석 단계가 아직 수행되지 않았거나 실패했습니다._"
        )
    lines.append("")

    return anchor, "\n".join(lines)


def build_prd(summary: dict[str, Any], mode: str) -> str:
    file_key = summary["file_key"]
    context = summary.get("context") or ""
    output_dir = Path(summary["output_dir"])
    nodes = summary["nodes"]

    title = context or file_key
    generated_at = datetime.datetime.now().astimezone().isoformat()
    figma_url = f"https://www.figma.com/design/{file_key}"

    sections: list[str] = []
    toc_lines: list[str] = []
    texts_paths: list[Path] = []
    for i, node_entry in enumerate(nodes, start=1):
        anchor, sec = render_node_section(i, file_key, node_entry, mode, output_dir)
        sections.append(sec)
        toc_lines.append(f"{i}. [{node_entry['label']}](#{anchor})")
        texts_paths.append(Path(node_entry["node_dir"]) / "texts.md")

    glossary = collect_glossary_terms(texts_paths)
    glossary_md = (
        "\n".join(f"- `{term}` — {count}회 등장" for term, count in glossary)
        if glossary
        else "_자동 수집된 용어 없음._"
    )

    extract_meta = "\n".join(
        f"- `{n['node_id']}` — label: {n['label']} / texts: {n['text_count']} / images: {n['image_count']}"
        for n in nodes
    )

    template = (TEMPLATE_DIR / f"prd.{mode}.template.md").read_text(encoding="utf-8")
    return (
        template.replace("{{TITLE}}", title)
        .replace("{{GENERATED_AT}}", generated_at)
        .replace("{{FIGMA_FILE_URL}}", figma_url)
        .replace("{{NODE_COUNT}}", str(len(nodes)))
        .replace("{{CONTEXT}}", context or "_없음_")
        .replace("{{TOC}}", "\n".join(toc_lines))
        .replace("{{NODE_SECTIONS}}", "\n\n".join(sections))
        .replace("{{GLOSSARY}}", glossary_md)
        .replace("{{EXTRACT_META}}", extract_meta)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="figma-prd 합성 — texts + analysis → prd.md"
    )
    parser.add_argument(
        "--config",
        default=None,
        help="figma-prd.config.json 경로 (생략 시 cwd 또는 git 루트에서 자동 탐색)",
    )
    args = parser.parse_args()

    cfg_path = discover_config(args.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    file_key = cfg["file_key"]
    output_dir = resolve_output_dir(cfg, cfg_path)
    print(f"[synthesize] config: {cfg_path}", file=sys.stderr)
    print(f"[synthesize] output_dir: {output_dir}", file=sys.stderr)
    file_root = output_dir / file_key

    summary_path = file_root / "extract.summary.json"
    if not summary_path.exists():
        print(
            f"ERROR: {summary_path} 없음. 먼저 extract.py를 실행하세요.",
            file=sys.stderr,
        )
        sys.exit(2)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    mode = cfg.get("mode", "backend")
    title = auto_title(summary)
    print(f"[synthesize] title: {title}", file=sys.stderr)
    if mode == "both":
        for sub in ("backend", "frontend"):
            md = build_prd(summary, sub)
            out = file_root / output_filename(title, sub)
            out.write_text(md, encoding="utf-8")
            print(f"[synthesize] {sub} → {out}", file=sys.stderr)
    elif mode in ("backend", "frontend"):
        md = build_prd(summary, mode)
        out = file_root / output_filename(title, mode)
        out.write_text(md, encoding="utf-8")
        print(f"[synthesize] {mode} → {out}", file=sys.stderr)
    else:
        print(
            f"ERROR: unknown mode '{mode}'. backend|frontend|both 중 하나여야 합니다.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
