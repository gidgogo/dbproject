# 데이터 검증 방법 (2-2 매핑 검증, 2-3 기록실 비교)

## 1. playerId 매핑 검증 (2-2 ④)

목표: 2025-06-01 테스트 데이터(타자 124명, 투수 53명)의 이름+팀이 **전부 하나의 playerId**로 매칭되는지.

```bash
python etl/kbodata_to_tables.py ~/Desktop/data/test/raw.json --players data/player_season_team.csv --check-only
```

리포트에서 볼 것: `선수ID 매칭: 177/177 (100.0%)`, 방법별 건수(exact / exact_kind / prefix …), 실패 목록.
같은 시즌·같은 팀 동명이인은 `reason=ambiguous` 로 나오고 `candidates`에 후보 playerId가 있다 → 별도 기록해 보고서에 사례로 쓴다.

## 2. 기록실 공식 값 vs 경기 기록 집계 (2-3 검증)

적재 후 DB에서 (예: 2025 시즌):

```sql
-- 타자: 기록실 선수 중 주요 항목(AB·H·HR·RBI·BB·SO)이 모두 일치하는 비율
SELECT season,
       count(*)                                   AS players,
       count(*) FILTER (WHERE is_match)           AS exact_match,
       round(100.0 * count(*) FILTER (WHERE is_match) / count(*), 1) AS match_pct
FROM v_compare_batting_official
WHERE season = 2025
GROUP BY season;

-- 항목별 차이 합계 (어느 항목이 틀리는지)
SELECT sum(abs(ab_off - ab_calc)) AS ab_diff, sum(abs(h_off - h_calc)) AS h_diff,
       sum(abs(hr_off - hr_calc)) AS hr_diff, sum(abs(bb_off - bb_calc)) AS bb_diff,
       count(*) FILTER (WHERE ab_calc IS NULL) AS missing_in_games
FROM v_compare_batting_official WHERE season = 2025;

-- 타율 비교 예시 (보고서 표용): 타석 많은 10명
SELECT p.player_name, c.avg_off, c.avg_calc, c.ab_off, c.ab_calc, c.h_off, c.h_calc
FROM v_compare_batting_official c JOIN player p USING (player_id)
WHERE c.season = 2025 ORDER BY c.pa_off DESC NULLS LAST LIMIT 10;

-- 투수, 팀 순위
SELECT round(100.0 * count(*) FILTER (WHERE is_match) / count(*), 1) FROM v_compare_pitching_official WHERE season = 2025;
SELECT * FROM v_compare_team_rank WHERE season = 2025 ORDER BY rank_off;
```

차이가 생길 수 있는 이유 (보고서에 함께 적기)
- kbodata가 받지 못한 경기 (kbodata README의 미제공 경기 목록, 우천 서스펜디드 등)
- 이름 매핑 실패로 빠진 행 (`data/load/_unmatched_players.csv`)
- 투수 결정(W/L) — kbodata 버그 (`crawl/kbodata_patch.py` 적용 전 데이터)
- WHIP — kbodata는 볼넷·사구를 합쳐 줘서 사구 포함 근사값
- 타석(PA) — kbodata 이닝 칸에 없는 타석(예: 3아웃 주루사 직전 타석)은 셀 수 없음

## 3. 내부 일관성 (행이 없어야 정상)

```sql
SELECT 'team_runs' AS chk, count(*) FROM v_check_team_runs
UNION ALL SELECT 'team_hits', count(*) FROM v_check_team_hits
UNION ALL SELECT 'batter_pa', count(*) FROM v_check_batter_pa
UNION ALL SELECT 'game_result', count(*) FROM v_check_game_result
UNION ALL SELECT 'pitcher_decision', count(*) FROM v_check_pitcher_decision;
```
