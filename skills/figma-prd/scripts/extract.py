#!/usr/bin/env python3
"""figma-prd 스킬 — 추출 단계.

Figma REST API로 지정 노드들의 트리·텍스트·이미지를 결정적으로 수집해
출력 디렉터리에 저장한다. 멀티모달 분석은 이 스크립트가 하지 않는다 — 그 단계는
스킬 컨트롤러가 Agent 도구로 위임한다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

FIGMA_API = "https://api.figma.com/v1"


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


def walk(
    node: dict[str, Any],
    parent_path: list[str],
    exclude_ids: set[str],
    include_hidden: bool,
    texts: list[dict[str, Any]],
    images: list[str],
) -> None:
    node_id = node.get("id", "")
    if node_id in exclude_ids:
        return
    if not include_hidden and node.get("visible") is False:
        return

    name = node.get("name", "")
    node_type = node.get("type", "")

    if node_type == "TEXT":
        style = node.get("style") or {}
        texts.append(
            {
                "id": node_id,
                "path": list(parent_path),
                "name": name,
                "characters": node.get("characters", ""),
                "font_size": style.get("fontSize"),
                "font_weight": style.get("fontWeight"),
            }
        )

    if has_image_fill(node) and node_id:
        images.append(node_id)

    next_path = parent_path + ([name] if name and node_type != "TEXT" else [])
    for child in node.get("children") or []:
        walk(child, next_path, exclude_ids, include_hidden, texts, images)


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
    node_cfg: dict[str, Any],
    output_dir: Path,
    token: str,
    include_hidden: bool,
) -> dict[str, Any]:
    node_id = parse_node_id(node_cfg["id"])
    label = node_cfg.get("label", node_id)
    exclude_ids = {parse_node_id(x) for x in (node_cfg.get("exclude_node_ids") or [])}

    node_dir = output_dir / file_key / safe_node_id(node_id)
    (node_dir / "images").mkdir(parents=True, exist_ok=True)

    print(f"[extract] node {node_id} ({label})", file=sys.stderr)

    tree = fetch_node_tree(file_key, node_id, token)
    (node_dir / "tree.json").write_text(
        json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    document = ((tree.get("nodes") or {}).get(node_id) or {}).get("document") or {}
    texts: list[dict[str, Any]] = []
    images: list[str] = []
    walk(document, [], exclude_ids, include_hidden, texts, images)

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
        f"[extract]   texts={len(texts)} images={len(images)} → {node_dir}",
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
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Figma 노드 추출 (text/image)")
    parser.add_argument("--config", required=True, help="figma-prd.config.json 경로")
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="visible=false 노드도 포함 (기본 제외)",
    )
    args = parser.parse_args()

    token = os.environ.get("FIGMA_TOKEN")
    if not token:
        print("ERROR: 환경 변수 FIGMA_TOKEN이 필요합니다.", file=sys.stderr)
        sys.exit(2)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    file_key = cfg["file_key"]
    output_dir = Path(cfg.get("output_dir", "./prd-out")).resolve()
    nodes = cfg.get("nodes") or []
    if not nodes:
        print("ERROR: config.nodes가 비어 있습니다.", file=sys.stderr)
        sys.exit(2)

    summary: list[dict[str, Any]] = []
    for node_cfg in nodes:
        summary.append(
            process_node(file_key, node_cfg, output_dir, token, args.include_hidden)
        )

    summary_path = output_dir / file_key / "extract.summary.json"
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
