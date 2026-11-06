# 11/10(화) 팀 회의 안건 — 이성수 준비

> 미리 볼 것: `erd/img/erd_conceptual.png`(개념 ERD), `erd/img/erd_logical.svg`(논리 ERD),
> `docs/report/06_logical_model.md`, `docs/report/10_table_spec.md`(테이블 기술서)
> dbdiagram.io 에서 보려면 `erd/kbo_erd.dbml` 내용을 붙여 넣기

## 1. ERD 초안 리뷰 (김경주, 배인표) — 20분

테이블 24개: 기준 정보 3, 선수 3, 경기 기록 12, 투구 3, 기록실 공식(검증용) 3

결정할 것
- [ ] 엔터티 목록·관계에 빠진 화면 기능이 있는가 (경기 결과 / 선수 프로필·비교 / 팀 프로필 / 순위 / 시각화)
- [ ] 주식별자: 선수 = KBO playerId(integer), 경기 = kbodata id `20250601_OBWO0`, 팀 = KBO 팀코드 — 동의?
- [ ] 시즌 성적·순위를 테이블에 저장하지 않고 **머티리얼라이즈드 뷰**로 계산하는 방식 — 백엔드에서 MV를 읽기 전용 엔터티로 써도 되는가
- [ ] `team_game.home_away` 의도적 중복(트리거로 일관성 보장) 괜찮은가

## 2. 컬럼명·자료형 규칙 합의 — 15분

제안 (docs/report/07_physical_model.md 7.2, 09_domain_definition.md)
- [ ] 영어 소문자 snake_case, 테이블 단수형, `_id`/`_code`/`is_`/단위 접미어(`_cm`, `_kmh`, `_10k_krw`)
- [ ] 이닝은 **아웃카운트 정수**(6⅓ = 19)로 저장, 표시만 `6 1/3`
- [ ] 비율은 numeric (타율 numeric(4,3)), 돈은 만원 단위 정수 + 달러 별도 컬럼
- [ ] PostgreSQL DOMAIN 사용 (Spring은 `ddl-auto=none`, docs/handoff/backend_kimkyungju.md)

## 3. 배인표 전처리와의 인터페이스 — 10분

- [ ] 매핑표 형식: `data/player_season_team.csv` (season, team_id, player_id, name, is_batter, is_pitcher)
- [ ] 적재용 CSV 형식 = `etl/kbodata_to_tables.py` 출력 (테이블 컬럼 순서 그대로) — 참고 구현을 그대로 쓸지, 인표가 새로 만들지
- [ ] **kbodata 버그 2개 공유**: 결정 없는 투수도 'L'(패), 타순 열 버림 → `crawl/kbodata_patch.py` 를 kbo_fetch.py에 적용한 뒤 시즌 수집하자
- [ ] 기타기록(ETC_info) 파싱 분담 — 참고 구현(`etl/kbodata_parse.parse_etc_item`) 있음

## 4. 수집 연도 범위 확정 — 5분

| 안 | 장점 | 단점 |
|---|---|---|
| 2021~2025 | 수집·검증 부담 적음, SSG 팀명 하나 | 팀명 변경 이력 사례가 적음 |
| 2008~2025 | kbodata 지원 전체, 팀명 변경(넥센→키움, SK→SSG) 사례 풍부 | kbodata 시즌당 40~60분 × 18, 오래된 시즌 데이터 품질 ❓ |

🟡 추천: **2025 먼저 → 2021~2024 → 시간 남으면 2008까지.** 투구(네이버 좌표)는 2023년 이후만 있으므로 시각화는 2023~2025.
참고: 오늘(11/5) 기준 2026 시즌도 끝나서 2026 데이터도 받을 수 있다 — 넣을지 결정.

## 5. 기타 — 10분

- [ ] 모델링 도구: ERwin(Windows) vs ERDCloud vs dbdiagram.io — 지금 ERD는 DDL에서 자동 생성(DBML·Mermaid·PNG)되므로
      보고서에는 자동 생성 그림을 쓰고, 필요하면 ERwin으로 다시 그리기
- [ ] 보고서 1~4번(개요서, 업무 기능도, 단위 업무 기술서, 업무 흐름도) 담당자
- [ ] DB dump 담당 (김경주 추천)
- [ ] 팀명
- [ ] 교수님이 데이터 수집 방법은 신경 쓰지 않는다고 말씀하신 내용 공유 (별도 문의 불필요, docs/email_professor.md)

## 공유할 진행 상황 (이성수)

| 항목 | 상태 |
|---|---|
| ERD v0 + PostgreSQL DDL | ✅ 로컬 PostgreSQL 16에서 생성·적재·뷰·제약조건 테스트 통과 |
| 크롤러 (기록실·선수 상세·순위·네이버) | ✅ 코드 완료, 맥에서 probe 실행 후 실데이터 수집 (11/9 샘플 목표) |
| kbodata 변환·검증 | ✅ 참고 구현 + 버그 패치 |
| 보고서 6~10장 | 🟡 초안 (6, 7, 8, 9, 10장) |
