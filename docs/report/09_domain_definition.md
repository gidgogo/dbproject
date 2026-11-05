# 9. 도메인 정의서

> 담당: 이성수 · 초안 v0 (2026-11-05)
> 도메인 = "같은 의미의 값이 가질 수 있는 자료형과 범위". 아래 도메인은 `erd/ddl/01_domains.sql`에
> PostgreSQL `CREATE DOMAIN`으로 그대로 구현했다. 도메인별 사용 컬럼 전체 목록은 `09_domain_usage.md`(자동 생성).

## 9.1 DB 도메인 (CREATE DOMAIN)

| 도메인 분류 | 도메인명 | 자료형 | 허용 값 | 예시 | 쓰는 곳 |
|---|---|---|---|---|---|
| 식별자 | d_team_id | char(2) | 영문 대문자 2자 | OB, SK, WO | 팀ID |
| 식별자 | d_player_id | integer | 1 이상 | 76232 | 선수ID, 투수ID, 타자ID |
| 식별자 | d_game_id | varchar(14) | `YYYYMMDD_` + 팀코드 4자 + 더블헤더 1자리 | 20250601_OBWO0 | 경기ID |
| 시간 | d_season | smallint | 1982 ~ 2100 | 2025 | 시즌, 지명연도, 입단연도 |
| 순서 | d_inning | smallint | 1 ~ 18 | 9 | 이닝 |
| 수량 | d_count | smallint | 0 이상 | 4 | 경기 단위 횟수 (타수, 안타 …) |
| 수량 | d_total | integer | 0 이상 | 162 | 시즌 누적 횟수 |
| 수량 | d_outs | integer | 0 이상 | 19 (=6⅓이닝) | 투수 아웃카운트 |
| 비율 | d_rate | numeric(4,3) | 0 ~ 1 | 0.312 | 타율, 출루율, 승률 |
| 비율 | d_slg | numeric(5,3) | 0 ~ 5 | 0.875 | 장타율, OPS |
| 비율 | d_era | numeric(6,2) | 0 이상 | 3.21 | 평균자책점, WHIP |
| 코드 | d_hand | char(1) | L, R, S | R | 투구손(L/R), 타격방향(L/R/S) |
| 명칭 | d_person_name | varchar(30) | 공백만은 불가 | 홍길동 | 선수명, 심판명 |

## 9.2 도메인으로 만들지 않은 공통 형식

| 분류 | 자료형 | 규칙 | 예 |
|---|---|---|---|
| 코드(한 글자) | char(1) + CHECK | 값 목록을 CHECK로 제한 | 승패(W/L/D), 홈원정(H/A), 초말(T/B), 투수결정(W/L/S/H) |
| 코드(문자열) | varchar(n) + FK | 코드표 테이블을 참조 | 타석결과유형, 구종명, 기타기록유형 |
| 일자 / 시각 / 일시 | date / time / timestamptz | | 경기일자, 개시시각, 수집일시 |
| 여부 | boolean | `is_` 접두어 | is_retired, is_dome |
| 금액 | integer | 단위를 컬럼명에 표시, 통화별 컬럼 분리 | salary_10k_krw(만원), salary_usd |
| 신체 | smallint + CHECK | 신장 140~230cm, 체중 40~200kg | |
| 투구 위치 | numeric(6,3) | 피트(ft), 원본 PITCHf/x 단위 그대로 | plate_x = -0.415 |
| 구속 | smallint + CHECK | 50 ~ 175 km/h | 151 |
| 원문 텍스트 | varchar(n) | 화면 표시·추적용, 검색·집계하지 않음 | 경력, 지명정보, 기타기록 원문 |

## 9.3 도메인 결정 근거

1. **이닝을 아웃카운트 정수로**: 6⅓이닝을 6.33(실수)으로 두고 세 경기를 더하면 18.99이닝이 되어 정답 19이닝과 달라진다(아웃 수로는 19 × 3 = 57).
   kbodata의 `61` 표기는 숫자 61로 오해할 수 있다. 정수 아웃 수는 합산이 정확하고, 화면 표시만 `6 1/3`으로 바꾸면 된다.
2. **비율은 numeric**: 타율 .300 을 float로 저장하면 0.29999… 같은 값이 생겨 동률 비교가 틀어질 수 있다.
3. **경기 단위 smallint, 시즌 누적 integer**: 한 경기 안타는 수십을 넘지 않지만 시즌 투구수는 수천이다.
4. **선수ID integer**: KBO playerId는 숫자다. 문자(varchar)보다 조인·인덱스가 가볍다.
   (❓ 네이버 pcode에 영문이 섞인 경우가 보고되어, 그런 선수는 이름 매핑으로 KBO playerId를 찾는다)
5. **팀ID char(2)**: KBO 팀코드는 항상 2자리. 고정 길이 + 정규식으로 소문자·오타를 막는다.
6. **금액 단위 분리**: 상세 페이지 연봉이 "52000만원", "100000달러"처럼 통화가 섞여 있어 한 컬럼에 넣으면 비교가 불가능하다.

## 9.4 Spring(JPA) 매핑 메모 (김경주 참고)

| DB 도메인 / 자료형 | Java 타입 |
|---|---|
| d_player_id, d_total, d_outs, integer | Integer |
| d_count, d_inning, d_season, smallint | Short (또는 Integer — Hibernate가 읽기는 처리하지만 `ddl-auto=validate`는 꺼야 함) |
| d_rate, d_slg, d_era, numeric | BigDecimal |
| d_team_id, char(1)/char(2) | String |
| date / time / timestamptz | LocalDate / LocalTime / OffsetDateTime |

도메인 컬럼은 JDBC 메타데이터상 타입 이름이 도메인명(d_team_id 등)으로 보여서 Hibernate 스키마 검증과 맞지 않을 수 있다.
스키마는 SQL 스크립트로 관리하므로 `spring.jpa.hibernate.ddl-auto=none` 을 권장한다.
