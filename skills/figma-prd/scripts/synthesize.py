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
    domain = (cfg.get("domain") or "").strip().strip("/")
    if domain:
        return (project_root / "docs" / domain / "prd").resolve()
    return (project_root / "docs" / "prd-out").resolve()


def resolve_prd_dir_name(cfg: dict[str, Any]) -> str:
    """PRD 출력 디렉터리 이름. task_name 명시 시 그것을, 없으면 file_key fallback."""
    return cfg.get("task_name") or cfg["file_key"]


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


def render_comments_for_prd(node_dir: Path) -> str | None:
    """node_dir/comments.md 를 PRD 노드 섹션에 임베드할 수 있게 변환.

    standalone 파일의 h1 제목 + 메타 줄은 떼고, ``## 스레드`` 헤딩은 ``#### 스레드``
    로 강등해 노드 sub-section(h3) 아래에 자연스럽게 들어가게 한다. 댓글 원문은
    결정적으로 PRD에 보존된다 (LLM 분석을 거치지 않음).
    """
    p = node_dir / "comments.md"
    if not p.exists():
        return None
    out: list[str] = []
    started = False
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not started:
            if ln.startswith("## 스레드"):
                started = True
            else:
                continue
        out.append(ln.replace("## 스레드", "#### 스레드", 1) if ln.startswith("## 스레드") else ln)
    body = "\n".join(out).strip()
    return body or None


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

    # 1) 시각 자료
    lines.append(f"### {index}.1 시각 자료")
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

    # 2) 분석 결과
    lines.append(f"### {index}.2 {mode} 요구사항 (분석)")
    lines.append("")
    analysis_path = node_dir / f"analysis.{mode}.md"
    if analysis_path.exists():
        lines.append(analysis_path.read_text(encoding="utf-8").rstrip())
    else:
        lines.append(
            f"_{analysis_path.name} 없음 — 분석 단계가 아직 수행되지 않았거나 실패했습니다._"
        )
    lines.append("")

    # 3) 관련 댓글 (Figma) — 결정적으로 원문 보존 (있는 노드만)
    comments_md = render_comments_for_prd(node_dir)
    if comments_md:
        lines.append(f"### {index}.3 관련 댓글 (Figma)")
        lines.append("")
        lines.append(comments_md)
        lines.append("")

    return anchor, "\n".join(lines)


# 변경 요약 노이즈 필터(구조적·빈도 휴리스틱만 — 프로젝트 고유값 하드코딩 금지).
SUMMARY_REPEAT_THRESHOLD = 3  # 같은 값이 N회 이상 + 짧은 단일 토큰이면 반복 더미 셀로 간주
SUMMARY_NOISE_PATTERNS = [
    re.compile(r"^\d+([-.]\d+)*$"),    # 번호 뱃지: 1, 1-1, 2.3
    re.compile(r"^.+\(\s*\d+\s*\)$"),  # 트리 카운트 노드: 000팀 (99), 미분류 그룹 (999)
    re.compile(r"\*"),                  # 마스킹 샘플: 송*섭
]


def _is_summary_noise(text: str, total: int) -> bool:
    """요약에서 접을 노이즈인지 판정. 구조적 패턴 또는 반복-짧은토큰(테이블 더미 셀)."""
    for pat in SUMMARY_NOISE_PATTERNS:
        if pat.search(text):
            return True
    if total >= SUMMARY_REPEAT_THRESHOLD and (" " not in text) and len(text) <= 16:
        return True
    return False


