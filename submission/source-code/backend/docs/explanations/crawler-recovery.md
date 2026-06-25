# 크롤러 중단 복구 설명

## 목적

카드 크롤링 도중 인터넷 연결, 실행 프로세스 또는 개발 세션이 종료돼도 완료된
데이터를 잃지 않고 남은 항목부터 재개하기 위한 구조를 설명한다.

## 저장 모델

`CrawlJob`은 카드사 채널 단위 실행 상태를 저장한다.

```text
source_channel
status
resume_cursor
total_count
success_count
failed_count
last_error
last_checkpoint_at
```

`CrawlItem`은 카드 상세 URL 단위 상태를 저장한다.

```text
job
external_id
source_url
status
retry_count
raw_payload
last_error
last_attempted_at
completed_at
```

같은 작업과 URL 조합에는 하나의 항목만 생성할 수 있어 재실행 시 중복을 막는다.

## 카드 한 건 처리 흐름

```text
pending 또는 retry_pending 항목 조회
  -> fetching 상태 커밋
  -> 네트워크 요청 및 파싱
  -> 성공하면 raw_payload와 success 상태 커밋
  -> 실패하면 재시도 또는 failed 상태 커밋
```

네트워크 요청 전에 `fetching` 상태를 저장하기 때문에 프로세스가 갑자기 종료돼도
처리 중이던 항목을 식별할 수 있다.

## 인터넷 연결 오류

연결 오류, 타임아웃과 일시적인 서버 오류는 재시도 대상으로 분류한다.

```text
1차 실패 -> 2초 대기
2차 실패 -> 5초 대기
3차 실패 -> 15초 대기 후 마지막 재시도
4차 실패 -> failed
```

현재 기본값은 최초 요청 1회와 추가 재시도 3회로 총 4회 시도한다.

403과 429는 무리한 재시도를 하지 않고 해당 채널을 `paused` 처리한다.

## 프로세스와 세션 종료

`KeyboardInterrupt`처럼 실행 자체가 종료되는 예외는 일반 실패로 삼키지 않는다.
항목은 `fetching` 상태로 남고 다음 실행에서 `recover_interrupted_job()`이
`retry_pending`으로 되돌린다.

Codex 토큰이나 개발 세션 종료는 애플리케이션이 직접 감지할 수 없다. 따라서
런타임 체크포인트는 SQLite에, 구현 진행 상태와 다음 작업은
`backend/docs/plans/card-normalization-plan.md`에 각각 보존한다.

## 이미지 원자적 저장

```text
원본 이미지 요청
  -> {filename}.part 저장
  -> 이미지 콘텐츠 타입과 크기 검증
  -> 최종 파일명으로 이동
```

다운로드 중 오류가 발생하면 `.part` 파일을 삭제한다. 깨진 파일이 정상 카드
이미지로 인식되는 것을 방지한다.

## 현재 구현 경계

완료:

- SQLite 체크포인트 모델
- 항목 등록 멱등성
- 중단 상태 복구
- 오류 분류와 재시도
- 채널별 일시정지
- 이미지 원자적 저장
- 관리 명령 공통 옵션
- `--resume` 관리 명령 통합 검증
- `--resume --retry-failed` 실패 항목 복구 검증

미완료:

- 나머지 카드사별 목록 수집기
- Neo4j 동기화

## 재개 명령

프로세스가 종료될 때 `fetching`이었던 항목은 다음 실행에서
`retry_pending`으로 복구한다. 이미 `success`인 항목은 다시 처리하지 않는다.

```text
python manage.py crawl_cards --issuer shinhan --resume
```

네트워크 단절이 재시도 한도를 모두 소진해 항목이 `failed`가 됐다면 실패
항목 재시도를 명시한다.

```text
python manage.py crawl_cards --issuer shinhan --resume --retry-failed
```

통합 테스트는 성공 항목과 처리 중 항목이 섞인 작업의 재개, 재시도 한도를
소진한 실패 항목의 복구를 각각 검증한다.
