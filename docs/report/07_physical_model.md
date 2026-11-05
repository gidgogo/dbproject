# 7. 물리적 데이터 모델

> 담당: 이성수·김경주 · 초안 v0 (2026-11-05) · DDL: `erd/ddl/` · 테이블 기술서: `docs/report/10_table_spec.md`(자동 생성)

## 7.1 DBMS와 객체 구성

- PostgreSQL 16에서 실행 확인 (14 이상이면 동작). 스키마는 기본 `public`.
- 실행 순서: `erd/ddl/00_create_all.sql` 하나로 아래를 모두 실행한다.

| 파일 | 내용 | 개수 |
|---|---|---|
| 01_domains.sql | 도메인 (자료형 + CHECK) | 13 |
| 02_tables.sql | 테이블, PK·FK·UNIQUE·CHECK, 컬럼 주석 | 테이블 24, FK 34 |
| 03_indexes.sql | 조회용 보조 인덱스 | 15 (+ MV 인덱스 5) |
| 04_triggers.sql | 팀경기기록 홈/원정 일치 트리거 | 1 |
| 05_views.sql | 화면용 뷰·MV, 검증 뷰, 함수 | 뷰 18, MV 3, 함수 3 (+트리거 함수 1) |
| 06_reference_data.sql | 기준 데이터 적재 (data/reference) | |
| 07_load_data.sql / 08_load_pitch.sql | 수집 데이터 적재 (재실행 안전) | |
| 99_drop_all.sql | 개발용 전체 삭제 | |

## 7.2 명명 규칙 🟡 (김경주와 합의 필요)

- 테이블·컬럼: 영어 소문자 snake_case, 테이블은 단수형 (`player`, `batter_game`)
- 식별자 컬럼: `<엔터티>_id` (`player_id`, `game_id`), 코드 컬럼: `_code`, 여부: `is_` 접두어
- 횟수: 복수형 영어 (`hits`, `at_bats`), 단위가 있으면 접미어 (`height_cm`, `speed_kmh`, `salary_10k_krw`)
- 제약조건: `pk_<표>`, `fk_<표>_<부모>`, `uq_<표>_<컬럼>`, `ck_<표>_<내용>`, 인덱스 `ix_<표>_<컬럼>`
- 공식(기록실) 저장 테이블은 `_official`, 뷰는 `v_`, 머티리얼라이즈드 뷰는 `mv_` 접두어

## 7.3 자료형과 도메인

도메인 정의서(9장)를 PostgreSQL `CREATE DOMAIN`으로 옮겼다. 같은 의미의 컬럼은 같은 도메인을 써서
허용 범위가 한곳에서 관리된다. (예: 모든 선수ID는 `d_player_id` = 양의 정수)

주요 결정
- **이닝은 아웃카운트 정수로 저장**: kbodata `61`(=6⅓이닝), 기록실 `144 1/3` 모두 아웃 수(19, 433)로 바꾼다.
  소수(6.33)로 저장하면 6⅓+⅔ 같은 합산이 부정확하다. 표시는 함수 `fn_ip_display(19) = '6 1/3'`.
- 타율·출루율·승률: `numeric(4,3)` (0~1), 장타율·OPS: `numeric(5,3)` (최대 4.000/5.000), ERA: `numeric(6,2)`.
  부동소수(`real`)는 반올림 오차 때문에 쓰지 않았다.
- 경기 단위 횟수는 `smallint`(최대 32767), 시즌 누적은 `integer`.
- 돈: 원화는 **만원 단위 정수**(`salary_10k_krw`), 외국인 달러 연봉은 별도 컬럼(`salary_usd`) — 한 컬럼에 단위가 섞이지 않게.
- 투구 좌표는 원본(PITCHf/x) 단위인 **피트(ft)** 그대로 `numeric(6,3)`.

## 7.4 무결성 제약

### CHECK (업무 규칙)

| 규칙 | 제약 |
|---|---|
| 안타 ≤ 타수 | `ck_batter_game_hits`, `ck_sbo_hits` |
| 자책점 ≤ 실점, 피홈런 ≤ 피안타 ≤ 피타수 ≤ 상대타자수 | `ck_pitcher_game_er/hr/hits/ab` |
| 홈팀 ≠ 원정팀, 더블헤더 0~2 | `ck_game_teams`, `ck_game_doubleheader` |
| 경기ID = 날짜_원정팀홈팀더블헤더 | `ck_game_id_parts` (지능형 키 일관성) |
| 승패는 W/L/D, 투수 결정은 W/L/S/H | `ck_team_game_result`, `ck_pitcher_game_decision` |
| 볼카운트 0~3 / 0~2, 구속 50~175km/h | `ck_pitch_count`, `ck_pitch_speed` |
| 안타 유형이면 루타 > 0 이고 타수 포함 | `ck_pa_result_type_hit`, `ck_pa_result_type_ab` |
| 순위표 승+패+무 = 경기 | `ck_tro_games` |

