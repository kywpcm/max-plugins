---
name: project-discord-setup
description: >
  일반 Claude Code 프로젝트에 디스코드 채널(DM 전용 또는 DM+음성)을 붙일 때 사용한다.
  트리거: "디스코드 채널 붙여", "이 프로젝트에 디스코드", "discord 채널 설정",
  "디스코드 음성 붙여줘", "음성 브릿지 연결", "프로젝트 디스코드 연동",
  "project discord setup", "디스코드 DM 설정", "디스코드 봇 연결",
  "이 프로젝트에서 음성으로 대화", "디스코드로 원격 클로드".
  기존 디스코드 서버에 채널을 추가하는 방식이고, 봇/토큰 발급 같은 브라우저 작업은
  사용자에게 단계별로 안내한 뒤 붙여넣은 값으로 파일을 만든다. 새 서버 생성이나
  access 정책 변경 자체가 목적이면 쓰지 않는다(그건 discord:configure / discord:access).
user-invocable: true
argument-hint: "[dm | voice]"
version: 0.3.0
---

# project-discord-setup

현재 작업 중인 Claude Code 프로젝트에 디스코드 채널을 붙이는 **대화형 마법사**다. 두 가지 구성을 지원한다.

- **DM 전용**: 봇과 1:1 DM으로 원격 Claude와 텍스트 대화. 봇 1개.
- **DM + 음성**: DM 위에 음성 채널을 얹어 STT↔Claude↔TTS 음성 대화. 봇 2개 + voice-bridge pm2 프로세스.

자동화 가능한 부분(파일 생성·검증·pm2 기동)은 스킬이 처리하고, **브라우저에서만 가능한 부분(Developer Portal 봇 생성·토큰 발급·채널/ID 복사)은 사용자에게 안내**한 뒤 붙여넣은 값을 받아 진행한다. 참고 구성: DM 전용 `~/workspace/stock-speciality-team`, 음성 `~/workspace/discord-voice-bridge`.

## 핵심: 두 봇 · 4개 ID (혼동이 1순위 실패 원인)

| 값 | 무엇 | 어디에 저장 |
|---|---|---|
| **봇 #2 토큰** | Claude MCP 봇(응답 본체)의 토큰 | `$PWD/.claude/channels/discord/.env` → `DISCORD_BOT_TOKEN` |
| **봇 #2 user ID** | 〃 의 user ID | voice-bridge env → `CLAUDE_BOT_ID` |
| **봇 #1 토큰** | voice-bridge 봇(STT/TTS)의 토큰 | voice-bridge env → `DISCORD_BOT_TOKEN` |
| **봇 #1 user ID** | 〃 의 user ID | 봇 #2 채널 `.env` → `DISCORD_ALLOW_BOT_IDS` |

봇 #2(Claude MCP)는 DM·음성 둘 다에 필요하고, 봇 #1(voice-bridge)은 음성에만 추가된다. 값을 수집할 때마다 **어느 봇의 무슨 값인지 라벨을 강하게 붙이고**, 받은 뒤 마스킹해서 되읽어 확인한다.

## 흐름

```
0. 사전 점검  →  1. 구성 분기(dm/voice)  →  2. DM 경로  →  (voice면) 3. 음성 경로  →  4. 검증
```

### 0. 사전 점검
- `pwd`로 현재 디렉토리를 보여주고 **"이 프로젝트에 붙이는 게 맞는지"** 확인받는다(서브디렉토리일 수 있으니 `git rev-parse --show-toplevel`로 루트 확인 권장).
- `.claude/channels/discord/.env`가 이미 있으면 "이미 설정됨"을 보고하고 재설정 여부를 묻는다.
- `which direnv` — 없으면 설치 안내(`.envrc`가 무의미해짐).
- **셸 오염 검증**: `env | grep -E 'DISCORD_(BOT_TOKEN|STATE_DIR)'`. 이미 export돼 있으면 프로젝트 `.env`가 무시되니(아래 주의점) 경고한다.

### 1. 구성 분기
`$ARGUMENTS`에 `dm` 또는 `voice`가 오면 그대로 진행. 없으면 AskUserQuestion으로 "DM 전용 / DM+음성"을 묻는다.

