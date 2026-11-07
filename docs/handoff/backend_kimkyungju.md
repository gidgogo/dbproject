# 김경주(백엔드·Spring)에게 — DB 사용 안내

> 팀 레포(gidgogo/KBO) 설정 기준: Spring Boot 4.1 · JPA · Flyway · `ddl-auto: validate` · Postgres 16 docker(localhost:5434, kbo/kbo/kbo).
> 🟡 테이블·컬럼명은 11/10 회의에서 확정. 확정 후 바뀌는 점은 **새 마이그레이션 파일(V3__…)** 로 고친다(머지된 V1·V2는 수정 금지).

## 1. 이 레포에서 팀 레포로 옮길 파일

| 이 레포 | 팀 레포 (같은 경로) | 내용 |
|---|---|---|
| `backend/src/main/resources/db/migration/V1__init_schema.sql` | 같음 | 테이블 21·인덱스·트리거·뷰 16·MV 3·함수 |
| `backend/src/main/resources/db/migration/V2__reference_data.sql` | 같음 | 팀·구장·팀시즌·타석결과 코드표·기타기록 종류 |

팀 레포의 `db/migration` 폴더는 현재 `.gitkeep`만 있으므로 번호가 겹치지 않는다.
데이터 수집·적재(`data-pipeline/`)는 백엔드와 별개라 팀 레포에 넣을지는 회의에서 정한다.

## 2. 로컬 DB 띄우기

```bash
docker compose up -d          # 팀 레포 루트. postgres:16, localhost:5434, DB/계정/비번 모두 kbo
./gradlew bootRun             # backend/. 시작할 때 Flyway가 V1 → V2 적용, 이어서 Hibernate validate
```

- **빈 DB에서 시작한다.** 팀 설정에 `baseline-on-migrate: true`가 있어서, 테이블이 이미 있는 DB(예: 예전 psql 스크립트로 만든 DB)에
  Flyway를 처음 돌리면 그 상태를 V1로 간주하고 V1을 건너뛴다. 예전 DB가 있으면 `docker compose down -v`로 볼륨을 지우고 다시 띄운다.
- 백엔드 없이 스키마만 만들 때는 Flyway CLI 도커를 써도 같다:

```bash
docker run --rm --network host -v "$PWD/backend/src/main/resources/db/migration:/flyway/sql" flyway/flyway:11 \
  -url=jdbc:postgresql://localhost:5434/kbo -user=kbo -password=kbo migrate
```

## 3. 개발용 데이터 넣기

실제 데이터가 오기 전에는 가상 데이터로 API를 개발할 수 있다. 이 레포의 `data-pipeline/` 폴더에서:

```bash
pip install -r requirements.txt
python tests/fixtures/make_synthetic.py
python etl/crawl_to_tables.py --data tests/fixtures/synthetic/data --out data/load
python etl/kbodata_to_tables.py tests/fixtures/synthetic/raw_games.json --players tests/fixtures/synthetic/data/player_season_team.csv --out data/load
PGPASSWORD=kbo psql -h localhost -p 5434 -U kbo -d kbo -f sql/load_data.sql
```

- `sql/load_data.sql`은 Flyway 파일이 아니라 psql 스크립트다(`\copy`로 CSV를 읽음). 마이그레이션 폴더에 넣지 않는다.
- KBO 선수 프로필·기록실 공식 기록만 넣을 때는 `sql/load_kbo.sql` (경기 CSV 불필요).
- 더 큰 가상 데이터(한 시즌 720경기, 시즌 2099)는 `tools/perf_check.sql` 앞부분을 쓰면 된다. **운영 DB에는 넣지 말 것.**
- 현재 소속·등번호는 `player.current_team_name/current_uniform_no`이고 과거 시즌 소속(`player_season`)과 구분한다.

## 4. 엔터티 매핑

아래 규칙으로 21개 테이블 엔터티를 만들어 **Spring Boot 4.1.2 + `ddl-auto: validate` + Flyway** 로 실제로 띄워 통과를 확인했다(2026-11-07).
같은 검사에서 `smallint`·`char(n)`·DOMAIN 컬럼은 각각 `found [int2]`, `found [bpchar]`, `found [d_x (Types#DISTINCT)]` 오류로 실패했다.
그래서 DB에는 이 타입들을 쓰지 않는다.

| DB 자료형 | Java 타입 | 비고 |
|---|---|---|
| `integer` | `Integer` | 시즌·이닝·횟수 전부 |
| `bigint` (대리키 `id`, `match_event.event_id`) | `Long` | `@GeneratedValue(strategy = GenerationType.IDENTITY)` |
| `numeric(p,s)` | `BigDecimal` | 타율·ERA 등 |
| `varchar(n)`, `text` | `String` | 팀ID·경기ID·코드값 |
| `boolean` | `Boolean` | |
| `date` / `time` / `timestamptz` | `LocalDate` / `LocalTime` / `OffsetDateTime` | |

