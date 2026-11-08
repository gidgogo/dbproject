-- =====================================================================
-- 성능 확인용: 한 시즌 규모 **가상 데이터** 생성 + 주요 조회 EXPLAIN ANALYZE
--   별도 DB에서 실행한다 (실제 데이터 DB에 넣지 말 것!)
--     createdb kbo_perf  → Flyway 마이그레이션(V1, V2)을 kbo_perf 에 적용한 뒤
--     psql -X -q -d kbo_perf -f tools/perf_check.sql > docs/report/07_perf_result.txt
--   가상 선수 ID는 800001번부터, 경기는 2099 시즌(실제 시즌과 겹치지 않게)
-- =====================================================================
\set ON_ERROR_STOP on
\timing off
SELECT setseed(0.42);

INSERT INTO team_season (team_id, season, team_name, short_name, home_stadium_id)
SELECT team_id, 2099, team_name, team_id, NULL FROM team ON CONFLICT DO NOTHING;

-- 선수 300명 (팀당 타자 20 + 투수 10)
INSERT INTO player (player_id, player_name)
SELECT 800000 + g, '가상선수' || g FROM generate_series(1, 300) g;
WITH t AS (SELECT team_id, row_number() OVER (ORDER BY team_id) - 1 AS k FROM team)
INSERT INTO player_season (player_id, season, team_id, name_in_season, is_batter, is_pitcher)
SELECT 800000 + t.k * 30 + j, 2099, t.team_id, '가상선수' || (t.k * 30 + j), j <= 20, j > 20
FROM t, generate_series(1, 30) j;

-- 720경기: 하루 5경기 × 144일, 팀 순서를 날마다 돌려서 짝을 만든다
CREATE TEMP TABLE tk AS SELECT team_id, row_number() OVER (ORDER BY team_id) - 1 AS k FROM team;
CREATE TEMP TABLE g AS
SELECT d, m,
       (SELECT team_id FROM tk WHERE k = (d + 2 * m) % 10)     AS away,
       (SELECT team_id FROM tk WHERE k = (d + 2 * m + 1) % 10) AS home
FROM generate_series(0, 143) d, generate_series(0, 4) m;
INSERT INTO match (match_id, match_date, away_team_id, home_team_id, doubleheader_no, stadium_id, attendance)
SELECT to_char(date '2099-03-28' + d, 'YYYYMMDD') || '_' || away || home || '0', date '2099-03-28' + d,
       away, home, 0, 1 + (d % 14), 8000 + (random() * 15000)::int
FROM g;

-- 팀경기기록: 점수 무작위, 같으면 무승부
CREATE TEMP TABLE sc AS SELECT match_id, (random() * 10)::int AS ar, (random() * 10)::int AS hr FROM match WHERE season = 2099;
INSERT INTO match_team (match_id, team_id, home_away, result, runs, hits, errors, walks_hbp)
SELECT s.match_id, g.away_team_id, 'A', CASE WHEN ar > hr THEN 'W' WHEN ar < hr THEN 'L' ELSE 'D' END, ar, ar + 4, 0, 3
FROM sc s JOIN match g USING (match_id)
UNION ALL
SELECT s.match_id, g.home_team_id, 'H', CASE WHEN hr > ar THEN 'W' WHEN hr < ar THEN 'L' ELSE 'D' END, hr, hr + 4, 1, 2
FROM sc s JOIN match g USING (match_id);

-- 타자: 팀마다 9명, 4타수 / 타석: 이닝 1~9 중 4개, 결과코드 무작위
INSERT INTO batter_match (match_id, player_id, team_id, lineup_seq, batting_order, positions, at_bats, hits, rbi, runs)
SELECT tg.match_id, 800000 + tk.k * 30 + j, tg.team_id, j, j, '8', 4, (random() * 2)::int, 0, 0
FROM match_team tg JOIN tk ON tk.team_id = tg.team_id JOIN match g ON g.match_id = tg.match_id
CROSS JOIN generate_series(1, 9) j WHERE g.season = 2099;
CREATE TEMP TABLE codes AS SELECT result_code, row_number() OVER () AS n FROM pa_result_code;
INSERT INTO plate_appearance (match_id, player_id, inning, seq_in_inning, result_code)
SELECT b.match_id, b.player_id, (b.lineup_seq + 2 * i) % 9 + 1, 1,
       (SELECT result_code FROM codes WHERE n = 1 + ((hashtext(b.match_id || b.player_id || i) & 2147483647) % 179))
FROM batter_match b CROSS JOIN generate_series(0, 3) i
JOIN match g ON g.match_id = b.match_id WHERE g.season = 2099;

-- 투수: 팀마다 3명
INSERT INTO pitcher_match (match_id, player_id, team_id, appearance_seq, decision, outs_recorded, batters_faced,
                          at_bats, pitches, hits_allowed, home_runs_allowed, walks_hbp, strikeouts, runs_allowed, earned_runs)
SELECT tg.match_id, 800000 + tk.k * 30 + 20 + j, tg.team_id, j, NULL, 9, 12, 10, 45, 2, 0, 1, 3, 1, 1
FROM match_team tg JOIN tk ON tk.team_id = tg.team_id JOIN match g ON g.match_id = tg.match_id
CROSS JOIN generate_series(1, 3) j WHERE g.season = 2099;

SELECT fn_refresh_stats();
ANALYZE;

\echo '=== 데이터 규모 ==='
SELECT (SELECT count(*) FROM match) AS games, (SELECT count(*) FROM batter_match) AS batter_rows,
       (SELECT count(*) FROM plate_appearance) AS pa_rows, (SELECT count(*) FROM pitcher_match) AS pitcher_rows;

\echo ''
\echo '=== Q1. 선수 프로필: 한 선수의 경기별 타격 기록 (인덱스 있음) ==='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT * FROM batter_match WHERE player_id = 800005;

\echo ''
\echo '=== Q1-비교. 같은 조회, ix_batter_match_player 인덱스를 지운 경우 ==='
BEGIN;
DROP INDEX ix_batter_match_player;
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT * FROM batter_match WHERE player_id = 800005;
ROLLBACK;

\echo ''
\echo '=== Q2. 경기 결과 화면: 하루 경기 목록 ==='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT * FROM v_match_summary WHERE match_date = date '2099-06-01';

\echo ''
\echo '=== Q3. 선수 시즌 성적: MV에서 읽기 ==='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT * FROM mv_season_batting WHERE player_id = 800005 AND season = 2099;

\echo ''
\echo '=== Q3-비교. 같은 값을 MV 없이 경기 기록에서 바로 계산 ==='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT player_id, season, sum(at_bats), sum(hits), sum(home_runs)
FROM v_batter_match_line WHERE player_id = 800005 AND season = 2099 GROUP BY player_id, season;

\echo ''
\echo '=== Q4. 순위 화면 ==='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT * FROM mv_team_standings WHERE season = 2099 ORDER BY rank;

\echo ''
\echo '=== Q5. MV 갱신 시간 (데이터 적재 후 1회) ==='
\timing on
SELECT fn_refresh_stats();
\timing off
