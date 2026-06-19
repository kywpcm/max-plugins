---
name: reconcile-claude-env
description: >
  현재 머신의 라이브 Claude Code 환경(~/.claude/)과 max-plugins repo를 한 번에 양방향 동기화(reconcile)합니다.
  받을 변경은 받고(pull) 올릴 변경은 올리고(push) 자동 처리하며, 진짜 충돌만 사용자에게 묻습니다.
  여러 머신(회사/홈 등)에서 환경을 맞출 때, sync/apply 순서를 신경쓰지 않고 이 스킬 하나만 호출하면 됩니다.
  "claude 환경 동기화", "claude 환경 맞춰", "환경 reconcile", "env reconcile", "sync claude env", "env sync",
  "apply claude env", "env apply", "머신 간 환경 동기화", "claude 환경 업데이트", "claude 환경 반영",
  "settings.json 동기화", "CLAUDE.md 반영", "훅 동기화", "max-plugins 동기화", "max-plugins 업데이트",
  "새 머신 claude 설정", "claude 환경 설치", "claude 환경 구축", "claude 환경 복원" 시 사용합니다.
  shell/터미널 dotfiles(.zshrc/.tmux.conf 등)가 아닌 Claude Code 환경 전용입니다(그건 sync/apply-dotfiles-env).
  인자: 없음=자동 양방향, "pull"=repo→라이브 강제, "push"=라이브→repo 강제.
user-invocable: true
version: 0.1.0
---

# reconcile-env

라이브 환경(`~/.claude/`)과 max-plugins repo를 **한 번의 호출로 양방향 동기화**한다. 받을 건 받고 올릴 건 올린다. 어느 머신에서 호출하든 동일하게 동작하므로, 더 이상 sync/apply 순서를 신경 쓸 필요가 없다.

## 핵심 원칙

- **3-way reconcile**: `BASE`(이 머신이 마지막으로 reconcile한 repo 커밋) / `LIVE`(~/.claude) / `REPO`(pull 후 repo)를 비교해 방향을 자동 판별. 한쪽만 바뀐 건 자동 pull/push, 양쪽이 같은 항목을 다르게 바꾼 **진짜 충돌만** 사용자에게 묻는다.
- **base 추적**: 머신로컬 파일 `~/.claude/.max-env-base.json`(git 밖이라 머신별)에 마지막 reconcile 커밋 SHA를 저장. 이게 3-way의 공통 조상이다.
- **동기화 대상 = 결정적 파일 4종**: `settings.json`(sync-fields 5필드, 필드 단위), `CLAUDE.md`, `statusline-command.sh`, `hooks/scripts/*.sh`. `known_marketplaces.json`/`installed_plugins.json`은 **대상이 아니다**(파생 상태 — Claude Code가 관리).
- **제외 항목**(`dotfiles/sync-exclude.json`): `plugins`(discord 등)·`marketplaces`(머신 전용 커스텀 마켓)는 양방향에서 제외. `enabledPlugins`/`extraKnownMarketplaces`는 제외 항목의 라이브 상태를 보존(push 시 드롭, pull 시 보존).
- 민감 정보(봇 토큰, 유저 ID)는 절대 커밋하지 않는다.
- 엔진은 `skills/reconcile-claude-env/scripts/reconcile.py`. 이 스킬은 git/플러그인 작업과 충돌 UX·커밋만 담당한다.

## 모드 (인자)

- 인자 없음 → **자동 양방향**(기본).
- `pull` → repo를 이 머신에 강제 적용(옛 apply / 복구 / 새 머신).
- `push` → 이 머신을 repo로 강제 업로드(옛 sync / 복구).

## 새 머신 부트스트랩 (스킬이 없는 상태)

스킬은 자신이 속한 플러그인을 설치할 수 없다. 새 머신에서는 **딱 한 번 수동 2줄**로 플러그인을 깐 뒤 이 스킬을 부른다:

```bash
claude plugin marketplace add --source github:kywpcm/max-plugins
claude plugin install dotfiles-claude-code@max-plugins
```