## 2. DM 경로

**[수동 1] 봇 #2(Claude MCP 봇) 준비 — 사용자가 브라우저에서:**
1. https://discord.com/developers/applications → "New Application" (이름 예: `claude-<프로젝트명>`)
2. 좌측 **Bot** 탭 → "Reset Token" → 토큰 복사 (1회만 표시!)
3. 같은 Bot 탭에서 **MESSAGE CONTENT INTENT** 토글 ON (필수)
4. **OAuth2 → URL Generator**: Scopes `bot`, Bot Permissions `Send Messages` `Read Message History` `View Channels` → 생성된 URL을 열어 **기존 디스코드 서버**에 초대
   → 끝나면 **봇 #2 토큰**을 붙여넣게 한다.

**[수동 2] 내 user ID** — 설정 → 고급 → 개발자 모드 ON → 내 프로필 우클릭 → "ID 복사".
→ **본인 user ID**를 붙여넣게 한다(봇 ID 아님, 17~20자리 숫자).

**[자동] 스킬이 `$PWD` 기준으로 생성:**
1. `.envrc` — `grep -q DISCORD_STATE_DIR .envrc` 2>/dev/null로 중복 확인 후, 없으면 아래 라인을 append(파일 없으면 생성):
   ```bash
   export DISCORD_STATE_DIR="$PWD/.claude/channels/discord"
   ```
   변경 후 `direnv allow` 실행(또는 사용자에게 안내).
2. `mkdir -p .claude/channels/discord`
3. `.claude/channels/discord/.env` (그 후 `chmod 600`):
   ```
   DISCORD_BOT_TOKEN=<봇#2 토큰>
   ```
4. `.claude/channels/discord/access.json` (2-space indent):
   ```json
   {
     "dmPolicy": "allowlist",
     "allowFrom": ["<내 user id>"],
     "groups": {},
     "pending": {}
   }
   ```
   (user ID를 직접 넣으므로 페어링 단계 생략. user ID를 모르면 `dmPolicy:"pairing"`으로 시작 → 봇에 DM → 받은 코드로 `/discord:access pair <code>` → 그 뒤 allowlist로 잠금.)
5. `.gitignore` — `grep -q '.claude/channels/' .gitignore` 2>/dev/null 확인 후 없으면 파일 끝에 주석 + `.claude/channels/` 라인 append(토큰·allowlist 보호).

