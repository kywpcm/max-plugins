---
description: 원격 대비 뒤처진 로컬 브랜치들을 일괄 pull 합니다
allowed-tools: Bash
model: haiku
---

다음 단계를 순서대로 수행하여 로컬 브랜치들을 원격과 동기화해줘:

1. 현재 브랜치를 `git branch --show-current`로 기록해둬 (작업 완료 후 복귀용)
2. `git fetch --all --prune`으로 모든 원격 브랜치 정보를 최신화해줘
3. 로컬 브랜치 중 원격 추적 브랜치가 있는 것들을 대상으로, 원격 대비 뒤처진(behind) 브랜치 목록을 확인해줘
   - `git for-each-ref --format='%(refname:short) %(upstream:short) %(upstream:track)' refs/heads/` 명령으로 확인
   - `[behind ...]` 또는 `[behind ..., ahead ...]`가 포함된 브랜치가 pull 대상
4. 결과를 확인해줘:
   - pull이 필요한 브랜치가 **없으면** → "모든 로컬 브랜치가 최신 상태입니다" 메시지를 출력하고 종료
   - pull이 필요한 브랜치가 **있으면** → 브랜치별 behind 커밋 수를 표로 보여주고 바로 pull 진행
5. 대상 브랜치마다 `git checkout {branch} && git pull` 실행
   - 각 브랜치의 pull 성공/실패 결과를 기록해둬
   - 충돌(conflict)이 발생하면 `git merge --abort`로 되돌리고 해당 브랜치는 건너뛰어줘
6. 1단계에서 기록한 원래 브랜치로 `git checkout {원래 브랜치}`하여 복귀해줘
7. 최종 결과를 요약 테이블로 보여줘 (브랜치명, 결과: 성공/실패/건너뜀)
