# Graph DB Neo4j 계획

## 결정 사항
Graph DB는 실제로 프로젝트에 연동한다.

다만 개발자 A의 백엔드 경계, API 계약, 카드 데이터 구조가 안정된 뒤 연동한다.

## 목적
Neo4j는 관계가 많은 추천 데이터를 빠르게 탐색하기 위한 추천 엔진 데이터 레이어로 사용한다.

Django의 관계형 DB는 사용자, 카드, 크롤링 원본 데이터, 인증 관련 데이터 같은 핵심 애플리케이션 레코드를 계속 담당한다.

## 후보 노드
- `User`
- `Area`
- `Store`
- `Category`
- `Card`
- `Benefit`

## 후보 관계
- `(User)-[:LIVES_IN]->(Area)`
- `(User)-[:OWNS]->(Card)`
- `(Store)-[:LOCATED_IN]->(Area)`
- `(Store)-[:BELONGS_TO]->(Category)`
- `(Card)-[:HAS_BENEFIT]->(Benefit)`
- `(Benefit)-[:APPLIES_TO]->(Category)`

## 예시 사용 사례
사용자가 선택한 지역에 많이 존재하는 매장 카테고리에 혜택을 제공하는 카드를 찾는다.

```cypher
MATCH (a:Area {id: $area_id})<-[:LOCATED_IN]-(s:Store)-[:BELONGS_TO]->(cat:Category)
MATCH (card:Card)-[:HAS_BENEFIT]->(b:Benefit)-[:APPLIES_TO]->(cat)
RETURN card, cat, count(s) AS nearby_store_count, collect(b) AS benefits
ORDER BY nearby_store_count DESC
```

## 연동 단계
1. 카드와 혜택의 정규화 스키마를 확정한다.
2. Neo4j 환경변수를 추가한다.
3. Neo4j 읽기/쓰기를 담당하는 graph repository 레이어를 추가한다.
4. 크롤링한 카드, 혜택, 카테고리, 지역, 매장 데이터를 Neo4j에 동기화한다.
5. Neo4j 쿼리 결과를 Python Seul-Score 함수의 입력으로 사용한다.

## 런타임 규칙
Neo4j는 추천 후보 관계를 찾는 역할을 담당한다.

최종 Seul-Score 계산은 Python 함수가 담당한다. 이렇게 해야 알고리즘을 독립적으로 테스트할 수 있다.