def build_changes_section(summary: dict[str, Any]) -> str:
    """extract 단계가 결정적으로 감지한 변경/추가/수정 표시를 노드 링크와 함께 취합.

    큰 변경 박스가 테이블 전체를 덮으면 그 안의 더미 셀까지 태깅되므로, 요약 단계에서
    (a) 중복 제거 (b) 구조적·반복 노이즈 필터 를 적용해 의미 있는 변경분만 신호로 남기고
    나머지는 말미에 '기타 N건' 한 줄로 접는다. (원본 마커는 각 노드 texts.md 에 그대로 보존)
    """
    # 1) (label, text) 단위로 전역 집계: 등장 횟수 + 등장 노드 링크(중복 제거, 순서 유지)
    totals: dict[tuple[str, str], int] = {}
    order: list[tuple[str, str]] = []
    node_links: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for n in summary.get("nodes") or []:
        anchor = f"node-{safe_node_id(n['node_id'])}"
        for ch in n.get("changes") or []:
            text = " ".join((ch.get("text") or "").split())
            if len(text) < 2 or text.isdigit():
                continue
            key = (ch["label"], text)
            totals[key] = totals.get(key, 0) + 1
            if key not in node_links:
                node_links[key] = []
                order.append(key)
            link = (n["label"], anchor)
            if link not in node_links[key]:
                node_links[key].append(link)

    # 2) 고유 항목을 신호/노이즈로 분류. 신호는 항목당 1줄(등장 노드 모두 링크),
    #    노이즈는 말미에 건수·고유종수로 접는다.
    signal: list[str] = []
    noise_total = 0
    noise_types = 0
    for key in order:
        label, text = key
        if _is_summary_noise(text, totals[key]):
            noise_total += totals[key]
            noise_types += 1
            continue
        disp = text if len(text) <= 120 else text[:120] + "…"
        links = ", ".join(f"[{nl}](#{a})" for nl, a in node_links[key])
        signal.append(f"- `[{label}]` {disp} → {links}")

    if not signal and noise_total == 0:
        return "_자동 감지된 변경/추가/수정 표시 없음._"

    out = list(signal)
    if noise_total:
        out.append("")
        out.append(
            f"> 그 외 UI 노이즈/반복 더미 **{noise_total}건**(고유 {noise_types}종) 제외 "
            "— 더미 셀 값·트리 카운트 노드·번호 뱃지·마스킹 샘플. 원본 마커는 각 노드 `texts.md` 참조."
        )
    return "\n".join(out)


def build_prd(summary: dict[str, Any], mode: str) -> str:
    file_key = summary["file_key"]
    context = summary.get("context") or ""
    nodes = summary["nodes"]
    # 이미지·로컬경로 링크는 PRD .md 가 놓이는 디렉터리(노드 디렉터리들의 공통 부모) 기준
    # 상대경로로 만든다. output_dir(상위) 기준이면 task 하위에 쓰인 PRD 와 어긋나 이중 중첩됨.
    prd_root = Path(nodes[0]["node_dir"]).parent if nodes else Path(summary["output_dir"])

    title = context or file_key
    generated_at = datetime.datetime.now().astimezone().isoformat()
    figma_url = f"https://www.figma.com/design/{file_key}"

    sections: list[str] = []
    toc_lines: list[str] = []
    texts_paths: list[Path] = []
    for i, node_entry in enumerate(nodes, start=1):
        anchor, sec = render_node_section(i, file_key, node_entry, mode, prd_root)
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
        f"- `{n['node_id']}` — label: {n['label']} / texts: {n['text_count']} / "
        f"images: {n['image_count']} / changes: {len(n.get('changes') or [])} / "
        f"comments: {n.get('comment_count', 0)}"
        for n in nodes
    )

    template = (TEMPLATE_DIR / f"prd.{mode}.template.md").read_text(encoding="utf-8")
    return (
        template.replace("{{TITLE}}", title)
        .replace("{{GENERATED_AT}}", generated_at)
        .replace("{{FIGMA_FILE_URL}}", figma_url)
        .replace("{{NODE_COUNT}}", str(len(nodes)))
        .replace("{{CONTEXT}}", context or "_없음_")
        .replace("{{CHANGES}}", build_changes_section(summary))
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
    prd_dir_name = resolve_prd_dir_name(cfg)
    print(f"[synthesize] config: {cfg_path}", file=sys.stderr)
    print(f"[synthesize] output_dir: {output_dir}", file=sys.stderr)
    print(f"[synthesize] prd_dir_name: {prd_dir_name}", file=sys.stderr)
    file_root = output_dir / prd_dir_name

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
