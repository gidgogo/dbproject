# data/ — 데이터 파일 설명

## reference/ (직접 입력·생성, git에 포함)

팀·구장·팀시즌·코드표 CSV는 `tools/gen_reference_migration.py`가 Flyway `V2__reference_data.sql`로 바꾼다.
CSV를 고치면 V2는 그대로 두고 새 버전(V3…)을 만든다.

| 파일 | 내용 | 비고 |
|---|---|---|
| team.csv | 10개 구단, KBO 팀코드 | |
| team_season.csv | 2008~2026 시즌별 팀명·약칭(kbodata 표기)·홈구장 | `needs_check=Y` 행은 ❓ 확인 필요 |
| stadium.csv | 구장 18곳 | 수용 인원은 공식 자료로 채울 것(현재 비움) |
| stadium_place_map.csv | 박스스코어 구장 표기 + 시즌 → 구장ID | 변환기가 사용 (DB에는 없음) |
| pa_result_type.csv / pa_result_code.csv | 타석 결과 유형·코드 179개 | `tools/gen_pa_result_code.py` 가 kbodata 코드표에서 생성 |
| kbodata_batter_codes.ini, LICENSE.kbodata | kbodata 결과 코드표 발췌와 MIT 라이선스 | |
| match_event_type.csv | 박스스코어 기타 기록 항목 | 모르는 항목이 나오면 변환 리포트에 표시 |
| position.csv | kbodata 포지션 코드 | 참고용 |
| player_name_overrides.csv | 동명이인 수동 매핑 (season, team_id, name, player_id, match_id, note). match_id를 적으면 그 경기만, 비우면 시즌·팀 전체 | 변환기가 선수ID 실패로 멈추면 추가 |

## 크롤링 결과 (맥에서 생성, 팀 공유용)

| 파일 | 만드는 스크립트 | 컬럼 |
|---|---|---|
| player_season_team.csv | crawl/kbo_records.py | season, team_id, player_id, name, is_batter, is_pitcher |
| season_batting.csv | crawl/kbo_records.py | season, team_id, player_id, name, games … ops (DB 컬럼명과 같음) |
| season_pitching.csv | crawl/kbo_records.py | season, team_id, player_id, name, games … whip, ip_text, outs_recorded |
| players.csv | crawl/kbo_profiles.py | player_id, player_name, birth_date, throws, bats, height_cm, … salary_season, team_id |
| team_rank.csv | crawl/kbo_team_rank.py | season, as_of_date, rank, team_id, games, wins, losses, draws, win_pct, games_behind, last10, streak |
| player_game_dates.csv | crawl/kbo_gamelogs.py | player_id, game_date |

## 프로필과 시즌 구분

`players.csv`는 조회 시점의 프로필이다. 현재 소속명·등번호·출처는 `player`에 저장한다.
상무는 KBO 10개 구단에 억지로 연결하지 않고 현재 소속 원문으로 보존한다.
시즌별 소속은 `player_season_team.csv`, 연봉 기준 연도는 `salary_season`으로 구분한다.
KBO 자료만 적재할 때는 ETL 실행 후 `sql/load_kbo.sql`을 사용한다 (data-pipeline 폴더에서).

## git에 올리지 않는 폴더

- `raw/` — 받은 원본 HTML·JSON (재파싱용, 용량 큼)
- `load/` — DB 적재용 CSV (etl/ 스크립트로 언제든 다시 만듦)
