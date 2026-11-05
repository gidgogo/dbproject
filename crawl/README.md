# 크롤링 실행 가이드 (성수 맥에서)

클라우드 환경에서는 koreabaseball.com·네이버 접속이 막혀 있어서 **모든 수집은 맥에서** 실행한다.
모든 명령은 **레포 최상위 폴더**(이 README의 상위 폴더)에서 실행한다.

## 0. 준비 (처음 한 번)

```bash
source ~/Desktop/kbo-env/bin/activate
```

```bash
pip install -r crawl/requirements.txt
```

## 1. 페이지 구조 확인 (요청 약 12회, 1분) — 꼭 먼저

```bash
python crawl/probe_kbo.py --season 2025
```

```bash
python crawl/naver_probe.py --years 2018,2020,2022,2023,2025
```

결과: `docs/probe/kbo_probe_YYYYMMDD.md`, `docs/probe/naver_probe_YYYYMMDD.md`.
❌ 항목이 있으면 그 파일과 `data/raw/probe/*.html`을 Claude에게 넘겨서 크롤러를 고친 뒤 진행한다.

## 2. 선수 목록·playerId 매핑표 + 기록실 시즌 기록 (2-2 ①, 2-3)

프로토타입(2025 두산, 이번 주 목표):

```bash
python crawl/kbo_records.py --seasons 2025 --teams OB
```

2025 전체 팀 (약 90요청, 3분):

```bash
python crawl/kbo_records.py --seasons 2025
```

결과: `data/player_season_team.csv`(매핑표 → 배인표), `data/season_batting.csv`, `data/season_pitching.csv`.
중간에 끊기면 **같은 명령을 다시** 실행하면 끝난 (시즌, 팀) 단위는 건너뛴다(`data/raw/kbo/records/_done.json`).

## 3. 선수 상세 (2-2 ②)

샘플 20명:

```bash
python crawl/kbo_profiles.py --seasons 2025 --limit 20
```

2025 선수 전원 (약 600~700명 × 1~2초 ≈ 15~25분):

```bash
python crawl/kbo_profiles.py --seasons 2025
```

결과: `data/players.csv` (이미 받은 선수는 건너뜀, 20명마다 저장)

## 4. 팀 순위 (2-3)

```bash
python crawl/kbo_team_rank.py --seasons 2025
```

## 5. kbodata 박스스코어와 매핑 검증 (2-2 검증)

kbo_fetch.py 에 `crawl/kbodata_patch.py` 적용 방법: `docs/handoff/preprocessing_baeinpyo.md` 1번.

```bash
python etl/kbodata_to_tables.py ~/Desktop/data/test/raw.json --players data/player_season_team.csv --check-only
```

같은 팀·같은 이름이 있어 'ambiguous'가 나오면 출전 일자를 받아 다시 매핑:

```bash
python etl/kbodata_to_tables.py ~/Desktop/data/test/raw.json --players data/player_season_team.csv
```

```bash
python crawl/kbo_gamelogs.py --from-unmatched data/load/_unmatched_players.csv
```

## 6. 네이버 투구 (2-4, 11/20까지)

시험 3경기:

```bash
python crawl/naver_relay.py --season 2025 --team OB --max-games 3
```

한 팀 시즌 전체 (약 1,400요청, 35~45분):

```bash
python crawl/naver_relay.py --season 2025 --team OB
```

결과: `data/pitches_2025_OB.csv`, 리포트 `data/raw/naver/2025/_report_OB.md`

## 7. DB에 적재

```bash
python etl/crawl_to_tables.py
```

kbo_fetch.py 가 raw JSON 을 저장한 위치로 경로를 바꿔서 실행 (여러 파일 가능):

```bash
python etl/kbodata_to_tables.py ~/Desktop/data/2025/*.json
```

```bash
python etl/pitches_to_tables.py
```

```bash
psql -d kbo -f erd/ddl/07_load_data.sql
```

```bash
psql -d kbo -f erd/ddl/08_load_pitch.sql
```

## 크롤링 예의 (모든 스크립트 공통, crawl/common.py)

- 요청 사이 1~2초 무작위 간격, 순차 요청(동시 요청 없음)
- 네트워크 오류·5xx는 2·4·8·16초 기다렸다 최대 4번 재시도
- 시즌·팀·경기 단위 이어받기, 원본(HTML/JSON)은 `data/raw/`에 저장해서 다시 받지 않고 재파싱
- User-Agent는 일반 브라우저 문자열 (개인정보 없음). 바꾸려면 `export KBO_CRAWL_UA="..."`

## 파일 구성

| 파일 | 역할 |
|---|---|
| common.py | HTTP 세션(간격·재시도), 체크포인트, CSV 저장 |
| aspnet.py | KBO ASP.NET 포스트백 (폼 전체 재전송) |
| kbo_parsers.py | KBO HTML 파서 (순수 함수, 테스트 있음) |
| probe_kbo.py | KBO 구조 확인 |
| kbo_records.py | 기록실 → 매핑표 + 시즌 기록 |
| kbo_profiles.py | 선수 상세 |
| kbo_team_rank.py | 팀 순위 |
| kbo_gamelogs.py | 동명이인 구분용 출전 일자 |
| kbodata_patch.py | kbodata 버그 보정 |
| naver_parsers.py | 네이버 중계 → 투구 행 (순수 함수, 테스트 있음) |
| naver_probe.py | 네이버 구조·제공 연도 확인 |
| naver_relay.py | 네이버 투구 수집 |
