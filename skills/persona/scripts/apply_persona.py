#!/usr/bin/env python3
"""입력된 페르소나를 파일 기반 메모리에 기록하거나 제거한다 (프로젝트 영구 적용 전용).

- 기록(set): 페르소나 본문을 stdin 으로 받아 <memory>/persona.md 에 쓰고 MEMORY.md 포인터 갱신.
             (임시 파일을 만들지 않으려고 본문은 파일이 아닌 stdin 으로 받는다.)
- 제거(clear): --clear 로 persona.md 삭제 + MEMORY.md 포인터 제거.

세션 전용 적용/해제는 이 스크립트를 쓰지 않는다 — Claude 가 현재 대화 컨텍스트에서
페르소나를 채택/폐기하기만 하면 된다.
"""
import argparse
import os
import sys

POINTER_KEY = "(persona.md)"  # MEMORY.md 의 persona 포인터 라인을 식별하는 키


def derive_memory_dir():
    """$PWD 를 Claude Code 메모리 slug 로 변환해 메모리 디렉터리 경로를 만든다.

    예: /Users/me/work/proj -> ~/.claude/projects/-Users-me-work-proj/memory
    """
    slug = os.getcwd().replace("/", "-")
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", slug, "memory")


def set_persona(memory_dir, name, body):
    """persona.md 를 덮어쓰고(단일 활성 페르소나) MEMORY.md 포인터를 교체/추가한다."""
    os.makedirs(memory_dir, exist_ok=True)

    persona_md = os.path.join(memory_dir, "persona.md")
    front = (
        "---\n"
        "name: active-persona\n"
        f"description: 현재 적용 중인 어시스턴트 페르소나 — {name}\n"
        "metadata:\n"
        "  type: project\n"
        "---\n\n"
    )
    with open(persona_md, "w", encoding="utf-8") as f:
        f.write(front + body.strip() + "\n")

    pointer = (
        f"- [Persona: {name}](persona.md) — "
        "현재 적용 중인 어시스턴트 페르소나 (세션 시작 시 적용)"
    )
    memory_md = os.path.join(memory_dir, "MEMORY.md")
    if os.path.exists(memory_md):
        with open(memory_md, encoding="utf-8") as f:
            lines = f.read().splitlines()
        out, replaced = [], False
        for line in lines:
            if POINTER_KEY in line:
                if not replaced:  # 첫 매칭만 교체, 나머지 중복 포인터는 제거
                    out.append(pointer)
                    replaced = True
            else:
                out.append(line)
        if not replaced:
            out.append(pointer)
        content = "\n".join(out).rstrip() + "\n"
    else:
        content = "# Memory Index\n\n" + pointer + "\n"
    with open(memory_md, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"적용 완료: '{name}'")
    print(f"  - 페르소나 파일: {persona_md}")
    print(f"  - 인덱스 갱신: {memory_md}")


def clear_persona(memory_dir):
    """persona.md 를 지우고 MEMORY.md 의 persona 포인터 라인을 제거한다."""
    persona_md = os.path.join(memory_dir, "persona.md")
    memory_md = os.path.join(memory_dir, "MEMORY.md")
    removed = []

    if os.path.exists(persona_md):
        os.remove(persona_md)
        removed.append(persona_md)

    if os.path.exists(memory_md):
        with open(memory_md, encoding="utf-8") as f:
            lines = f.read().splitlines()
        kept = [ln for ln in lines if POINTER_KEY not in ln]
        if len(kept) != len(lines):
            with open(memory_md, "w", encoding="utf-8") as f:
                f.write("\n".join(kept).rstrip() + "\n")
            removed.append(f"{memory_md} (포인터 제거)")

    if removed:
        print("프로젝트 페르소나 해제 완료:")
        for r in removed:
            print(f"  - {r}")
    else:
        print("해제할 프로젝트 페르소나가 없음 (이미 없음).")


def main():
    ap = argparse.ArgumentParser(description="페르소나를 파일 기반 메모리에 기록/제거")
    ap.add_argument("--clear", action="store_true", help="프로젝트 저장 페르소나 제거")
    ap.add_argument("--name", help="페르소나 이름 (set 모드 필수; MEMORY.md 포인터에 사용)")
    ap.add_argument("--memory-dir", default=None, help="메모리 디렉터리 (생략 시 $PWD 로 도출)")
    args = ap.parse_args()

    memory_dir = args.memory_dir or derive_memory_dir()

    if args.clear:
        clear_persona(memory_dir)
        return

    if not args.name:
        sys.exit("set 모드에는 --name 이 필요함")
    body = sys.stdin.read()
    if not body.strip():
        sys.exit("페르소나 본문이 stdin 으로 들어오지 않음")
    set_persona(memory_dir, args.name, body)


if __name__ == "__main__":
    main()