### 트리거

`trg_team_game_check_side` — 팀경기기록의 (팀ID, 홈원정구분)이 경기의 홈팀·원정팀과 일치해야 한다.
홈/원정만 바꾸는 UPDATE는 `ck_game_id_parts`가 막고, 경기ID까지 바꾸면 CASCADE로 전파된 뒤 트리거가 다시 검사한다.

### 참조 무결성 정책 (ON DELETE / ON UPDATE)

| 관계 유형 | 정책 | 예 | 이유 |
|---|---|---|---|
| 부모가 없으면 의미 없는 하위 기록 | ON DELETE **CASCADE** | 경기 → 팀경기기록 → 타자경기기록 → 타석 | 잘못 적재한 경기를 지우고 다시 넣을 때 하위 기록이 함께 정리됨 (적재 스크립트가 이 방식을 씀) |
| 다른 기록이 참조하는 기준 정보 | ON DELETE **RESTRICT** | 선수, 팀, 타석결과코드 | 경기 기록이 있는 선수를 실수로 지우면 기록이 고아가 됨 → 막는다 |
| 없어도 되는 선택 정보 | ON DELETE **SET NULL** | 구장, 경기기타기록의 선수 | 구장 정보를 지워도 경기는 남아야 함 |
| 식별자 값 수정 | ON UPDATE **CASCADE** | 선수ID 정정 | playerId 매핑 오류를 고치면 하위 기록에 자동 반영 |
| 생성 컬럼이 들어간 FK | NO ACTION | 경기(팀ID, 시즌) → 팀시즌 | 생성 컬럼은 CASCADE로 바꿀 수 없음 |

테스트(`tests/test_db.py`)에서 경기 삭제 시 CASCADE, 기록 있는 선수 삭제 시 RESTRICT 거부를 확인했다.

## 7.5 인덱스 설계

PK·UNIQUE는 자동 인덱스가 생긴다. 복합 PK `(game_id, player_id)`는 경기로는 찾지만 선수로는 못 찾으므로,
화면별 조회 패턴 중 **PK의 첫 컬럼이 아닌 조건**만 보조 인덱스를 만들었다.

| 화면 / 조회 | 조건 | 인덱스 |
|---|---|---|
| 경기 결과: 날짜별 경기 | `game_date = ?` | `ix_game_date` |
| 팀 프로필: 팀의 시즌 경기 | `home_team_id = ? AND season = ?` | `ix_game_home_team`, `ix_game_away_team`, `ix_team_game_team` |
| 선수 프로필: 선수의 경기 기록 | `player_id = ?` | `ix_batter_game_player`, `ix_pitcher_game_player` |
| 선수 프로필: 선수의 타석 집계 (2루타·홈런·볼넷…) | `plate_appearance.player_id = ?` | `ix_pa_player` (성능 확인 중 발견해 추가, 7.8) |
| 선수 검색·이름 매핑 | `player_name = ?`, `(season, team_id, name_in_season)` | `ix_player_name`, `ix_player_season_lookup` |
| 시각화: 투수의 구종별 투구 | `pitcher_id = ? (AND pitch_type_ko = ?)` | `ix_pitch_pitcher` |
| 시즌 성적 MV | `(player_id, season, team_id)` | MV 유니크 인덱스 (REFRESH CONCURRENTLY 가능) |

성능 확인: `tools/perf_check.sql` 로 한 시즌 규모 가상 데이터에서 인덱스 사용 여부를 `EXPLAIN ANALYZE`로 확인한다
(결과는 7.8).

## 7.6 뷰 / 머티리얼라이즈드 뷰

| 이름 | 종류 | 용도 |
|---|---|---|
| v_game_summary, v_game_pitchers | 뷰 | 경기 결과 화면 (팀명·점수·승리팀·구장, 선발·승·패·세 투수) |
| v_batter_game_line | 뷰 | 타자 경기별 기록 + 타석 결과 집계(2루타·홈런·볼넷·삼진…) |
| mv_season_batting / v_season_batting_total | MV / 뷰 | 시즌 타격 (팀별 / 이적 합산) — 타율·출루율·장타율·OPS |
| mv_season_pitching / v_season_pitching_total | MV / 뷰 | 시즌 투구 — ERA, WHIP(사구 포함 근사), QS |
| mv_team_standings | MV | 순위·승률·게임차·최근10경기·연속 (윈도 함수) |
| v_team_head_to_head | 뷰 | 상대 전적 |
| v_spray_chart | 뷰 | 타구 방향(5구역) × 결과 유형 |
| v_pitch_detail, v_pitch_mix | 뷰 | 존 구역(Statcast 1~9, 11~14), 구종 비율·구속·헛스윙률 |
| v_batting_percentile | 뷰 | 규정타석 이상 타자 백분위 (Savant 퍼센타일 막대) |
| v_check_* | 검증 뷰 | 행이 나오면 데이터 문제 (득점 합, 안타 합, 타석 변환, 승패, 투수 결정) |
| v_compare_* | 검증 뷰 | 기록실 공식 값 vs 계산 값 (일치율) |