이후 `reconcile`를 호출하면, base 파일이 없으므로 **bootstrap 흐름**으로 진입한다(아래 Step B-0).

## Workflow

### Step 1: repo 위치 + 스킬 엔진 경로 + 모드

```bash
REPO_DIR=$(find ~/workspace ~/projects ~ -maxdepth 3 -type d -name "max-plugins" 2>/dev/null | head -1)
RECON="$REPO_DIR/skills/reconcile-claude-env/scripts/reconcile.py"
MODE="auto"   # 인자가 pull/push면 그 값으로
```

- `REPO_DIR`를 못 찾으면(새 머신) 사용자에게 클론 위치를 묻거나 `~/workspace/max-plugins`에 클론한다(부트스트랩).
- 인자($ARGUMENTS)가 `pull` 또는 `push`면 `MODE`에 반영.

### Step 2: 워킹트리 clean + 원격 최신화 + 자기 업데이트

```bash
cd "$REPO_DIR"
# 워킹트리가 더러우면 중단(예상치 못한 로컬 변경 보호)
[ -z "$(git status --porcelain)" ] || { echo "repo 워킹트리에 미커밋 변경이 있습니다. 정리 후 다시 실행하세요."; exit 1; }

git pull --ff-only origin master || { echo "ff-only pull 실패(로컬 미푸시 커밋?). 정리 필요."; exit 1; }
claude plugin marketplace update max-plugins 2>&1 | tail -1
claude plugin update dotfiles-claude-code@max-plugins 2>&1 | tail -1
```

- `claude plugin update`가 reconcile 스킬 자신을 바꿔도, **로드된 본문은 재시작 전까지 구버전**이다. 이번 실행은 그대로 완주하고 완료 보고에서 재시작을 권한다.
- 3-way의 REPO는 cache가 아니라 이 workspace clone의 `dotfiles/`다(pull 후 최신).

### Step 3: base 확인 → 분기

```bash
BASE_SHA=$(python3 "$RECON" base-get | python3 -c "import json,sys;print(json.load(sys.stdin).get('baseSha',''))")
```

- `BASE_SHA`가 **비어있으면** → **Step B-0 (bootstrap)**.
- 있으면 → **Step 4 (일반 reconcile)**.
- `MODE`가 `pull`/`push`면 base와 무관하게 **Step 4의 강제 모드**로 진행(분류 없이 차이나는 항목을 한 방향으로).

### Step B-0: bootstrap (base 없음 = 첫 실행)

1. workspace clone이 없으면 클론: `git clone git@github.com:kywpcm/max-plugins.git ~/workspace/max-plugins` (실패 시 https).
2. `claude plugin marketplace update` + `claude plugin update`로 cache 최신화(Step 2와 동일).
3. **라이브에 보존할 로컬 변경이 있는지** 판단: `python3 "$RECON" classify --repo "$REPO_DIR" --base "$(git rev-parse HEAD)"` 를 실행하면, base=HEAD라 라이브와 다른 항목이 `push`로 표시된다(=이 머신에만 있는 차이).
   - 차이가 거의 없음(새 머신) → **`reconcile pull` 흐름**: `install.sh` 실행으로 repo 환경을 시드.
     ```bash
     bash "$REPO_DIR/install.sh"
     ```
   - 라이브에만 있는 의미 있는 차이가 있음(기존 머신이 처음 reconcile 도입) → 사용자에게 차이를 보여주고 **항목별로 pull(repo 채택)/push(로컬 업로드)** 선택받아 `apply`로 반영. push가 생기면 Step 6 커밋.
4. base 기록: `python3 "$RECON" base-set --repo "$REPO_DIR" --sha "$(git rev-parse HEAD)" --at "$(date -u +%FT%TZ)"`.
5. 완료 보고로 종료.

### Step 4: 분류 (read-only)

```bash
python3 "$RECON" classify --repo "$REPO_DIR" --base "$BASE_SHA"
```

출력 JSON의 `summary`로 pull/push/converged/noop/conflict 목록을 파악해 사용자에게 표로 요약한다. settings는 필드 단위(`settings.json#permissions` 등)로 잡힌다.