**[사용자] 봇 #2 실행 · 검증:**
- **먼저 direnv가 `DISCORD_STATE_DIR`을 export했는지 확인**한다. `.envrc`를 방금 만들었거나 `direnv allow` 직후엔 현재 셸에 아직 반영 안 됐을 수 있으니, **디렉토리를 한 번 벗어났다가 다시 진입**해 direnv를 재로드한다:
  ```bash
  cd .. && cd -                # direnv: loading …/.envrc → "export +DISCORD_STATE_DIR" 확인
  echo "$DISCORD_STATE_DIR"    # 프로젝트의 .claude/channels/discord 경로가 찍혀야 함
  ```
  값이 비어 있으면 discord MCP가 글로벌 STATE_DIR(`~/.claude/channels/discord`)을 읽어 **프로젝트 봇 토큰을 못 찾는다**(봇 #2가 엉뚱한 토큰/무토큰으로 떠 실패).
- 그 다음 **대상 프로젝트 디렉토리에서 채널 모드로 Claude Code를 띄운다**:
  ```bash
  clauded --channels plugin:discord@claude-plugins-official
  ```
  `clauded`는 `claude --dangerously-skip-permissions` alias다(alias 없으면 `claude --dangerously-skip-permissions --channels plugin:discord@claude-plugins-official`). 원격(디스코드)에선 권한 모달을 못 푸므로 bypassPermissions로 띄운다(음성 워크플로 정신).
- 이미 채널 모드로 떠 있는 세션이면 `/reload-plugins`로 새 토큰을 로드 — server.ts는 토큰을 **부팅 시 1회만** 읽으므로 필수.
- 디스코드에서 **봇 #2에게 DM** 전송 → Claude 응답이 오면 DM 구성 완료(봇 #2 토큰 정확성까지 검증됨).

DM 전용이면 여기서 끝. 음성이면 3으로.

## 3. 음성 경로 (DM 경로 완료 후 이어서)

먼저 **프로젝트명 `PROJ`를 정한다**: 현재 디렉토리 basename(`basename "$PWD"`)을 기본값으로 보여주고 확인/수정받는다. `PROJ`는 voice-bridge env 파일명·pm2 app 이름에 쓰이므로 영문/숫자/하이픈만 허용.

**공유 API 키 (프로젝트 불변 — repo에 절대 안 넣음)**: `SONIOX_API_KEY`·`HUME_API_KEY`·`OPENAI_API_KEY`는 모든 음성 인스턴스가 **같은 계정 키를 공유**한다(프로젝트마다 다르지 않다). ⚠️ **public 플러그인 repo·스킬·seed에 하드코딩하면 그대로 유출되므로 절대 넣지 않는다.** 대신 로컬 기존 설정에서 자동으로 끌어온다:
- 출처 우선순위: `~/.config/voice-bridge/shared-keys.env` → `~/workspace/discord-voice-bridge/.env` → `~/workspace/discord-voice-bridge/envs/*.env`(가장 최근).
- 스킬은 처음 발견되는 출처에서 세 키를 `grep`해 새 env에 주입한다. 어디에도 없으면(최초 구성) 사용자에게 **1회만** 입력받아 `~/.config/voice-bridge/shared-keys.env`(`chmod 600`, repo 밖)에 저장 → 이후 모든 프로젝트는 자동.
- 따라서 사용자가 매번 넣는 값은 **프로젝트별로 다른 것만**: 봇 #1 토큰, 봇 #1/#2 user ID, 채널 ID 2개.

**[수동 1] 채널 2개 생성** — 기존 서버에 채널 2개를 만든다. **새 서버는 만들지 않는다**(봇이 프로젝트마다 달라 한 서버에서 음성 채널 여러 개 동시 운영 가능). 각 채널 우클릭 → "ID 복사". 둘을 섞지 않게 라벨을 분명히:
- **텍스트 채널**(중계 통로, 예 `#<PROJ>-bridge`) → `TEXT_CHANNEL_ID`
- **음성 채널**(예 🔊 `<PROJ>-voice`) → `VOICE_CHANNEL_ID`

**[수동 2] 봇 #1(voice-bridge 봇) 새로 생성** — 봇 #2와 **별개의 새 Application**:
- Bot 탭 → Reset Token → 토큰 복사
- **MESSAGE CONTENT INTENT + SERVER MEMBERS INTENT** ON
- OAuth2 권한: `bot` + `Connect` `Speak` `View Channels` `Send Messages` `Read Message History` → **같은 서버**에 초대
- 서버 멤버 목록에서 봇 #1 우클릭 → "ID 복사"
→ **봇 #1 토큰, 봇 #1 user ID, 봇 #2 user ID**(서버에서 봇 #2 우클릭 → ID 복사) 수집. **API 키(Soniox/Hume/OpenAI)는 위 '공유 API 키' 출처에서 자동 주입** — 최초 구성 때만 1회 입력한다. `USER_ID`(선택, 입퇴장 자동 토글)만 필요 시 받는다.

**[수동 3] 두 채널 권한에 봇 #1 추가 — ⚠️ 빠지면 음성이 *조용히* 깨진다(실전 검증된 필수 단계):**
OAuth 초대는 **길드(서버) 단위** 권한만 준다. 채널이 비공개거나 **카테고리에 권한 오버라이드**가 걸려 있으면 봇은 그 채널에 **접근조차 못 한다**(`403 Missing Access`). 각 채널 **설정(⚙️) → 권한 → 역할/멤버 추가**로 봇 #1을 넣고 켠다:
- 📝 **텍스트 채널**: `채널 보기`(View Channel)·`메시지 보내기`(Send Messages)·`메시지 기록 보기`(Read Message History) — 봇 #1이 받아쓰기를 올리고 `!join`/`!leave`를 읽으려면 필요.
- 🔊 **음성 채널**: `채널 보기`(View Channel)·`연결`(Connect)·`말하기`(Speak) — 없으면 음성 연결이 `signalling`에서 멈춰 **`ready` 도달 실패** → **봇이 음성 채널 UI에 안 보이고** 음성·STT 전부 불가(게이트웨이 `VoiceStateUpdate`는 길드 단위라 "Auto-joined" 로그는 찍혀서 정상으로 *착각하기 쉽다*).
- (봇 #2도 텍스트 채널을 못 읽으면 중계가 끊기니, 텍스트 채널 권한에 **봇 #2도 함께** 추가해 두면 안전하다.)

**[자동] 채널 접근 검증** — 빌드 전에 [수동 3] 누락을 잡는다(봇 #1 토큰으로 REST 도달 확인):
```bash
for CH in "<VOICE_CHANNEL_ID>" "<TEXT_CHANNEL_ID>"; do
  echo -n "$CH → "; curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bot <봇#1 토큰>" "https://discord.com/api/v10/channels/$CH"
done
```
`200`이면 접근 OK, `403`(Missing Access)이면 그 채널 권한이 빠진 것 → 사용자에게 [수동 3] 권한 추가를 요청하고 **`200`이 나올 때까지** 재확인한다. 음성 채널은 도달(200)만으로 부족하고 `Connect`/`Speak`까지 켜져야 하므로, 의심되면 `GET /channels/<id>`의 `permission_overwrites` + 봇 role 권한을 계산해 `CONNECT`(`1<<20`)·`SPEAK`(`1<<21`) 비트를 확인한다.

**[확인] 자동 생성 전, 수집한 ID를 마스킹해 매핑을 되읽어 확인받는다** (잘못 매핑하면 파일은 정상 생성돼도 음성이 *조용히* 깨진다):
- 봇 #1(voice-bridge, STT/TTS) user ID → `DISCORD_ALLOW_BOT_IDS` (봇 #2 채널 `.env`)
- 봇 #1 토큰 → voice-bridge env `DISCORD_BOT_TOKEN`
- 봇 #2(Claude MCP) user ID → voice-bridge env `CLAUDE_BOT_ID`

**[자동] 스킬이 처리:**
1. 봇 #2 채널 `.env`에 라인 추가 (ADR-0006 — 봇 #1 메시지를 봇 #2가 받게 허용):
   ```
   DISCORD_ALLOW_BOT_IDS=<봇#1 user id>
   ```
2. `access.json`의 `groups`에 텍스트 채널 등록:
   ```json
   "groups": { "<TEXT_CHANNEL_ID>": { "requireMention": false, "allowFrom": [] } }
   ```
3. voice-bridge env 파일 작성 — `mkdir -p ~/workspace/discord-voice-bridge/envs` 후 `envs/<PROJ>.env` 생성 + `chmod 600`:
   ```
   DISCORD_BOT_TOKEN=<봇#1 토큰>
   VOICE_CHANNEL_ID=<VOICE_CHANNEL_ID>
   TEXT_CHANNEL_ID=<TEXT_CHANNEL_ID>
   CLAUDE_BOT_ID=<봇#2 user id>
   SONIOX_API_KEY=<공유 출처에서 자동 주입>
   HUME_API_KEY=<공유 출처에서 자동 주입>
   OPENAI_API_KEY=<공유 출처에서 자동 주입 — 선택(TTS 폴백)>
   USER_ID=<...>          # 선택(입퇴장 자동 토글)
   ```
   SONIOX/HUME/OPENAI 세 줄은 위 "공유 API 키" 출처에서 읽어 채운다(사용자 직접 입력 아님). 봇 토큰·채널 ID·`CLAUDE_BOT_ID`만 이번에 수집한 프로젝트별 값.
4. `~/workspace/discord-voice-bridge/ecosystem.config.js`의 `const projects = [...]` 배열에 `'<PROJ>'` 추가.
5. **server.ts 패치 검증**(읽기 전용 grep, 버전 경로는 동적 탐색):
   ```bash
   D=~/.claude/plugins/cache/claude-plugins-official/discord
   grep -l DISCORD_ALLOW_BOT_IDS "$D"/*/server.ts
   ```
   결과가 나오면 **"패치 적용됨 ✓"로 스킵**한다(현재 0.0.4 캐시엔 이미 적용돼 있다). 비어 있을 때만 ADR-0006 패치(messageCreate 핸들러의 봇 차단을 `DISCORD_ALLOW_BOT_IDS` 화이트리스트로 푸는 4~5줄)를 보여주고 **사용자 승인 하에만** 적용한다(공식 플러그인 코드 수정이므로). 버전이 바뀌면 패치가 사라지니 **음성 설정 때마다 검증**.
6. 빌드·기동:
   ```bash
   cd ~/workspace/discord-voice-bridge && nvm use 22 && npm run build
   pm2 start ecosystem.config.js --only voice-bridge-<PROJ> && pm2 save
   ```
   (`grep -q VOICE_BRIDGE_ENV src/index.ts`로 멀티 지원 코드가 이미 있는지 확인 — 없으면 ADR-0009 변경이 빠진 구버전이니 사용자에게 알림.)

**[사용자] 보안상 직접:**
- `/discord:access group add <TEXT_CHANNEL_ID> --no-mention` (봇 #2가 중계 채널에 반응하도록, ADR-0002)
- 봇 #2 채널 `.env`를 바꿨으니 `/reload-plugins`.

## 3-A. 음성 운영 환경 시드 — hooks + 메모리

음성 워크플로(운전 중 음성 대화)를 매끄럽게 하려면, voice-bridge에서 검증된 알림 hook과 운영 메모리를 새 프로젝트에도 시드한다. 원본은 스킬 디렉토리의 `seed/`다(다른 머신에서도 완결되도록 스킬에 동봉).

**① 훅** — `seed/hooks.settings.json`의 `hooks`를 프로젝트 `.claude/settings.json`에 **병합**(기존 settings 있으면 hook type별로 추가, 없으면 새로 생성). 4종: ack(`UserPromptSubmit`)·approval(`Notification`)·progress(`PostToolUse`)·Stop(타이머 초기화).
- **전제 검증**: 스크립트가 `~/.claude/hooks/scripts/voice-notify-{ack,approval,progress}.sh`에 있어야 동작한다. `ls`로 확인하고, 없으면 *"글로벌 hooks 미설치 — apply-claude-env로 환경 동기화 필요"*라고 안내한다(스크립트 자체는 글로벌 환경 자산이라 이 스킬이 아닌 환경 동기화가 배포한다).
- hook이 알림을 보내려면 봇 #2 토큰(`.claude/channels/discord/.env`)과 **프로젝트 루트 `.env`의 `TEXT_CHANNEL_ID`·`USER_ID`**가 필요하다. 토큰은 DM 경로에서 만들지만 **루트 `.env`는 아래 ①-b에서 새로 만들어야 한다**(안 만들면 ack·progress가 조용히 no-op).

**①-b 프로젝트 루트 `.env` (hook 입력값) — 훅과 반드시 세트로 생성:**
음성 알림 hook(`voice-notify-*.sh`)은 `$PROJECT_DIR/.env`에서 아래 값을 읽는다(봇 토큰은 `.claude/channels/discord/.env`에서 읽으므로 여기엔 안 넣는다 — 비밀값 없음). 프로젝트 루트에 `.env` 생성 + `chmod 600`:
```
TEXT_CHANNEL_ID=<TEXT_CHANNEL_ID>   # progress·approval 발송 채널
USER_ID=<USER_ID>                   # ack: 영우 본인 텍스트 메시지 필터(🎤 음성 발화는 무관)
CLAUDE_BOT_ID=<봇#2 user id>        # ack 호환
```
- `.gitignore`에 `.env` 추가(`grep -qx '.env' .gitignore` 확인 후).
- ⚠️ 이건 `~/workspace/discord-voice-bridge/envs/<PROJ>.env`(voice-bridge **프로세스**가 읽는, 봇 #1 토큰·API 키 든 파일)와 **다른 파일**이다. 소비자가 달라 둘로 분리한다:
  - `envs/<PROJ>.env` → voice-bridge pm2 프로세스(STT/TTS) — 봇 #1 토큰·채널 ID·API 키
  - `<프로젝트>/.env` → Claude Code 알림 hook(ack/progress/approval) — 비밀 아닌 ID 3개

**①-c 발송 검증** — 시드 직후 progress 스크립트를 1회 실행해 실제 전송을 확인한다(타이머를 과거로 세팅해 120초 쿨다운 통과):
```bash
F="/tmp/voice_bridge_progress_$(id -u)"; echo $(( $(date +%s) - 200 )) > "$F"
CLAUDE_PROJECT_DIR="$PWD" bash ~/.claude/hooks/scripts/voice-notify-progress.sh </dev/null; rm -f "$F"
```
텍스트 채널에 "⚙️ 작업 진행 중…"이 뜨면 스크립트·값 정상. 안 뜨면 `BOT_TOKEN`(채널 `.env`)·`TEXT_CHANNEL_ID`(루트 `.env`)를 확인한다.

**② 메모리** — `seed/memory/`의 7개 `.md` + `MEMORY.md`를 새 프로젝트의 메모리 디렉토리에 복사:
- 경로: `~/.claude/projects/<인코딩된_프로젝트_절대경로>/memory/` — 절대경로의 `/`를 `-`로 치환한다(예: `/Users/kywpcm/workspace/foo` → `~/.claude/projects/-Users-kywpcm-workspace-foo/memory/`).
- 디렉토리가 없으면 생성. `MEMORY.md`가 이미 있으면 seed의 인덱스 줄들을 **append**(중복 제목 제외), 없으면 seed `MEMORY.md`를 그대로 둔다.
- 내용은 톤(수진)·ack 규칙·음성 워크플로·hook 설명·SSOT·병렬편집·todo 컨벤션 — 새 프로젝트에 보편 적용되는 **일반화판**이다. 프로젝트 고유 사실이 생기면 이후 대화로 별도 메모리를 쌓는다.

이 단계는 **음성 구성에서 기본 수행**한다. DM 전용 구성에선 hook 시드는 보통 생략하되, 톤(`feedback_conversation_tone`)·SSOT 메모리 정도는 원하면 시드할 수 있다(사용자에게 물어 결정).

**⚠️ [중요] 시드 후 적용 — 세션을 한 번 나갔다 다시 들어와야 한다.** 시드가 끝나면 사용자에게 다음을 안내한다:
- **훅**: Claude Code는 **시작 시점에 훅 스냅샷을 고정**한다(세션 중 `settings.json`이 바뀌어도 자동 적용 안 함 — 보안 모델). 따라서 ① **세션 재시작**, 또는 ② **`/hooks` 메뉴에서 변경 검토→적용** 중 하나가 필요하다. `/reload-plugins`는 *플러그인* 훅만 다시 읽지 **프로젝트 `settings.json` 훅 스냅샷은 갱신하지 않는다**.
- **메모리**: `MEMORY.md` 인덱스는 **세션 시작 시** 컨텍스트에 로드된다. 시드한 메모리는 **다음 세션부터** 자동 인식된다.
- → 결론: 시드 직후 **봇 #2 세션을 재시작**(`clauded --channels plugin:discord@claude-plugins-official`를 다시 실행)하면 훅·메모리가 함께 적용된다.

## 4. 검증

**DM**: 봇 #2에게 DM → Claude 응답. 실패 시 — `direnv status`(DISCORD_STATE_DIR export?), `.env` 토큰·`chmod 600`, `access.json`의 `allowFrom`에 내 ID, MESSAGE CONTENT INTENT.

**음성**: `pm2 logs voice-bridge-<PROJ>`에서 봇 #1 로그인·`REQUIRED_ENV` 미스 없음 확인 → 음성 채널 입장(환영 음성) → 말하기 → 텍스트 채널에 `🎤 [음성]…` 도착 → 봇 #2가 응답 작성 → TTS 음성 재생되면 **전체 루프 성공**. 봇 #2가 응답 안 하면(가장 흔함): 봇 #2가 `clauded --channels …`로 떠 있나? / server.ts 패치 / `DISCORD_ALLOW_BOT_IDS`에 봇 #1 ID 정확? / `group add` 적용? / `/reload-plugins` 했나?

**봇 #1이 음성 채널 UI에 안 보이거나 음성·STT가 안 되면** → [수동 3] 채널 권한 문제다. 로그가 `[Voice] state: signalling -> destroyed`만 반복하고 `ready`에 못 가면 강한 신호. 봇 #1 토큰으로 `GET /channels/<VOICE_CHANNEL_ID>`가 `403`이면 접근 자체가 없는 것 → 음성 채널 권한에 봇 #1(View/Connect/Speak)을 추가하면 즉시 해결된다(봇 재시작 불필요, 다음 입장부터 적용).

## 흔한 실수
- **4개 ID 혼동**: 봇 #1/#2 토큰·user ID를 섞어 넣음 → 위 표로 매번 대조.
- **봇 #2 토큰을 글로벌에 저장**: `/discord:configure`는 `~/.claude/...`(글로벌)에 쓴다. 이 스킬은 **프로젝트 경로**에 직접 써야 하므로 `/discord:configure`에 의존하지 않는다.
- **셸 env 오염**: 셸에 `DISCORD_BOT_TOKEN`이 export돼 있으면 server.ts가 프로젝트 `.env`를 무시한다(실제 env 우선). 사전 점검에서 확인.
- **reload 누락**: 토큰/`DISCORD_ALLOW_BOT_IDS`를 바꾼 뒤 `/reload-plugins` 안 하면 옛 설정으로 동작.
- **봇 #2 미실행**: 봇 #2는 대상 프로젝트에서 `clauded --channels plugin:discord@claude-plugins-official`로 떠 있어야 DM·채널에 응답한다. 안 띄우면 메시지를 보내도 무응답이라 토큰 문제로 오인하기 쉽다.
- **direnv 미반영**: `.envrc`를 만든 직후 같은 셸엔 `DISCORD_STATE_DIR`이 아직 안 떠 있을 수 있다. `clauded` 띄우기 전 디렉토리를 나갔다 재진입(`cd .. && cd -`)해 `export +DISCORD_STATE_DIR`을 확인할 것. 안 하면 글로벌 STATE_DIR을 읽어 프로젝트 봇 토큰을 못 찾아 봇 #2가 무응답이 된다.
- **봇 #1 채널 권한 누락(음성 무음 실패의 1순위)**: OAuth 초대는 **길드 권한만** 준다. 채널이 비공개/카테고리 오버라이드면 봇 #1이 채널에 접근 못 해(`403 Missing Access`) 음성 연결이 `signalling→destroyed`만 반복하고 `ready`에 못 가 **UI에 안 보인다**. 게이트웨이 "Auto-joined" 로그는 길드 이벤트라 찍히므로 정상으로 오인하기 쉽다. → [수동 3]에서 두 채널 권한에 봇 #1을 직접 추가(음성: View/Connect/Speak, 텍스트: View/Send/Read History)하고, 봇 #1 토큰으로 `GET /channels/<id>`가 `200`인지 검증.
- **hook용 루트 `.env` 누락(알림 무음 실패)**: ack·progress·approval은 `$PROJECT_DIR/.env`에서 `TEXT_CHANNEL_ID`·`USER_ID`를 읽는다. `envs/<PROJ>.env`(voice-bridge 프로세스용)만 만들고 루트 `.env`를 빠뜨리면 알림이 조용히 안 온다(no-op). [3-A ①-b]에서 hook과 세트로 생성하고 progress 스크립트 1회 실행으로 발송까지 검증. (소비자가 다른 별개 파일임 — 통합하지 않는다.)
- **새 서버 생성**: 음성은 기존 서버에 채널만 추가. 봇이 프로젝트마다 다르므로 한 서버로 충분.
- **API 키 하드코딩 금지**: `SONIOX/HUME/OPENAI` 키는 **public 플러그인 repo·스킬·seed에 절대 넣지 않는다**(유출). 프로젝트 불변 공유 키라, 로컬 출처(`~/.config/voice-bridge/shared-keys.env` 또는 기존 voice-bridge env)에서만 주입한다.