**뷰 vs MV**: 시즌 성적·순위는 화면에서 자주 읽고 데이터 적재 때만 바뀐다 → MV로 계산 결과를 저장하고
적재 후 `SELECT fn_refresh_stats();` 로 갱신한다(07_load_data.sql 마지막 줄). MV에는 유니크 인덱스가 있어
서비스 중에도 `REFRESH MATERIALIZED VIEW CONCURRENTLY`로 읽기를 막지 않고 갱신할 수 있다.

**저장된 유도 값의 불일치 문제**: 만약 시즌 타율을 테이블에 저장했다면, 경기 기록 한 건을 고칠 때 시즌 표도
같이 고쳐야 한다(갱신 이상). MV는 "언제 갱신했는가"만 관리하면 되고, `v_compare_batting_official`로
공식 값과의 차이를 언제든 확인할 수 있다.

## 7.7 계산식 (뷰에 구현된 정의)

| 지표 | 식 | 비고 |
|---|---|---|
| 타율 AVG | H / AB | |
| 출루율 OBP | (H + BB + HBP) / (AB + BB + HBP + SF) | 고의4구는 BB에 포함 |
| 장타율 SLG | TB / AB, TB = H + 2B + 2×3B + 3×HR | |
| OPS | OBP + SLG (반올림 전 값으로 더함) | |
| 평균자책점 ERA | ER × 27 / 아웃카운트 | = ER × 9 / IP |
| WHIP | (피안타 + 4사구) × 3 / 아웃카운트 | kbodata가 볼넷·사구를 합쳐 주므로 **사구 포함 근사값** (공식 WHIP와 차이 가능) |
| 퀄리티스타트 | 선발, 6이닝(18아웃) 이상, 자책 3 이하 | |
| 승률 | 승 / (승 + 패) | ❓ 2008~2010 무승부 규정 확인 |
| 게임차 | ((1위 승 − 승) + (패 − 1위 패)) / 2 | |
| 규정타석 | 팀 경기 수 × 3.1 | 백분위 대상 |

## 7.8 성능 확인 (EXPLAIN ANALYZE)

**방법**: `tools/perf_check.sql`이 별도 DB에 한 시즌 규모의 **가상 데이터**(경기 720, 타자 기록 12,960,
타석 51,840, 투수 기록 4,320행)를 만들고 화면별 대표 조회의 실행 계획을 출력한다.
전체 출력: `docs/report/07_perf_result.txt` (PostgreSQL 16, 클라우드 개발 환경. 절대 시간은 환경마다 다름)

| 조회 | 실행 계획 요약 | 실행 시간 |
|---|---|---:|
| Q1 선수 경기별 타격 (`batter_game.player_id = ?`) | Bitmap Index Scan on `ix_batter_game_player` (144행) | 0.04 ms |
| Q1 비교: 같은 조회, 인덱스 삭제 | **Seq Scan** — 12,960행 중 12,816행 버림 | 0.73 ms (약 20배) |
| Q2 하루 경기 목록 (`v_game_summary`) | `ix_game_date` 인덱스 → 5경기만 조인 | 0.37 ms |
| Q3 선수 시즌 성적 (MV 읽기) | MV에서 1행 | 0.02 ms |
| Q3 비교: MV 없이 경기 기록에서 직접 집계 | 타자 기록 144행 + 타석 576행 집계 | 1.09 ms |
| Q4 순위 화면 (`mv_team_standings`) | MV 10행 정렬 | 0.04 ms |
| MV 3개 다시 계산 (`fn_refresh_stats`) | 적재 후 1회 | 약 83 ms |

**발견하고 고친 것**: 처음 측정 때 Q3 비교 조회에서 `plate_appearance`를 **순차 탐색**(51,840행 중 51,264행 버림)했다.
PK가 `(game_id, player_id, inning, seq_in_inning)`라 `player_id`만으로는 PK 인덱스를 쓸 수 없기 때문이다.
`ix_pa_player`를 추가한 뒤 Bitmap Index Scan으로 바뀌었고 3.57 ms → 1.09 ms로 줄었다.
2008~2025 전체를 적재하면 타석이 약 100만 행(시즌당 약 5만)이 되므로 차이는 더 커진다.

**결론**: 시즌 성적·순위처럼 많이 읽는 유도 값은 MV로 미리 계산해 두면 조회는 수십 배 빠르고, 갱신 비용은 적재 때 1회(0.1초 미만)뿐이다.
