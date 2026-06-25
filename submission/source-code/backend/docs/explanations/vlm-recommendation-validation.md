# VLM 소비 프로필 추천 검증

## 목적

실제 VLM 연결 전에 사용자 정보와 월간 카테고리별 소비 리포트를 더미 데이터로
입력해 전체 추천과 카테고리 추천이 정상적으로 달라지는지 확인한다.

## 더미 데이터

기준 파일:

```text
backend/finance/testdata/vlm_spending_profiles.json
```

총 7개 프로필을 사용한다.

| 프로필 | 주요 목적 |
| --- | --- |
| `cafe_focused` | 카페 중심 소비 |
| `delivery_focused` | 배달 중심 소비 |
| `dining_focused` | 외식 중심 소비 |
| `mart_focused` | 마트 중심 소비 |
| `balanced` | 균형 소비 |
| `zero_spending` | 모든 소비가 0원인 경계값 |
| `partial_categories` | 일부 카테고리만 전달되는 경우 |

각 프로필에는 사용자 ID, 닉네임, `spending`, `owned_card_ids`가 포함된다.
`spending_source`는 평가 시 `image_parser`로 지정한다.

## 실행 방법

전체 추천 비교:

```powershell
python manage.py evaluate_vlm_profiles --limit 3
```

특정 프로필의 카페 추천:

```powershell
python manage.py evaluate_vlm_profiles `
  --profile cafe_focused `
  --category cafe `
  --limit 3
```

평가 명령은 SQLite의 실제 `active` 카드와 고정된 주변 상권 표본을 사용한다.
DB를 수정하지 않는다.

## 검증 항목

### 전체 추천

- 소비 성향에 따라 `spending_benefit_fit`이 달라지는가
- 주변 상권이 같을 때 `local_brand_fit`은 카드 혜택 범위에 따라 달라지는가
- 전체 점수가 정확히 `60/25/15`로 계산되는가
- 보유 카드가 점수 가산 없이 `is_owned=true`로만 표시되는가

### 카테고리 추천

- 선택 카테고리 소비액이 혜택 잠재액에 반영되는가
- 다른 카테고리 소비가 Top 3 정렬에 개입하지 않는가
- 브랜드 접근성과 지역 접근성이 각각 응답되는가

### 경계값

- 소비액이 모두 0원이면 모든 혜택과 추천 점수가 0이 되는가
- 일부 카테고리가 누락돼도 예외 없이 계산되는가

## 2026-06-22 실행 결과

- 전체 소비 비중은 카드 내부가 아니라 사용자 전체 소비액 기준으로 계산됐다.
- 배달 중심 프로필에서는 배달 특화 신용카드가 전체 추천 상단으로 이동했다.
- 카페 카테고리 추천에서는 카페 혜택과 주변 카페 브랜드만 순위에 반영됐다.
- 카페 추천에서 배달 소비액을 변경해도 카페 순위는 바뀌지 않았다.
- `zero_spending` 프로필은 신용·체크카드 모두 추천 점수가 0점이었다.
- 보유 카드 ID는 `is_owned`와 `badge`에만 반영되고 점수에는 영향을 주지 않았다.

실제 카드 데이터에는 범용 할인 카드와 일부 동일 구조 상품이 있어 서로 다른
소비 프로필에서도 같은 카드가 상단에 남을 수 있다. 이는 산식 오류가 아니라
현재 활성 카드 구성과 약관 데이터 분포의 영향이다.
