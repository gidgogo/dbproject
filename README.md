# KBO 야구 기록 DB — 데이터베이스응용 텀프로젝트

KBO 공식 선수·시즌 기록·팀 순위를 관리하는 PostgreSQL 데이터베이스입니다.
**2026-11-06 결정: 네이버 문자중계 수집을 제외하고, 실제 수집 가능한 KBO 데이터를 사용합니다.**
구종 비율·구속 분포·스트라이크존 히트맵은 구현 범위에서 제외합니다.

현재 제공할 수 있는 화면은 선수 프로필·비교, 시즌 타자·투수 기록, 팀별 시즌 기록과 순위입니다.
경기 결과·상대전적·타구 방향·경기 기반 백분위는 기존 kbodata 경기 데이터가 적재된 뒤 사용할 수 있습니다.
수비·주루 전용 시즌 기록과 엔트리 등록·말소는 아직 수집하지 않으므로 이번 확정 범위에 포함하지 않습니다.

## 먼저 볼 파일

- [개념 ERD](erd/img/erd_conceptual.png) · [논리 ERD](erd/img/erd_logical.svg) · [DBML](erd/kbo_erd.dbml)
- [논리 모델 설명](docs/report/06_logical_model.md) · [테이블 기술서](docs/report/10_table_spec.md)
- [수집·적재 가이드](crawl/README.md) · [실제 수집 결과](docs/collection_status.md)

## 빠른 시작

레포 최상위 폴더에서 실행합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r crawl/requirements.txt
python crawl/kbo_records.py --seasons 2025
python crawl/kbo_profiles.py --seasons 2025
python crawl/kbo_team_rank.py --dates 2025-10-31
python etl/crawl_to_tables.py
createdb kbo
psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/00_create_all.sql
psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/11_load_kbo.sql
```

`11_load_kbo.sql`은 경기 CSV 없이 실행할 수 있습니다. 기존 경기 기록도 건드리지 않습니다.
경기 JSON을 별도로 확보했다면 [수집 가이드](crawl/README.md)의 박스스코어 적재 절차를 사용합니다.

**기존 버전 DB가 있다면** 새로 만들지 말고 아래 순서로 전환합니다.

```bash
psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/10_kbo_only.sql
python etl/crawl_to_tables.py
psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/11_load_kbo.sql
```

전환은 기존 `pitch`, `pitch_type`, `pitch_result`와 관련 뷰·함수를 `legacy_naver`에 보존하고,
현재 프로필의 소속명·등번호·출처 컬럼을 추가합니다. 새 DB에는 네이버 객체를 만들지 않습니다.
현재 소속명은 상무 등도 원문으로 보존하고, 과거 소속은 `player_season`에서 조회합니다.
현재 상세 페이지의 연봉은 수집 대상 시즌(예: 2025)의 과거 연봉으로 소급하지 않습니다.

## 폴더 구성

| 폴더 | 내용 |
|---|---|
| `erd/` | 21개 테이블의 ERD·DBML·PostgreSQL DDL |
| `crawl/` | KBO 기록실·선수 상세·순위·동명이인 확인용 일자별 기록, kbodata 보정 |
| `etl/` | 수집 CSV·경기 JSON을 DB 적재용 CSV로 변환 |
| `data/` | 기준 데이터와 수집 CSV (`raw/`, `load/`는 git 제외) |
| `docs/` | 모델 보고서, 수집 결과, 인수인계, 회의 문서 |
| `tools/` | DB 기반 ERD·기술서 생성, 그림 렌더링, 성능 확인 |
| `tests/` | 파서·변환·DB 적재·기존 DB 전환 검증 |

## 검증

```bash
python -m pytest tests -q -rs
```

DB 테스트는 `psql`과 PostgreSQL 접속이 필요합니다(`PGHOST`/`PGPORT`/`PGUSER`).
테스트용 DB(`KBO_TEST_DB`, 기본 `kbo_pytest`)를 재생성하므로 서비스 DB 이름을 지정하지 않습니다.
실제 수집과 가상 데이터 검증 범위는 [수집 결과](docs/collection_status.md)에 구분해 기록합니다.

## 담당과 출처

백엔드 김경주, 전처리 배인표, ERD·추가 수집 이성수.
교수님은 데이터 수집 방법은 신경 쓰지 않는다고 말씀하셨으며 별도 문의는 필요하지 않습니다.
데이터 출처는 KBO 공식 홈페이지이며, 박스스코어 도구 kbo-data는 MIT 라이선스입니다.
코드표 발췌의 라이선스는 `data/reference/LICENSE.kbodata`에 보존합니다.