차이가 전혀 없으면(모두 noop/converged) "이미 동기화됨"을 알리고 base만 갱신(Step 7) 후 종료.

### Step 5: 충돌 해소 (있을 때만)

`conflict` 항목마다 세 버전을 보여주고 선택받는다:

```bash
python3 "$RECON" show --repo "$REPO_DIR" --base "$BASE_SHA" --key "settings.json#hooks"
```

- `[1]` 이 머신 값 채택(push) → `--resolve "KEY=live"`
- `[2]` repo 값 채택(pull) → `--resolve "KEY=repo"`
- `[3]` 건너뜀 → resolve 없음(미적용, base 미전진)

삭제(한쪽에서 파일이 사라진 경우)도 충돌·강제 모드 외에는 항상 사용자 확인 후 진행한다.

### Step 6: 적용

```bash
# 자동 + 충돌 해소 반영 (예시)
python3 "$RECON" apply --repo "$REPO_DIR" --base "$BASE_SHA" --mode "$MODE" \
  --resolve "settings.json#hooks=repo"
```

- 강제 모드면 `--mode pull` 또는 `--mode push`(resolve 불필요).
- 출력 report의 `repo_changed`가 true면 → Step 7(커밋). `live_changed`는 라이브에 반영된 것(`.bak` 백업됨).
- `unresolved_conflicts`가 비어있지 않으면 base를 전진시키지 않는다(Step 7에서 분기).

### Step 7: repo 변경 커밋 (push가 있었을 때만)

`report.repo_changed == true`면:

1. **보안 스캔**:
   ```bash
   grep -rIn "BOT_TOKEN=[^ \"']\|allowFrom.*[0-9]\{5,\}" "$REPO_DIR/dotfiles/" && echo "⚠️ 점검" || echo "ok"
   ```
2. **버전 bump**(dotfiles만 변경 = patch; hook/스킬 등 구조 변경 동반 시 minor): `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json[plugins[0]]`의 `version` 동시 갱신.
3. **커밋·푸시**:
   ```bash
   cd "$REPO_DIR" && git add -A
   git commit -m "reconcile: {올린 항목 요약}"
   git push origin master
   ```

문제 발생 시 `git checkout -- dotfiles/`로 repo 워킹트리 롤백 가능(커밋 전).

### Step 8: base 갱신

미해결 충돌이 없을 때만 base를 현재 HEAD로 전진:

```bash
cd "$REPO_DIR"
python3 "$RECON" base-set --repo "$REPO_DIR" --sha "$(git rev-parse HEAD)" --at "$(date -u +%FT%TZ)"
```

(push해서 새 커밋이 생겼으면 그 커밋, pull만 했으면 origin HEAD가 곧 현재 HEAD.)

### Step 9: 완료 보고

무엇을 pull / push / converged / 충돌(미해결) 했는지 요약한다. `claude plugin update`가 이 스킬을 갱신했으면 `/reload-plugins`(또는 새 세션)를 권한다. 미해결 충돌이 있으면 다음 실행에서 다시 제시됨을 알린다.

## 설계 노트

- **왜 base가 필요한가**: base 없이는 "어느 쪽이 바뀌었는지" 알 수 없어 last-writer-wins로 다른 머신 변경을 조용히 덮는다. base(공통 조상)가 있어야 pull/push를 자동 판별하고 진짜 충돌만 가려낼 수 있다.
- **왜 settings는 필드 단위인가**: 파일 단위면 "회사 머신은 permissions만, 홈 머신은 hooks만" 바꾼 경우를 가짜 충돌로 오탐한다. 필드 단위 3-way면 둘 다 충돌 없이 합쳐진다.
- **왜 known_marketplaces/installed_plugins 제외**: 둘 다 Claude Code가 cache 실물 기준으로 생성하는 파생 상태이고 timestamp churn이 심해 가짜 충돌의 주범이다. 설치 의도는 `enabledPlugins`/`extraKnownMarketplaces`(동기화 settings 필드)에 이미 담긴다.
