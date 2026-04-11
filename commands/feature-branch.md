---
description: develop 브랜치 기준으로 feature 브랜치를 생성합니다
argument-hint: "{branch name}"
allowed-tools: Bash
model: haiku
---

다음 단계를 순서대로 수행하여 feature 브랜치를 생성해줘:

1. 현재 작업 중인 변경사항이 있는지 `git status`로 확인해줘
   - 변경사항이 없으면 → 바로 2단계로 진행
   - 변경사항이 있으면 → 변경된 파일 목록을 보여주고 사용자에게 다음 3가지 선택지를 제시해줘:
     - **Stash 후 진행**: `git stash push -m "WIP: <message>"` 실행 후 2단계로 계속 진행
     - **무시하고 진행**: stash 없이 그대로 2단계로 진행
     - **취소**: 브랜치 생성을 중단하고 종료
2. `git fetch origin develop` 으로 원격 develop 브랜치 최신화
3. `git checkout develop` 으로 develop 브랜치로 이동
4. `git pull origin develop` 으로 로컬 develop 브랜치를 최신 상태로 갱신
5. `git checkout -b feature/$ARGUMENTS` 으로 새 feature 브랜치 생성 및 체크아웃
6. 최종 결과를 `git branch --show-current` 로 확인하여 보여줘

브랜치명: feature/$ARGUMENTS
