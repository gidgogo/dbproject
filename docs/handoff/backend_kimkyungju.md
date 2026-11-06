# 김경주(백엔드·Spring)에게 — DB 사용 안내

> 🟡 컬럼명은 11/10 회의에서 확정. 바뀌면 `erd/ddl/02_tables.sql`을 고치고 `tools/gen_erd_docs.py`로 문서를 다시 만든다.

## 1. 로컬 DB 만들기 (5분)

```bash
createdb kbo
```

```bash
psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/00_create_all.sql
```

레포 최상위 폴더에서 실행해야 한다(기준 데이터 CSV를 상대 경로로 읽음). 실제 데이터가 오기 전에는
가상 데이터로 API를 개발할 수 있다.

```bash
python tests/fixtures/make_synthetic.py
```

```bash
python etl/crawl_to_tables.py --data tests/fixtures/synthetic/data --out data/load && python etl/kbodata_to_tables.py tests/fixtures/synthetic/raw_games.json --players tests/fixtures/synthetic/data/player_season_team.csv --out data/load
```

```bash
psql -d kbo -f erd/ddl/07_load_data.sql
```

더 큰 가상 데이터(한 시즌 720경기, 시즌 2099)는 `tools/perf_check.sql` 앞부분을 쓰면 된다.

KBO 실제 CSV만 적재하려면 `python etl/crawl_to_tables.py` 후 `11_load_kbo.sql`을 실행한다.
기존 DB 전환은 `10_kbo_only.sql`을 먼저 실행한다. 네이버 API·투구 엔터티는 구현하지 않는다.
현재 소속·등번호는 `player.current_team_name/current_uniform_no`이고 과거 시즌 소속과 구분한다.
경기 관련 화면·상대전적·백분위는 실제 박스스코어 적재 전까지 준비 상태로 표시한다.

## 2. application.yml 권장 설정

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/kbo
  jpa:
    hibernate:
      ddl-auto: none        # 스키마는 SQL 스크립트로 관리 (도메인 타입 때문에 validate 도 끄기)
    properties:
      hibernate.default_schema: public
```

## 3. 엔터티 매핑 메모

- 복합 PK 테이블이 많다: `batter_game(game_id, player_id)`, `team_game(game_id, team_id)`, `plate_appearance(game_id, player_id, inning, seq_in_inning)`,
  `player_season(player_id, season, team_id)` … → `@IdClass` 또는 `@EmbeddedId`
- 자료형: smallint 계열(d_count, d_inning, d_season) → `Short`(또는 `Integer`), numeric → `BigDecimal`, char(2) → `String`
- `game.season`, `game.kbo_game_id` 는 **생성 컬럼**이라 INSERT/UPDATE 금지 → `@Column(insertable = false, updatable = false)`
- `game_event.event_id` 는 `GENERATED ALWAYS AS IDENTITY` → `@GeneratedValue(strategy = IDENTITY)`
- 뷰·MV는 읽기 전용 엔터티로: `@Entity @Immutable @Table(name = "mv_season_batting")` + 복합 키

## 4. 화면별로 읽으면 되는 뷰

| 화면 / API | 뷰 | 조건 예 |
|---|---|---|
| 경기 목록·결과 | `v_game_summary`, `v_game_pitchers` | `game_date = ?` / `season = ? AND (home_team_id = ? OR away_team_id = ?)` |
| 박스스코어 | `team_game`, `inning_score`, `v_batter_game_line`, `pitcher_game`, `game_event` | `game_id = ?` |
| 선수 프로필 | `player`, `player_season`, `player_salary` | `player_id = ?` |
| 선수 시즌 표 (b-ref식) | `season_batting_official`, `season_pitching_official` | `player_id = ? ORDER BY season` |
| 선수 비교 | 위 뷰를 두 선수로 조회 + `v_batting_percentile` | `player_id IN (?, ?) AND season = ?` |
| 팀 프로필 | `team`, `team_season`, `v_team_head_to_head` | `team_id = ?` |
| 순위 | `team_rank_official` | `season = ? AND as_of_date = ? ORDER BY rank` |
| 시각화 | 공식 시즌 기록 비교, 경기 적재 후 `v_spray_chart`·`v_batting_percentile` | `player_id = ? AND season = ?` |

시즌 성적·순위 MV는 데이터 적재 후 `SELECT fn_refresh_stats();` 로 갱신한다(07_load_data.sql 마지막 줄에 포함).

## 5. 데이터 품질 확인

적재 후 아래 검증 뷰에 행이 나오면 데이터 문제다.

`v_check_team_runs`, `v_check_team_hits`, `v_check_batter_pa`, `v_check_game_result`, `v_check_pitcher_decision`,
`v_compare_batting_official`, `v_compare_pitching_official`, `v_compare_team_rank`
