#!/usr/bin/env python3
"""figma-prd 스킬 — 추출 단계.

Figma REST API로 지정 노드들의 트리·텍스트·이미지를 결정적으로 수집한다.
``page info`` 프레임은 본문 texts에서 빼고 ``page_info`` 메타 dict로 별도 수집한다
(노드 섹션 상단 "페이지 메타" 표시용). 그 외 노드는 ``exclude_node_ids`` 와
``visible=false`` 필터만 적용하고, 트리 그대로 ``texts.md`` 로 직렬화한다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

FIGMA_API = "https://api.figma.com/v1"

# 페이지 메타: 자기 자신은 보존하되 본문 texts에서는 빠진다.
PAGE_INFO_FRAME_NAMES = {"page info", "Page info"}


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
    """--config 인자가 없으면 cwd → git 루트 순으로 figma-prd.config.json 탐색."""
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
    """output_dir 결정 우선순위:

    1. config의 ``output_dir`` 절대 경로 → 그대로.
    2. config의 ``output_dir`` 상대 경로 → config 파일 디렉터리 기준.
    3. 명시 없음 → git 프로젝트 루트의 ``docs/prd-out``. git이 아니면 config 디렉터리.
    """
    raw = cfg.get("output_dir")
    config_dir = config_path.parent.resolve()
    if raw:
        p = Path(raw)
        return p.resolve() if p.is_absolute() else (config_dir / p).resolve()
    project_root = find_project_root(config_dir)
    return (project_root / "docs" / "prd-out").resolve()


def resolve_prd_dir_name(cfg: dict[str, Any]) -> str:
    """PRD 출력 디렉터리 이름. task_name 명시 시 그것을, 없으면 file_key fallback."""
    return cfg.get("task_name") or cfg["file_key"]


def http_get(url: str, headers: dict[str, str] | None = None) -> bytes:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def figma_get(path: str, token: str) -> dict[str, Any]:
    body = http_get(FIGMA_API + path, {"X-Figma-Token": token})
    return json.loads(body)


def safe_node_id(node_id: str) -> str:
    return node_id.replace(":", "-")


def parse_node_id(url_or_id: str) -> str:
    """Figma URL의 node-id 또는 'A:B'/'A-B' 형식을 'A:B'로 정규화."""
    if "node-id=" in url_or_id:
        query = urllib.parse.urlparse(url_or_id).query
        raw = urllib.parse.parse_qs(query).get("node-id", [None])[0]
        if raw is None:
            raise ValueError(f"node-id missing: {url_or_id}")
        return raw.replace("-", ":")
    return url_or_id.replace("-", ":")


def has_image_fill(node: dict[str, Any]) -> bool:
    fills = node.get("fills") or []
    return any(isinstance(f, dict) and f.get("type") == "IMAGE" for f in fills)


def extract_page_info(node: dict[str, Any]) -> dict[str, str]:
    """``page info`` 프레임에서 라벨(weight≥700) / 값(weight<700) 페어를 dict로 수집."""
    info: dict[str, str] = {}

    def visit_group(group: dict[str, Any]) -> None:
        label: str | None = None
        value: str | None = None
        for child in group.get("children") or []:
            if child.get("type") != "TEXT":
                continue
            style = child.get("style") or {}
            weight = style.get("fontWeight") or 400
            chars = (child.get("characters") or "").strip()
            if weight >= 700:
                label = chars
            else:
                value = chars
        if label and label.lower() != "page info":
            info[label.lower()] = value or ""

    def walk_for_groups(n: dict[str, Any]) -> None:
        for child in n.get("children") or []:
            name = child.get("name", "")
            if name.startswith("Group "):
                visit_group(child)
            else:
                walk_for_groups(child)

    walk_for_groups(node)
    return info


def walk(
    node: dict[str, Any],
    parent_path: list[str],
    exclude_ids: set[str],
    include_hidden: bool,
    texts: list[dict[str, Any]],
    images: list[str],
    page_info: dict[str, str],
    current_frame_id: str | None,
) -> None:
    node_id = node.get("id", "")
    if node_id in exclude_ids:
        return
    if not include_hidden and node.get("visible") is False:
        return

    name = node.get("name", "")
    node_type = node.get("type", "")

    if name in PAGE_INFO_FRAME_NAMES:
        page_info.update(extract_page_info(node))
        return

    if node_type == "TEXT":
        chars = node.get("characters") or ""
        style = node.get("style") or {}
        texts.append(
            {
                "id": node_id,
                "path": list(parent_path),
                "name": name,
                "characters": chars,
                "font_size": style.get("fontSize"),
                "font_weight": style.get("fontWeight"),
                "parent_frame_id": current_frame_id,
            }
        )

    if has_image_fill(node) and node_id:
        images.append(node_id)

    next_path = parent_path + ([name] if name and node_type != "TEXT" else [])
    new_frame_id = current_frame_id if node_type == "TEXT" else (node_id or current_frame_id)
    for child in node.get("children") or []:
        walk(
            child,
            next_path,
            exclude_ids,
            include_hidden,
            texts,
            images,
            page_info,
            new_frame_id,
        )


def render_texts_md(label: str, node_id: str, texts: list[dict[str, Any]]) -> str:
    lines = [
        f"# {label}",
        "",
        f"_Figma 노드 ID: `{node_id}` · 텍스트 노드 {len(texts)}개_",
        "",
    ]
    last_path: tuple[str, ...] = ()
    for t in texts:
        path = tuple(t["path"])
        if path != last_path:
            heading = " / ".join(path) if path else "(root)"
            lines.append("")
            lines.append(f"## {heading}")
            lines.append("")
            last_path = path

        chars = t.get("characters") or ""
        weight = t.get("font_weight") or 400
        size = t.get("font_size")
        meta = f"_(node `{t['id']}` · size={size} · weight={weight})_"

        if "\n" in chars:
            lines.append(f"- {meta}")
            lines.append("  ```")
            for line in chars.splitlines():
                lines.append("  " + line)
            lines.append("  ```")
        else:
            emphasized = f"**{chars}**" if weight >= 700 else chars
            lines.append(f"- {emphasized} {meta}")
    lines.append("")
    return "\n".join(lines)


def fetch_node_tree(file_key: str, node_id: str, token: str) -> dict[str, Any]:
    enc = urllib.parse.quote(node_id, safe="")
    return figma_get(f"/files/{file_key}/nodes?ids={enc}", token)


def fetch_image_urls(
    file_key: str, node_ids: list[str], token: str, scale: int = 2
) -> dict[str, str]:
    if not node_ids:
        return {}
    enc = ",".join(urllib.parse.quote(nid, safe="") for nid in node_ids)
    data = figma_get(f"/images/{file_key}?ids={enc}&format=png&scale={scale}", token)
    return data.get("images", {}) or {}


def download_to(url: str, dest: Path) -> None:
    if not url:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(http_get(url))


def process_node(
    file_key: str,
    prd_dir_name: str,
    node_cfg: dict[str, Any],
    output_dir: Path,
    token: str,
    include_hidden: bool,
) -> dict[str, Any]:
    node_id = parse_node_id(node_cfg["id"])
    label = node_cfg.get("label", node_id)
    exclude_ids = {parse_node_id(x) for x in (node_cfg.get("exclude_node_ids") or [])}

    node_dir = output_dir / prd_dir_name / safe_node_id(node_id)
    (node_dir / "images").mkdir(parents=True, exist_ok=True)

    print(f"[extract] node {node_id} ({label})", file=sys.stderr)

    tree = fetch_node_tree(file_key, node_id, token)
    (node_dir / "tree.json").write_text(
        json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    document = ((tree.get("nodes") or {}).get(node_id) or {}).get("document") or {}
    texts: list[dict[str, Any]] = []
    images: list[str] = []
    page_info: dict[str, str] = {}
    walk(
        document,
        [],
        exclude_ids,
        include_hidden,
        texts,
        images,
        page_info,
        current_frame_id=None,
    )

    if page_info:
        (node_dir / "page_info.json").write_text(
            json.dumps(page_info, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    (node_dir / "texts.md").write_text(
        render_texts_md(label, node_id, texts), encoding="utf-8"
    )

    snap = fetch_image_urls(file_key, [node_id], token, scale=2)
    if snap.get(node_id):
        download_to(snap[node_id], node_dir / "screenshot.png")
    else:
        print(f"[extract]   WARN: screenshot URL missing for {node_id}", file=sys.stderr)

    if images:
        urls = fetch_image_urls(file_key, images, token, scale=2)
        for img_id, url in urls.items():
            if url:
                download_to(url, node_dir / "images" / f"{safe_node_id(img_id)}.png")

    print(
        f"[extract]   texts={len(texts)} images={len(images)} "
        f"page_info_keys={list(page_info.keys()) or '-'} → {node_dir}",
        file=sys.stderr,
    )

    return {
        "node_id": node_id,
        "label": label,
        "node_dir": str(node_dir),
        "text_count": len(texts),
        "image_count": len(images),
        "exclude_node_ids": sorted(exclude_ids),
        "exclude_notes": node_cfg.get("exclude_notes") or [],
        "page_info": page_info,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Figma 노드 추출 (text/image + page_info)")
    parser.add_argument(
        "--config",
        default=None,
        help="figma-prd.config.json 경로 (생략 시 cwd 또는 git 루트에서 자동 탐색)",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="visible=false 노드도 포함 (기본 제외)",
    )
    args = parser.parse_args()

    cfg_path = discover_config(args.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    token = os.environ.get("FIGMA_TOKEN") or cfg.get("figma_token")
    if not token:
        print(
            "ERROR: FIGMA_TOKEN 환경 변수 또는 config.figma_token 필드가 필요합니다.",
            file=sys.stderr,
        )
        sys.exit(2)
    file_key = cfg["file_key"]
    output_dir = resolve_output_dir(cfg, cfg_path)
    prd_dir_name = resolve_prd_dir_name(cfg)
    print(f"[extract] config: {cfg_path}", file=sys.stderr)
    print(f"[extract] output_dir: {output_dir}", file=sys.stderr)
    print(f"[extract] prd_dir_name: {prd_dir_name}", file=sys.stderr)
    nodes = cfg.get("nodes") or []
    if not nodes:
        print("ERROR: config.nodes가 비어 있습니다.", file=sys.stderr)
        sys.exit(2)

    summary: list[dict[str, Any]] = []
    for node_cfg in nodes:
        summary.append(
            process_node(file_key, prd_dir_name, node_cfg, output_dir, token, args.include_hidden)
        )

    summary_path = output_dir / prd_dir_name / "extract.summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "file_key": file_key,
                "mode": cfg.get("mode"),
                "context": cfg.get("context"),
                "output_dir": str(output_dir),
                "nodes": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[extract] DONE → {summary_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
