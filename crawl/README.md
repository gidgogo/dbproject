# KBO 수집·적재 가이드

네이버 수집은 제외했다. 모든 명령은 레포 최상위 폴더에서 실행한다.

## 1. 준비

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r crawl/requirements.txt
```

페이지 구조가 바뀌어 실패하면 `python crawl/probe_kbo.py --season 2025`로 확인한다.

## 2. 선수 목록과 시즌 타자·투수 기록

```bash
python crawl/kbo_records.py --seasons 2025
```

한 팀만 시험하려면 `--teams OB`를 붙인다. 결과는 `data/player_season_team.csv`,
`data/season_batting.csv`, `data/season_pitching.csv`다.
시즌·팀·타자/투수·Basic1/2 단위로 완료를 기록하므로 같은 명령으로 이어받을 수 있다.
정규시즌 선택 후 연도를 바꾸며, 빈 표·반복 페이지·잘못된 시즌/팀을 완료 처리하지 않는다.
실패 시 종료 코드 1과 로그를 확인한다. 성공한 단위는 남으므로 파일 존재만으로 전체 완료라 판단하지 않는다.

## 3. 선수 상세

```bash
python crawl/kbo_profiles.py --seasons 2025
```

시험하려면 `--limit 20`. 이미 받은 선수는 건너뛰고 `--refresh`로 갱신한다.
결과는 `data/players.csv`, 실패 ID는 `data/raw/kbo/profiles/_failed.txt`에 기록한다.
일부 실패도 종료 코드 1로 알리며, 성공한 프로필은 저장한다.

프로필은 **조회 시점의 값**이다. `--seasons 2025`는 대상 선수 목록을 고를 뿐, 2025 프로필을 복원하지 않는다.
현재 소속명(상무 포함)·등번호·수집 시각·URL을 `player`에 저장하며 과거 소속은 `player_season`을 사용한다.
연봉 기준 연도는 `--salary-season`으로 지정한다(기본 3~12월 올해, 1~2월 전년이라는 추정 규칙).
페이지에 과거 시즌 근거가 없으므로 과거 연봉으로 표시하지 않는다. 필요하면 원문과 기준 연도를 별도로 확인한다.

## 4. 기준일별 팀 순위

```bash
python crawl/kbo_team_rank.py --dates 2025-10-31
```

결과는 `data/team_rank.csv`. 기준일은 `as_of_date`에 보존한다.

## 5. KBO 수집 결과만 DB에 적재

```bash
python etl/crawl_to_tables.py
createdb kbo
psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/00_create_all.sql
psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/11_load_kbo.sql
```

DB를 이미 만들었다면 `createdb`·`00_create_all.sql`을 반복하지 않는다.
옛 네이버 포함 설계에서 전환할 때는 먼저 `10_kbo_only.sql`을 실행한다.
전환 뒤에는 ETL을 다시 실행해야 새 프로필 컬럼 순서로 적재된다.
`11_load_kbo.sql`은 재실행 가능하며 경기 파일이 필요 없다.

화면은 `player`, `player_season`, `player_salary`, `season_batting_official`,
`season_pitching_official`, `team_rank_official`을 읽는다. 경기 MV가 비어 있어도 공식 시즌 기록은 조회 가능하다.

## 6. 박스스코어가 확보된 경우에만 추가 적재

kbodata 수집은 배인표 전처리 작업이다. 패치 안내는 [인수인계](../docs/handoff/preprocessing_baeinpyo.md)를 본다.
실제 JSON 경로를 지정한다.

```bash
python etl/kbodata_to_tables.py /path/to/raw.json --players data/player_season_team.csv --check-only
python etl/kbodata_to_tables.py /path/to/raw.json --players data/player_season_team.csv
psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/07_load_data.sql
```

동명이인은 playerId 자체와 별개로 이름→ID 매핑을 검증한다. 모호한 행을 임의로 연결하지 않는다.
필요하면 `crawl/kbo_gamelogs.py --from-unmatched data/load/_unmatched_players.csv`로 출전일을 확인한다.
스코어보드에 홈·원정 두 행이 없으면 적재 전체를 취소한다. 경기 집계 MV는 적재 후 갱신한다.
박스스코어를 완전히 적재한 뒤 공식 시즌 기록과 비교한다.

## 수집 범위와 요청 방식

- 수집 대상: 선수 상세, Basic1/2 시즌 타자·투수 기록, 기준일 팀 순위.
- 제외: 네이버 문자중계 및 투구별 구종·구속·좌표·볼카운트.
- 미구현: 수비·주루 전용 시즌 기록, 엔트리 등록·말소 이력.
- 요청 간격 1~2초, 순차 수집. 오류는 재시도하며 원본 HTML은 `data/raw/`에 저장한다.
- 지원 도구: `common.py`, `aspnet.py`, `kbo_parsers.py`, `probe_kbo.py`, `kbo_records.py`,
  `kbo_profiles.py`, `kbo_team_rank.py`, `kbo_gamelogs.py`, `kbodata_patch.py`.
