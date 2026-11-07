# 9. 도메인 정의서

> 담당: 이성수 · v1 (2026-11-07, 팀 레포 규칙 반영)
> 도메인 = "같은 의미의 값이 가질 수 있는 자료형과 범위". 도메인은 **보고서(논리 설계)에서 정의**하고,
> DB에는 `CREATE DOMAIN` 대신 **기본 자료형 + 컬럼 CHECK**로 구현했다. 팀 백엔드의 JPA `ddl-auto: validate`가
> DOMAIN 타입·`smallint`·`char`를 엔티티의 `Integer`/`String`과 다른 타입으로 보고 실패하기 때문이다.
> 도메인 목록은 `erd/domains.csv`, 컬럼별 도메인은 `erd/domain_columns.csv`, 사용 컬럼 전체 목록은 `09_domain_usage.md`(자동 생성).

## 9.1 도메인 (DB에는 자료형 + CHECK로 구현)

| 도메인 분류 | 도메인명 | 자료형 | 허용 값 | 예시 | 쓰는 곳 |
|---|---|---|---|---|---|
| 식별자 | d_team_id | varchar(2) | 영문 대문자 2자 | OB, SK, WO | 팀ID |
| 식별자 | d_player_id | integer | 1 이상 | 76232 | 선수ID, 투수ID, 타자ID |
| 식별자 | d_match_id | varchar(14) | `YYYYMMDD_` + 팀코드 4자 + 더블헤더 1자리 | 20250601_OBWO0 | 경기ID |
| 시간 | d_season | integer | 1982 ~ 2100 | 2025 | 시즌, 지명연도, 입단연도 |
| 순서 | d_inning | integer | 1 ~ 18 | 9 | 이닝 |
| 수량 | d_count | integer | 0 이상 | 4 | 경기 단위 횟수 (타수, 안타 …) |
| 수량 | d_total | integer | 0 이상 | 162 | 시즌 누적 횟수 |
| 수량 | d_outs | integer | 0 이상 | 19 (=6⅓이닝) | 투수 아웃카운트 |
| 비율 | d_rate | numeric(4,3) | 0 ~ 1 | 0.312 | 타율, 출루율, 승률 |
| 비율 | d_slg | numeric(5,3) | 0 ~ 5 | 0.875 | 장타율, OPS |
| 비율 | d_era | numeric(6,2) | 0 이상 | 3.21 | 평균자책점, WHIP |
| 코드 | d_hand | varchar(1) | L, R, S | R | 투구손(L/R), 타격방향(L/R/S) |
| 명칭 | d_person_name | varchar(30) | 공백만은 불가 | 홍길동 | 선수명, 심판명 |

## 9.2 도메인으로 만들지 않은 공통 형식

| 분류 | 자료형 | 규칙 | 예 |
|---|---|---|---|
| 코드(한 글자) | varchar(1) + CHECK | 값 목록을 CHECK로 제한 | 승패(W/L/D), 홈원정(H/A), 투수결정(W/L/S/H) |
| 코드(문자열) | varchar(n) + FK | 코드표 테이블을 참조 | 타석결과유형, 기타기록유형 |
| 일자 / 시각 / 일시 | date / time / timestamptz | | 경기일자, 개시시각, 수집일시 |
| 여부 | boolean | `is_` 접두어 | is_retired, is_dome |
| 금액 | integer | 단위를 컬럼명에 표시, 통화별 컬럼 분리 | salary_10k_krw(만원), salary_usd |
| 신체 | integer + CHECK | 신장 140~230cm, 체중 40~200kg | |
| 원문 텍스트 | varchar(n) | 화면 표시·추적용, 검색·집계하지 않음 | 경력, 지명정보, 기타기록 원문 |

## 9.3 도메인 결정 근거

1. **이닝을 아웃카운트 정수로**: 6⅓이닝을 6.33(실수)으로 두고 세 경기를 더하면 18.99이닝이 되어 정답 19이닝과 달라진다(아웃 수로는 19 × 3 = 57).
   kbodata의 `61` 표기는 숫자 61로 오해할 수 있다. 정수 아웃 수는 합산이 정확하고, 화면 표시만 `6 1/3`으로 바꾸면 된다.
2. **비율은 numeric**: 타율 .300 을 float로 저장하면 0.29999… 같은 값이 생겨 동률 비교가 틀어질 수 있다.
3. **횟수는 모두 integer**: 처음엔 경기 단위를 smallint로 두었지만, 팀 백엔드(JPA)가 `Integer`로 매핑하고 `ddl-auto: validate`로
   검증하므로 integer로 통일했다. 저장 공간 차이(2바이트)는 이 규모에서 의미가 없다. 범위는 CHECK(0 이상)로 지킨다.
4. **선수ID integer**: KBO playerId는 숫자다. 문자(varchar)보다 조인·인덱스가 가볍다.
5. **팀ID varchar(2) + 정규식 CHECK**: KBO 팀코드는 항상 2자리. `^[A-Z]{2}$` CHECK로 길이·소문자·오타를 막는다.
   char(2)는 JPA `String`과 타입 코드가 달라 validate에서 걸리므로 varchar로 했다.
6. **금액 단위 분리**: 상세 페이지 연봉이 "52000만원", "100000달러"처럼 통화가 섞여 있어 한 컬럼에 넣으면 비교가 불가능하다.

## 9.4 Spring(JPA) 매핑 메모 (김경주 참고)

팀 레포 설정(`ddl-auto: validate`)에 맞춰 DB에는 JPA가 바로 검증할 수 있는 기본 자료형만 쓴다.

| 도메인 / DB 자료형 | Java 타입 |
|---|---|
| d_player_id, d_season, d_inning, d_count, d_total, d_outs → integer | Integer |
| 대리키 id → bigint | Long (`@GeneratedValue(strategy = GenerationType.IDENTITY)`) |
| d_rate, d_slg, d_era → numeric(p,s) | BigDecimal (`@Column(precision = p, scale = s)`) |
| d_team_id, d_match_id, d_hand, d_person_name → varchar(n) | String (`@Column(length = n)`) |
| date / time / timestamptz | LocalDate / LocalTime / OffsetDateTime |
| boolean | Boolean |

`match.season`, `match.kbo_match_id`처럼 DB가 계산하는 생성 컬럼은 `@Column(insertable = false, updatable = false)`.