- **복합키 테이블은 `@Id Long id` 하나로 매핑한다.** `match_team`, `inning_score`, `batter_match`, `plate_appearance`, `pitcher_match`,
  `match_umpire`, `player_season`, `player_salary`, `team_season`, `*_official` 은 `id bigint IDENTITY`가 PK이고
  원래의 업무키는 `uq_<테이블>_key` UNIQUE다. `@IdClass`·`@EmbeddedId`는 필요 없다.
- 단일 자연키는 그대로 PK: `team.team_id`(String), `player.player_id`(Integer, KBO playerId), `match.match_id`(String, 예 `20250601_OBWO0`).
  `stadium.stadium_id`, `umpire.umpire_id`는 IDENTITY(Integer).
- FK는 업무키를 참조한다(예: `batter_match(match_id, team_id) → match_team(match_id, team_id)`). 연관관계를 걸 때
  `@JoinColumns`로 `referencedColumnName`을 업무키 컬럼에 맞추거나, 처음에는 FK 컬럼을 단순 값(`String matchId`)으로 두고 조회만 해도 된다.
- **생성 컬럼** `match.season`, `match.kbo_match_id` → `@Column(insertable = false, updatable = false)`.
- `player.throws` 컬럼명은 Java 예약어라 필드명을 바꾼다: `@Column(name = "throws") private String throwingHand;`
- 코드 값: 승패 `W/L/D`, 홈원정 `H/A`, 투수 결정 `W/L/S/H`, 투타 `L/R/S` (CHECK로 제한). enum으로 쓰려면 `@Enumerated(EnumType.STRING)` + 같은 글자.
- 테이블 이름 `match`는 PostgreSQL에서 따옴표 없이 쓸 수 있다(검증함). `@Table(name = "match")`.

### 뷰·MV

- `@Entity @Immutable @Table(name = "v_match_summary")`처럼 읽기 전용 엔터티로 매핑해도 validate를 통과한다(뷰·MV 모두 Boot 4.1.2에서 확인, 추가 설정 불필요).
- 키가 여러 컬럼인 뷰는 `@IdClass`가 필요하므로, 처음에는 `JdbcTemplate`이나 `@Query(nativeQuery = true)` + 인터페이스 프로젝션이 더 간단하다.
- `mv_team_standings.rank`처럼 윈도 함수 결과는 `bigint` → `Long`.

## 5. MV(머티리얼라이즈드 뷰) 갱신 규칙

| 누가 | 언제 | 어떻게 |
|---|---|---|
| 데이터 적재 담당 | 경기 데이터를 적재·수정한 직후 1회 | `data-pipeline/sql/load_data.sql` 마지막 줄 `SELECT fn_refresh_stats();` (자동) |
| 백엔드 | **갱신하지 않는다** | MV는 읽기만. 요청마다 REFRESH 하지 않는다 |

`fn_refresh_stats()`는 `REFRESH MATERIALIZED VIEW CONCURRENTLY`라 갱신 중에도 백엔드 조회가 막히지 않는다.
대상: `mv_season_batting`, `mv_season_pitching`, `mv_team_standings`. 선수 프로필·기록실만 적재(`load_kbo.sql`)할 때는 경기 기록이 안 바뀌므로 갱신이 필요 없다.

## 6. 화면별로 읽으면 되는 테이블·뷰

| 화면 / API | 테이블·뷰 | 조건 예 |
|---|---|---|
| 경기 목록·결과 | `v_match_summary`, `v_match_pitchers` | `match_date = ?` / `season = ? AND (home_team_id = ? OR away_team_id = ?)` |
| 박스스코어 | `match_team`, `inning_score`, `v_batter_match_line`, `pitcher_match`, `match_event` | `match_id = ?` |
| 선수 프로필 | `player`, `player_season`, `player_salary` | `player_id = ?` |
| 선수 시즌 표 (b-ref식) | `season_batting_official`, `season_pitching_official` | `player_id = ? ORDER BY season` |
| 선수 비교 | 위 표를 두 선수로 조회 + `v_batting_percentile` | `player_id IN (?, ?) AND season = ?` |
| 팀 프로필 | `team`, `team_season`, `v_team_head_to_head` | `team_id = ?` |
| 순위 | `team_rank_official` (공식) / `mv_team_standings` (경기 기록으로 계산) | `season = ? ORDER BY rank` |
| 시각화 | 공식 시즌 기록 비교, 경기 적재 후 `v_spray_chart`·`v_batting_percentile` | `player_id = ? AND season = ?` |

경기 관련 화면·상대전적·백분위는 실제 박스스코어 적재 전까지 준비 상태로 표시한다. 네이버 문자중계(투구 단위)는 구현하지 않는다.

## 7. 데이터 품질 확인

적재 후 아래 검증 뷰에 행이 나오면 데이터 문제다.

`v_check_team_runs`, `v_check_team_hits`, `v_check_batter_pa`, `v_check_match_result`, `v_check_pitcher_decision`,
`v_compare_batting_official`, `v_compare_pitching_official`, `v_compare_team_rank`
