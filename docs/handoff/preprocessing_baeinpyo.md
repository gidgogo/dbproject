# 배인표(전처리)에게 — kbodata 결과 정리 인터페이스

> 경로는 `data-pipeline/` 폴더 기준이다 (`cd data-pipeline` 후 실행). DB는 팀 docker `localhost:5434`, DB·계정·비번 `kbo`.

## 1. 먼저: kbodata 버그 2개 (시즌 수집 전에 꼭)

kbodata 0.2.2/0.2.3 소스를 읽다가 찾았다. (`data-pipeline/crawl/kbodata_patch.py`, 테스트 `data-pipeline/tests/test_kbodata_patch.py`)

1. **투수 결과**: `kbodata/parser/pitcher.py`의 `change_result`가 '세이브'·'홀드'·'승'이 아니면 전부 `"L"`을 돌려준다.
   결정이 없는 투수(빈 칸)도 패전 투수가 된다 → 시즌 패 수가 부풀려짐. (KBO 표기가 '세'라면 세이브도 L이 됨)
2. **타순**: `kbodata/parser/html.py`의 `away_batter/home_batter`가 박스스코어 첫 열(타순)을 지운다.

kbo_fetch.py 맨 위에 두 줄을 넣으면 고쳐진다 (kbodata 파일은 안 바뀜).

```python
import sys; sys.path.insert(0, "/Users/<맥 사용자명>/Desktop/프로젝트/data-pipeline/crawl")
import kbodata_patch; kbodata_patch.apply()
```

패치 후 투수 `result`는 W/L/S/H 또는 빈 문자열, 타자에는 `bat_order`(1~9)가 추가된다.
이미 받은 2025-06-01 테스트 데이터로 확인할 것: 경기마다 'L'이 진 팀에 1명뿐인지(패치 전엔 여러 명일 것),
`bat_order`가 1~9이고 선발 순서대로인지.

## 2. kbodata 값 처리 규칙 (변환기에 구현됨: `etl/kbodata_parse.py`)

| kbodata | DB | 규칙 |
|---|---|---|
| 경기 `id` `20250601_OBWO0` | match.match_id | 그대로. CSV의 `idx`는 팀마다 달라서 쓰지 않음 |
| 타자 `i_1`~`i_18` | plate_appearance | 칸 하나 = 타석 여러 개 가능: `10137000` → [1013, 7000] (4자리씩, '0'은 타석 아님, '-'는 빈 칸) |
| 타자 `position` `H8` | batter_match.positions | 그대로 (타→H, 주→R, 지→D, 一→3 …) |
| 투수 `inning` `61` | pitcher_match.outs_recorded = 19 | 마지막 자리 = 나머지 아웃, 앞자리 = 이닝 |
| 투수 `mound` | (저장 안 함) | 선발 = 등판순서 1. 다르면 경고 |
| 투수 `pitchnum` 0 | NULL | 과거 경기 투구수 누락 |
| 스코어보드 `result` 1/0/-1 | match_team.result W/D/L | |
| 스코어보드 `i_n` '-' | (행 없음) | 공격 안 한 이닝 |
| ETC_info `구장` | match.stadium_id | `data/reference/stadium_place_map.csv` (시즌별: 대구 ~2015 시민구장, 2016~ 라이온즈파크 …) |
| ETC_info `관중` "12,345" / `경기시간` "3:05" | attendance 12345 / duration_min 185 | |
| ETC_info `심판` 리스트 | umpire, match_umpire | 나열 순서 저장 |
| ETC_info 나머지 (결승타·홈런·2루타·도루·실책…) | match_event | 아래 3번 |
| 팀명 '두산', 'SSG', '키움' | team_id OB, SK, WO | `data/reference/team_season.csv` (시즌별 약칭) |
| 선수 이름 | player_id | 매핑표(4번) |

## 3. 기타 기록 파싱

kbodata는 `") "` 기준으로 잘라서 `"김준상(1회"`처럼 닫는 괄호가 빠진다. 변환기는 괄호를 복원한 뒤
- `이름` + (숫자 = 개수 또는 `숫자호` = 시즌 홈런 번호) + `(상세)`로 나누고
- 상세에서 이닝을 모두 찾는다: `"임종성2(4 6회)"` → 이닝 4, 6 (행 2개), `"최정2(3회1점 5회2점)"` → 3, 5
- 선수는 **그 경기 출전 선수 중 같은 이름**으로 playerId를 찾는다(팀 정보가 없어서). 못 찾으면 NULL + 원문 보존.
모르는 항목 이름이 나오면 리포트에 나오니 `data/reference/match_event_type.csv`에 추가.

## 4. 이름 → playerId 매핑 순서 (`etl/player_mapper.py`)

입력 매핑표 `data/player_season_team.csv` (성수 크롤링: `crawl/kbo_records.py`)

1. 사람이 확인한 예외표 `data/reference/player_name_overrides.csv` (season, team_id, name, player_id, note)
2. 같은 시즌·팀·이름 1명 → 확정
3. 여러 명이면 타자/투수 구분
4. 그래도 여러 명이면 선수별 출전 일자 (`crawl/kbo_gamelogs.py --from-unmatched data/load/_unmatched_players.csv`)
5. 이름이 잘린 경우 앞부분 일치 (외국인 '페르난데' → '페르난데스')
6. 공백·가운뎃점 차이 무시
7. 같은 시즌 다른 팀에 1명 (이적 시점 차이)

## 5. 변환·검증 명령

```bash
python etl/kbodata_to_tables.py ~/Desktop/data/test/raw.json --players data/player_season_team.csv --check-only
```

→ 타자 124명·투수 53명이 모두 매칭되는지(2-2 검증), 매칭 방법별 건수, 실패 목록, 투수 결정 이상 경기 수를 출력한다.
`--check-only`를 빼면 `data/load/*.csv`(DB 테이블 컬럼 순서 그대로)와 `_kbodata_report.md`를 만든다.

이 변환기는 ERD 검증용 **참고 구현**이다. 인표가 전처리를 따로 만들면 출력 CSV 컬럼만 `data/load/*.csv`와 맞춰 주면
`data-pipeline/sql/load_data.sql`로 바로 적재된다 (data-pipeline 폴더에서 실행, 팀 docker DB localhost:5434 kbo/kbo/kbo).
