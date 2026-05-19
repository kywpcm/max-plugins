#!/usr/bin/env python3
"""figma-prd 스킬 — 추출 단계.

Figma REST API로 지정 노드들의 트리·텍스트·이미지를 결정적으로 수집한다.
다음 4가지는 추출 단계에서 자동 처리되며 config로 노출되지 않는다:

  1. ``page info`` 프레임은 본문에서 빼고 ``page_info`` 메타 dict로 별도 수집.
  2. 노이즈 프레임(라디오 데모, 번호 매기기 ellipse 등)은 가지치기.
  3. 푸터·저작권·주소·연락처 같은 텍스트는 휴리스틱으로 스킵하고,
     같은 부모 프레임 안의 다른 텍스트도 함께 제거.
  4. 동일 줄이 5회 이상 반복되는 placeholder는 한 줄로 압축.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

FIGMA_API = "https://api.figma.com/v1"

# 페이지 메타: 자기 자신은 보존하되 본문 texts에서는 빠진다.
PAGE_INFO_FRAME_NAMES = {"page info", "Page info"}

# 가지치기 대상 프레임 이름 패턴.
NOISE_FRAME_PATTERNS = [
    re.compile(r"^라디오 조합$"),
    re.compile(r"^Group 1000001436$"),  # 번호 매기기 ellipse 래퍼 (안에 "1","2","3" 단일 숫자)
]

# 텍스트 노드 자체를 스킵하는 휴리스틱.
NOISE_TEXT_PATTERNS = [
    re.compile(r"Copyright"),
    re.compile(r"All rights reserved", re.IGNORECASE),
    re.compile(r"Cheonan-Si", re.IGNORECASE),
    re.compile(
        r"^\s*\(?\d{5}\)?\s*"
        r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
    ),
    re.compile(r"\d{2,4}-\d{3,4}-\d{4}.*@.*\."),  # 전화+이메일 (예: 031-000-0000(abc@abc.com))
]

# 동일 줄 반복 압축 임계치.
REPEAT_THRESHOLD = 5


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


def is_noise_frame(name: str) -> bool:
    if not name:
        return False
    return any(p.match(name) for p in NOISE_FRAME_PATTERNS)


def is_noise_text(chars: str | None) -> bool:
    if chars is None:
        return True
    stripped = chars.strip()
    if not stripped:
        return True
    if len(stripped) <= 1 and stripped in {"-", "_", ".", "·"}:
        return True
    return any(p.search(stripped) for p in NOISE_TEXT_PATTERNS)


def compress_repeats(text: str, threshold: int = REPEAT_THRESHOLD) -> str:
    """동일 문장이 threshold회 이상 등장하는 텍스트를 한 줄로 압축."""
    if not text:
        return text
    lines = text.split("\n")
    counter: Counter[str] = Counter(line.strip() for line in lines if line.strip())
    if not counter:
        return text
    top_line, top_count = counter.most_common(1)[0]
    if top_count < threshold:
        return text
    compressed: list[str] = []
    placed = False
    for line in lines:
        if line.strip() == top_line:
            if not placed:
                compressed.append(f"{top_line} (placeholder × {top_count}회 반복)")
                placed = True
        else:
            compressed.append(line)
    return "\n".join(compressed)


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
    noise_frame_ids: set[str],
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

    if is_noise_frame(name):
        return

    if node_type == "TEXT":
        chars = node.get("characters") or ""
        if is_noise_text(chars):
            if current_frame_id:
                noise_frame_ids.add(current_frame_id)
            return
        style = node.get("style") or {}
        texts.append(
            {
                "id": node_id,
                "path": list(parent_path),
                "name": name,
                "characters": compress_repeats(chars),
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
            noise_frame_ids,
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
    page_info: dict[str, str] = {}
    noise_frame_ids: set[str] = set()
    walk(
        document,
        [],
        exclude_ids,
        include_hidden,
        texts,
        images,
        page_info,
        noise_frame_ids,
        current_frame_id=None,
    )

    if noise_frame_ids:
        before = len(texts)
        texts = [t for t in texts if t.get("parent_frame_id") not in noise_frame_ids]
        removed = before - len(texts)
        if removed:
            print(
                f"[extract]   푸터/노이즈 frame 후처리: 텍스트 {removed}건 제거",
                file=sys.stderr,
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
