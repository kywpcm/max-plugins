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
version: 0.1.0
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

**[사용자] 적용·검증:**
- `/reload-plugins` (또는 세션 재시작) — server.ts는 토큰을 **부팅 시 1회만** 읽으므로 필수.
- 디스코드에서 **봇 #2에게 DM** 전송 → Claude 응답이 오면 DM 구성 완료.

DM 전용이면 여기서 끝. 음성이면 3으로.

## 3. 음성 경로 (DM 경로 완료 후 이어서)

먼저 **프로젝트명 `PROJ`를 정한다**: 현재 디렉토리 basename(`basename "$PWD"`)을 기본값으로 보여주고 확인/수정받는다. `PROJ`는 voice-bridge env 파일명·pm2 app 이름에 쓰이므로 영문/숫자/하이픈만 허용.

**[수동 1] 채널 2개 생성** — 기존 서버에 채널 2개를 만든다. **새 서버는 만들지 않는다**(봇이 프로젝트마다 달라 한 서버에서 음성 채널 여러 개 동시 운영 가능). 각 채널 우클릭 → "ID 복사". 둘을 섞지 않게 라벨을 분명히:
- **텍스트 채널**(중계 통로, 예 `#<PROJ>-bridge`) → `TEXT_CHANNEL_ID`
- **음성 채널**(예 🔊 `<PROJ>-voice`) → `VOICE_CHANNEL_ID`

**[수동 2] 봇 #1(voice-bridge 봇) 새로 생성** — 봇 #2와 **별개의 새 Application**:
- Bot 탭 → Reset Token → 토큰 복사
- **MESSAGE CONTENT INTENT + SERVER MEMBERS INTENT** ON
- OAuth2 권한: `bot` + `Connect` `Speak` `View Channels` `Send Messages` `Read Message History` → **같은 서버**에 초대
- 서버 멤버 목록에서 봇 #1 우클릭 → "ID 복사"
→ **봇 #1 토큰, 봇 #1 user ID** 수집. 추가로 **봇 #2 user ID**(서버에서 봇 #2 우클릭 → ID 복사)와 **API 키**(Soniox/Hume 필수, OpenAI/USER_ID 선택)도 수집.

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
   SONIOX_API_KEY=<...>
   HUME_API_KEY=<...>
   OPENAI_API_KEY=<...>   # 선택(TTS 폴백)
   USER_ID=<...>          # 선택(입퇴장 자동 토글)
   ```
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

## 4. 검증

**DM**: 봇 #2에게 DM → Claude 응답. 실패 시 — `direnv status`(DISCORD_STATE_DIR export?), `.env` 토큰·`chmod 600`, `access.json`의 `allowFrom`에 내 ID, MESSAGE CONTENT INTENT.

**음성**: `pm2 logs voice-bridge-<PROJ>`에서 봇 #1 로그인·`REQUIRED_ENV` 미스 없음 확인 → 음성 채널 입장(환영 음성) → 말하기 → 텍스트 채널에 `🎤 [음성]…` 도착 → 봇 #2가 응답 작성 → TTS 음성 재생되면 **전체 루프 성공**. 봇 #2가 응답 안 하면(가장 흔함): server.ts 패치 / `DISCORD_ALLOW_BOT_IDS`에 봇 #1 ID 정확? / `group add` 적용? / `/reload-plugins` 했나?

## 흔한 실수
- **4개 ID 혼동**: 봇 #1/#2 토큰·user ID를 섞어 넣음 → 위 표로 매번 대조.
- **봇 #2 토큰을 글로벌에 저장**: `/discord:configure`는 `~/.claude/...`(글로벌)에 쓴다. 이 스킬은 **프로젝트 경로**에 직접 써야 하므로 `/discord:configure`에 의존하지 않는다.
- **셸 env 오염**: 셸에 `DISCORD_BOT_TOKEN`이 export돼 있으면 server.ts가 프로젝트 `.env`를 무시한다(실제 env 우선). 사전 점검에서 확인.
- **reload 누락**: 토큰/`DISCORD_ALLOW_BOT_IDS`를 바꾼 뒤 `/reload-plugins` 안 하면 옛 설정으로 동작.
- **새 서버 생성**: 음성은 기존 서버에 채널만 추가. 봇이 프로젝트마다 다르므로 한 서버로 충분.
