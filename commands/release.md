---
description: develop 브랜치 기준으로 git-flow release 브랜치를 생성하고 master 머지, 태그 생성까지 진행합니다
allowed-tools: Bash
model: haiku
---

# Git-Flow Release 시작

현재 로컬 repo의 develop 브랜치 기준으로 git-flow release 과정을 진행한다.

## 진행 절차

### 1. 태그 이름 입력받기

- 사용자에게 릴리즈 태그 이름을 입력받는다.
- 이것이 전체 과정에서 유일한 사용자 입력이다. 이후 단계는 모두 자동으로 진행한다.

### 2. Release 브랜치 생성 및 완료

아래를 순서대로 자동 진행한다:

1. develop 브랜치 최신화: `git checkout develop && git pull origin develop`
2. release 브랜치 생성: `git checkout -b release/{태그이름} develop`
3. **master에 머지**: `git checkout master && git pull origin master && git merge --no-ff release/{태그이름}`
4. **태그 생성**: `git tag {태그이름}`
5. **develop에 머지**: `git checkout develop && git merge --no-ff release/{태그이름}`
6. **release 브랜치 삭제**: `git branch -d release/{태그이름}`

### 3. 원격 푸시

```
git push origin master
git push origin develop
git push origin {태그이름}
```

## 주의사항

- 사용자 입력은 태그 이름 1회만 받고, 이후 모든 단계는 중단 없이 자동 진행한다.
- 머지 충돌 발생 시에만 사용자에게 알리고 해결 방법을 안내한다.
