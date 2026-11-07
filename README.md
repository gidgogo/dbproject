# KBO 야구 기록 DB — 데이터베이스응용 텀프로젝트

KBO 공식 선수·시즌 기록·팀 순위를 관리하는 PostgreSQL 데이터베이스입니다.
**2026-11-06 결정: 네이버 문자중계 수집을 제외하고, 실제 수집 가능한 KBO 데이터를 사용합니다.**
구종 비율·구속 분포·스트라이크존 히트맵은 구현 범위에서 제외합니다.

현재 제공할 수 있는 화면은 선수 프로필·비교, 시즌 타자·투수 기록, 팀별 시즌 기록과 순위입니다.
경기 결과·상대전적·타구 방향·경기 기반 백분위는 기존 kbodata 경기 데이터가 적재된 뒤 사용할 수 있습니다.
수비·주루 전용 시즌 기록과 엔트리 등록·말소는 아직 수집하지 않으므로 이번 확정 범위에 포함하지 않습니다.

## 팀 레포와의 관계

팀 공용 레포 [gidgogo/KBO](https://github.com/gidgogo/KBO)(김경주 설정)가 기준입니다. 이 레포는 그 규칙에 맞춰 정리했습니다.

| 팀 레포 규칙 | 이 레포에서 |
|---|---|
| Flyway: `backend/src/main/resources/db/migration/V{n}__{설명}.sql`, 머지된 파일 수정 금지 | 스키마 `V1__init_schema.sql`, 기준 데이터 `V2__reference_data.sql` (같은 경로) |
| JPA `ddl-auto: validate` | DOMAIN·`smallint`·`char` 대신 `integer`·`varchar` + CHECK. 복합키 테이블은 `id bigint` 대리키 + 업무키 UNIQUE |
| 패키지 `player` / `team` / `match` | 경기 테이블 이름 `match`, `match_team`, `batter_match`, `pitcher_match`, `match_event`, `match_umpire` |
| docker Postgres 16 `localhost:5434`, DB·계정·비번 `kbo` | 문서·예시 명령을 모두 이 접속 정보로 맞춤 |
| 브랜치 `<type>/<설명>` → PR → 리뷰 → squash, Conventional Commits | 같은 방식 (`feat(data): …`, `docs(erd): …`) |

## 먼저 볼 파일

- [개념 ERD](erd/img/erd_conceptual.png) · [논리 ERD](erd/img/erd_logical.svg) · [DBML](erd/kbo_erd.dbml)
- [논리 모델 설명](docs/report/06_logical_model.md) · [물리 모델](docs/report/07_physical_model.md) · [테이블 기술서](docs/report/10_table_spec.md)
- [백엔드 인계(김경주)](docs/handoff/backend_kimkyungju.md) · [전처리 인계(배인표)](docs/handoff/preprocessing_baeinpyo.md)
- [수집·적재 가이드](data-pipeline/crawl/README.md) · [실제 수집 결과](docs/collection_status.md)

## 빠른 시작

**1) DB 스키마** — 팀 레포 루트에서 `docker compose up -d` 후 백엔드를 실행하면 Flyway가 V1·V2를 적용합니다.
백엔드 없이 스키마만 만들 때는 Flyway CLI 도커를 씁니다(이 레포 루트에서).

```bash
docker run --rm --network host -v "$PWD/backend/src/main/resources/db/migration:/flyway/sql" flyway/flyway:11 \
  -url=jdbc:postgresql://localhost:5434/kbo -user=kbo -password=kbo migrate
```

**2) 수집·적재** — `data-pipeline/` 폴더에서 실행합니다.

```bash
cd data-pipeline
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python crawl/kbo_records.py --seasons 2025
python crawl/kbo_profiles.py --seasons 2025
python crawl/kbo_team_rank.py --dates 2025-10-31
python etl/crawl_to_tables.py
PGPASSWORD=kbo psql -h localhost -p 5434 -U kbo -d kbo -v ON_ERROR_STOP=1 -f sql/load_kbo.sql
```

`sql/load_kbo.sql`은 경기 CSV 없이 실행할 수 있고 기존 경기 기록을 건드리지 않습니다.
경기 JSON을 확보했다면 [수집 가이드](data-pipeline/crawl/README.md)의 박스스코어 적재 절차(`sql/load_data.sql`)를 사용합니다.
현재 소속명은 상무 등도 원문으로 보존하고, 과거 소속은 `player_season`에서 조회합니다.
현재 상세 페이지의 연봉은 수집 대상 시즌(예: 2025)의 과거 연봉으로 소급하지 않습니다.

**3) 시즌 성적·순위 MV 갱신** — 데이터 적재 담당이 경기 데이터를 넣은 직후 한 번 합니다.
`sql/load_data.sql` 마지막 줄이 `SELECT fn_refresh_stats();`(CONCURRENTLY)를 자동으로 호출하므로 따로 할 일은 없습니다.
백엔드는 MV를 읽기만 합니다.

## 폴더 구성

| 폴더 | 내용 |
|---|---|
| `backend/src/main/resources/db/migration/` | Flyway 마이그레이션 (팀 레포에 같은 경로로 옮김) |
| `data-pipeline/crawl/` | KBO 기록실·선수 상세·순위·동명이인 확인용 일자별 기록, kbodata 보정 |
| `data-pipeline/etl/` | 수집 CSV·경기 JSON을 DB 적재용 CSV로 변환 |
| `data-pipeline/sql/` | 적재용 psql 스크립트 (`\copy`, Flyway 아님) |
| `data-pipeline/data/` | 기준 데이터와 수집 CSV (`raw/`, `load/`는 git 제외) |
| `data-pipeline/tests/` | 파서·변환·마이그레이션·DB 적재 검증 |
| `erd/` | ERD 그림·DBML·Mermaid, 도메인 정의 CSV |
| `docs/` | 모델 보고서, 수집 결과, 인수인계, 회의 문서 |
| `tools/` | DB 기반 ERD·기술서 생성, 기준 데이터 마이그레이션 생성, 그림 렌더링, 성능 확인 |

## 검증

```bash
cd data-pipeline
PGHOST=localhost PGPORT=5434 PGUSER=kbo PGPASSWORD=kbo python -m pytest tests -q -rs
```

DB 테스트는 `psql`과 PostgreSQL 접속이 필요합니다. 마이그레이션 V1·V2를 Flyway와 같은 순서로 적용한 뒤 적재·제약조건을 확인합니다.
테스트용 DB(`KBO_TEST_DB`, 기본 `kbo_pytest`)를 매번 지우고 새로 만들므로 운영 DB 이름(`kbo`)을 지정하지 않습니다.
실제 수집과 가상 데이터 검증 범위는 [수집 결과](docs/collection_status.md)에 구분해 기록합니다.

기준 데이터 CSV(`data-pipeline/data/reference/`)를 고친 뒤에는 V2를 고치지 말고 새 버전을 만듭니다.

```bash
python tools/gen_reference_migration.py --version 3 --name reference_data_update
```

## 담당과 출처

백엔드 김경주, 전처리 배인표, ERD·추가 수집 이성수.
교수님은 데이터 수집 방법은 신경 쓰지 않는다고 말씀하셨으며 별도 문의는 필요하지 않습니다.
데이터 출처는 KBO 공식 홈페이지이며, 박스스코어 도구 kbo-data는 MIT 라이선스입니다.
코드표 발췌의 라이선스는 `data-pipeline/data/reference/LICENSE.kbodata`에 보존합니다.
