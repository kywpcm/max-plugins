#!/usr/bin/env python3
"""reconcile.py — Claude Code 환경 양방향 reconcile 엔진.

repo(max-plugins)와 라이브 환경(~/.claude) 사이를 3-way(BASE/LIVE/REPO)로 비교해
각 아티팩트를 pull/push/noop/converged/conflict로 분류하고, 결정에 따라 적용한다.

BASE  = 이 머신이 마지막으로 reconcile을 끝낸 repo 커밋(`git show <base>:dotfiles/X`)
REPO  = pull 후 현재 repo 워킹트리(dotfiles/X)
LIVE  = ~/.claude/X (settings는 sync-fields 5필드 subset + sync-exclude 제외 플러그인 필터)

동기화 대상(결정적 파일만):
  - settings.json  → 5개 필드(sync-fields.json) 각각 필드 단위 3-way
  - CLAUDE.md
  - statusline-command.sh
  - hooks/scripts/*.sh  (base/repo/live 이름 union)
known_marketplaces.json / installed_plugins.json 은 reconcile 대상이 아니다(파생 상태).

서브커맨드:
  classify  --repo DIR --base SHA            → 분류 결과 JSON(read-only)
  show      --repo DIR --base SHA --key KEY  → 특정 항목의 base/live/repo 내용(충돌 제시용)
  apply     --repo DIR --base SHA [--mode auto|pull|push] [--resolve KEY=live|repo ...]
                                             → 적용 후 결과 JSON. live 쓰기는 .bak 백업.
  base-get  [--home DIR]                     → 저장된 base JSON(없으면 {})
  base-set  --sha SHA --repo DIR [--home DIR]→ base 파일 기록(lastReconcileAt은 --at로 주입)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

FIXED_FILES = ["CLAUDE.md", "statusline-command.sh"]  # 전체 파일 동기화 대상
HOOK_DIR_REL = "hooks/scripts"                          # repo: dotfiles/hooks/scripts, live: ~/.claude/hooks/scripts
SETTINGS = "settings.json"
BASE_FILENAME = ".max-env-base.json"


# ---------- 경로 ----------
def home_dir(args):
    return os.path.abspath(args.home) if getattr(args, "home", None) else os.path.expanduser("~")


def repo_rel(art):
    """아티팩트 키 → repo 내 상대경로(dotfiles/ 기준)."""
    return f"dotfiles/{art}"


def live_path(home, art):
    return os.path.join(home, ".claude", art)


def repo_path(repo, art):
    return os.path.join(repo, repo_rel(art))


# ---------- 입출력 ----------
def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def git_show(repo, sha, relpath):
    """`git show <sha>:<relpath>` 내용(없으면 None)."""
    if not sha:
        return None
    try:
        out = subprocess.run(
            ["git", "-C", repo, "show", f"{sha}:{relpath}"],
            capture_output=True, check=True,
        )
        return out.stdout.decode("utf-8")
    except subprocess.CalledProcessError:
        return None


def load_json_cfg(repo, name):
    with open(os.path.join(repo, "dotfiles", name), "r", encoding="utf-8") as f:
        return json.load(f)


def canon(value):
    """JSON 값 정규화 비교용 문자열(없으면 None)."""
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


# ---------- settings subset ----------
def excluded_plugins(repo):
    try:
        return set(load_json_cfg(repo, "sync-exclude.json").get("plugins", []))
    except FileNotFoundError:
        return set()


def excluded_marketplaces(repo):
    try:
        return set(load_json_cfg(repo, "sync-exclude.json").get("marketplaces", []))
    except FileNotFoundError:
        return set()


def sync_fields(repo):
    return load_json_cfg(repo, "sync-fields.json")


def filter_enabled(plugins, excluded):
    """enabledPlugins dict에서 제외 플러그인 제거."""
    if not isinstance(plugins, dict):
        return plugins
    return {k: v for k, v in plugins.items() if k not in excluded}


def filter_marketplaces(mkts, excluded):
    """extraKnownMarketplaces dict에서 제외 마켓 제거."""
    if not isinstance(mkts, dict):
        return mkts
    return {k: v for k, v in mkts.items() if k not in excluded}


def live_settings_subset(home, fields, excluded, excluded_mkts=frozenset()):
    """라이브 settings.json에서 sync 대상 필드만 + enabledPlugins/extraKnownMarketplaces 제외필터."""
    raw = read_text(live_path(home, SETTINGS))
    if raw is None:
        return {}
    data = json.loads(raw)
    sub = {k: data[k] for k in fields if k in data}
    if "enabledPlugins" in sub:
        sub["enabledPlugins"] = filter_enabled(sub["enabledPlugins"], excluded)
    if "extraKnownMarketplaces" in sub:
        sub["extraKnownMarketplaces"] = filter_marketplaces(sub["extraKnownMarketplaces"], excluded_mkts)
    return sub


def repo_settings(repo):
    raw = read_text(repo_path(repo, SETTINGS))
    return json.loads(raw) if raw is not None else {}


def base_settings(repo, base):
    raw = git_show(repo, base, repo_rel(SETTINGS))
    return json.loads(raw) if raw is not None else {}


# ---------- 아티팩트 열거 ----------
def hook_names(repo, base):
    names = set()
    # repo 워킹트리
    d = os.path.join(repo, "dotfiles", HOOK_DIR_REL)
    if os.path.isdir(d):
        names |= {n for n in os.listdir(d) if n.endswith(".sh")}
    # base (git)
    try:
        out = subprocess.run(
            ["git", "-C", repo, "ls-tree", "--name-only", base, f"dotfiles/{HOOK_DIR_REL}/"],
            capture_output=True, check=True,
        )
        for line in out.stdout.decode("utf-8").splitlines():
            b = os.path.basename(line.strip())
            if b.endswith(".sh"):
                names.add(b)
    except subprocess.CalledProcessError:
        pass
    return names


def live_hook_names(home):
    d = live_path(home, HOOK_DIR_REL)
    if os.path.isdir(d):
        return {n for n in os.listdir(d) if n.endswith(".sh")}
    return set()


# ---------- 3-way 판정 ----------
def classify_triple(base, live, repo):
    """base/live/repo(각각 비교가능 값 또는 None) → 상태."""
    if live == repo:
        return "noop" if live == base else "converged"
    # live != repo
    if live == base:
        return "pull"      # repo만 변경
    if repo == base:
        return "push"      # live만 변경
    return "conflict"      # 양쪽 다르게 변경


def file_triple(repo, base, home, art):
    return (
        git_show(repo, base, repo_rel(art)),
        read_text(live_path(home, art)),
        read_text(repo_path(repo, art)),
    )


def build_items(repo, base, home):
    """모든 아티팩트의 (key, kind, state, payload) 목록."""
    fields = sync_fields(repo)
    excluded = excluded_plugins(repo)
    excluded_mkts = excluded_marketplaces(repo)
    items = []

    # settings.json — 필드 단위
    b_set, l_set, r_set = base_settings(repo, base), live_settings_subset(home, fields, excluded, excluded_mkts), repo_settings(repo)
    for fld in fields:
        b, l, r = canon(b_set.get(fld)), canon(l_set.get(fld)), canon(r_set.get(fld))
        items.append({
            "key": f"{SETTINGS}#{fld}", "kind": "settings", "field": fld,
            "state": classify_triple(b, l, r),
        })

    # 고정 파일
    for art in FIXED_FILES:
        b, l, r = file_triple(repo, base, home, art)
        items.append({"key": art, "kind": "file", "art": art, "state": classify_triple(b, l, r)})

    # hook 스크립트 (union)
    for name in sorted(hook_names(repo, base) | live_hook_names(home)):
        art = f"{HOOK_DIR_REL}/{name}"
        b, l, r = file_triple(repo, base, home, art)
        items.append({"key": art, "kind": "file", "art": art, "state": classify_triple(b, l, r)})

    return items


# ---------- 적용 ----------
def backup(path):
    if os.path.isfile(path):
        shutil.copy2(path, path + ".bak")


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def chmod_x(path):
    if os.path.isfile(path):
        st = os.stat(path).st_mode
        os.chmod(path, st | 0o111)


def action_for(item, mode, resolutions):
    """item → 'pull' | 'push' | 'skip'."""
    state = item["state"]
    if mode == "pull":
        return "skip" if state in ("noop", "converged") else "pull"
    if mode == "push":
        return "skip" if state in ("noop", "converged") else "push"
    # auto
    if state in ("noop", "converged"):
        return "skip"
    if state in ("pull", "push"):
        return state
    # conflict
    choice = resolutions.get(item["key"])
    if choice == "live":
        return "push"
    if choice == "repo":
        return "pull"
    return "skip"


def apply(args):
    repo, base, home = args.repo, args.base, home_dir(args)
    resolutions = dict(r.split("=", 1) for r in (args.resolve or []))
    items = build_items(repo, base, home)
    fields = sync_fields(repo)
    excluded = excluded_plugins(repo)
    excluded_mkts = excluded_marketplaces(repo)

    report = {"pulled": [], "pushed": [], "deleted_live": [], "deleted_repo": [],
              "skipped": [], "unresolved_conflicts": []}

    # settings 필드 작업을 모아 한 번에 read-modify-write
    live_field_pulls = {}   # fld -> repo value (repo→live)
    repo_field_pushes = {}  # fld -> live value (live→repo)

    for it in items:
        act = action_for(it, args.mode, resolutions)
        if act == "skip":
            if it["state"] == "conflict":
                report["unresolved_conflicts"].append(it["key"])
            else:
                report["skipped"].append(it["key"])
            continue

        if it["kind"] == "settings":
            fld = it["field"]
            if act == "pull":
                live_field_pulls[fld] = repo_settings(repo).get(fld)
                report["pulled"].append(it["key"])
            else:  # push
                repo_field_pushes[fld] = live_settings_subset(home, fields, excluded, excluded_mkts).get(fld)
                report["pushed"].append(it["key"])
            continue

        # file 아티팩트
        art = it["art"]
        lp, rp = live_path(home, art), repo_path(repo, art)
        if act == "pull":
            content = read_text(rp)
            if content is None:        # repo에서 삭제됨 → live 삭제
                if os.path.isfile(lp):
                    backup(lp)
                    os.remove(lp)
                    report["deleted_live"].append(it["key"])
            else:
                backup(lp)
                write_file(lp, content)
                if art.endswith(".sh"):
                    chmod_x(lp)
                report["pulled"].append(it["key"])
        else:  # push
            content = read_text(lp)
            if content is None:        # live에서 삭제됨 → repo 삭제
                if os.path.isfile(rp):
                    os.remove(rp)
                    report["deleted_repo"].append(it["key"])
            else:
                write_file(rp, content)
                report["pushed"].append(it["key"])

    # settings 적용 (live)
    if live_field_pulls:
        lp = live_path(home, SETTINGS)
        raw = read_text(lp)
        data = json.loads(raw) if raw is not None else {}
        backup(lp)
        for fld, val in live_field_pulls.items():
            if val is None:
                data.pop(fld, None)
            elif fld == "enabledPlugins":
                # repo값(제외 없음) + 라이브의 제외 플러그인 보존
                live_now = data.get("enabledPlugins", {})
                live_now = live_now if isinstance(live_now, dict) else {}
                merged = filter_enabled(val, excluded)
                for pid in excluded:
                    if pid in live_now:
                        merged[pid] = live_now[pid]
                data["enabledPlugins"] = merged
            elif fld == "extraKnownMarketplaces":
                # repo값(제외 없음) + 라이브의 제외 마켓 보존
                live_now = data.get("extraKnownMarketplaces", {})
                live_now = live_now if isinstance(live_now, dict) else {}
                merged = filter_marketplaces(val, excluded_mkts)
                for mkt in excluded_mkts:
                    if mkt in live_now:
                        merged[mkt] = live_now[mkt]
                data["extraKnownMarketplaces"] = merged
            else:
                data[fld] = val
        write_file(lp, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # settings 적용 (repo)
    if repo_field_pushes:
        rp = repo_path(repo, SETTINGS)
        data = repo_settings(repo)
        for fld, val in repo_field_pushes.items():
            if val is None:
                data.pop(fld, None)
            elif fld == "enabledPlugins":
                data[fld] = filter_enabled(val, excluded)  # 제외 플러그인 드롭
            elif fld == "extraKnownMarketplaces":
                data[fld] = filter_marketplaces(val, excluded_mkts)  # 제외 마켓 드롭
            else:
                data[fld] = val
        write_file(rp, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    report["repo_changed"] = bool(report["pushed"] or report["deleted_repo"])
    report["live_changed"] = bool(report["pulled"] or report["deleted_live"])
    print(json.dumps(report, indent=2, ensure_ascii=False))


# ---------- read-only 커맨드 ----------
def classify(args):
    items = build_items(args.repo, args.base, home_dir(args))
    summary = {}
    for it in items:
        summary.setdefault(it["state"], []).append(it["key"])
    print(json.dumps({"base_sha": args.base, "items": items, "summary": summary},
                     indent=2, ensure_ascii=False))


def show(args):
    repo, base, home, key = args.repo, args.base, home_dir(args), args.key
    if key.startswith(SETTINGS + "#"):
        fld = key.split("#", 1)[1]
        fields, excluded, excluded_mkts = sync_fields(repo), excluded_plugins(repo), excluded_marketplaces(repo)
        out = {
            "key": key,
            "base": base_settings(repo, base).get(fld),
            "live": live_settings_subset(home, fields, excluded, excluded_mkts).get(fld),
            "repo": repo_settings(repo).get(fld),
        }
    else:
        b, l, r = file_triple(repo, base, home, key)
        out = {"key": key, "base": b, "live": l, "repo": r}
    print(json.dumps(out, indent=2, ensure_ascii=False))


# ---------- base 파일 ----------
def base_path(home):
    return os.path.join(home, ".claude", BASE_FILENAME)


def base_get(args):
    raw = read_text(base_path(home_dir(args)))
    print(raw if raw is not None else "{}")


def base_set(args):
    p = base_path(home_dir(args))
    data = {"baseSha": args.sha, "repoDir": os.path.abspath(args.repo),
            "lastReconcileAt": args.at or "", "schemaVersion": 1}
    write_file(p, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(data, ensure_ascii=False))


# ---------- CLI ----------
def main():
    p = argparse.ArgumentParser(description="Claude Code 환경 양방향 reconcile 엔진")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--repo", required=True)
        sp.add_argument("--base", default="")
        sp.add_argument("--home", default="")

    c = sub.add_parser("classify"); add_common(c); c.set_defaults(fn=classify)
    s = sub.add_parser("show"); add_common(s); s.add_argument("--key", required=True); s.set_defaults(fn=show)
    a = sub.add_parser("apply"); add_common(a)
    a.add_argument("--mode", choices=["auto", "pull", "push"], default="auto")
    a.add_argument("--resolve", action="append", default=[])
    a.set_defaults(fn=apply)
    bg = sub.add_parser("base-get"); bg.add_argument("--home", default=""); bg.set_defaults(fn=base_get)
    bs = sub.add_parser("base-set"); bs.add_argument("--repo", required=True); bs.add_argument("--sha", required=True)
    bs.add_argument("--home", default=""); bs.add_argument("--at", default=""); bs.set_defaults(fn=base_set)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
