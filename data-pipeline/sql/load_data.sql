-- =====================================================================
-- 수집 데이터 적재 (data-pipeline/data/load/*.csv → DB)
--   스키마는 Flyway(backend/src/main/resources/db/migration)가 만든다. 이 파일은 데이터만 넣는다.
--   Flyway 파일이 아니라 psql 스크립트다(\copy 사용). 마이그레이션 폴더에 넣지 말 것.
--
--   먼저 CSV를 만든다 (data-pipeline 폴더에서):
--     python etl/crawl_to_tables.py                    # 선수·기록실 → data/load
--     python etl/kbodata_to_tables.py <raw.json ...>   # 경기 → data/load
--   그다음 같은 data-pipeline 폴더에서 (팀 docker DB: localhost:5434, kbo/kbo/kbo):
--     PGPASSWORD=kbo psql -h localhost -p 5434 -U kbo -d kbo -f sql/load_data.sql
--   같은 파일을 다시 적재해도 된다(경기는 갱신, 박스스코어만 교체).
--   마지막에 fn_refresh_stats()로 시즌 성적·순위 MV를 갱신한다(MV 갱신은 적재 담당 몫).
--   복합키 테이블의 id(대리키)는 DB가 자동으로 매기므로 CSV에 없다.
-- =====================================================================
\set ON_ERROR_STOP on
BEGIN;

\ir includes/load_kbo.sql

-- 3. 경기 (경기 자체는 보존하고 이 수집기가 소유한 박스스코어만 교체) -----------
CREATE TEMP TABLE stg_match (
    match_id text, match_date date, away_team_id text, home_team_id text, doubleheader_no integer,
    series_id integer, stadium_id integer, attendance integer, start_time time, end_time time,
    duration_min integer) ON COMMIT DROP;
\copy stg_match FROM 'data/load/match.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO match (match_id, match_date, away_team_id, home_team_id, doubleheader_no, series_id,
                  stadium_id, attendance, start_time, end_time, duration_min)
SELECT * FROM stg_match
ON CONFLICT (match_id) DO UPDATE SET
    match_date = EXCLUDED.match_date,
    away_team_id = EXCLUDED.away_team_id,
    home_team_id = EXCLUDED.home_team_id,
    doubleheader_no = EXCLUDED.doubleheader_no,
    series_id = EXCLUDED.series_id,
    stadium_id = EXCLUDED.stadium_id,
    attendance = EXCLUDED.attendance,
    start_time = EXCLUDED.start_time,
    end_time = EXCLUDED.end_time,
    duration_min = EXCLUDED.duration_min;

DELETE FROM match_event WHERE match_id IN (SELECT match_id FROM stg_match);
DELETE FROM match_umpire WHERE match_id IN (SELECT match_id FROM stg_match);
-- 이닝·타자·투수·타석은 match_team에서 CASCADE. 경기 자체는 삭제하지 않는다.
DELETE FROM match_team WHERE match_id IN (SELECT match_id FROM stg_match);

\copy match_team (match_id, team_id, home_away, result, runs, hits, errors, walks_hbp) FROM 'data/load/match_team.csv' WITH (FORMAT csv, HEADER true)
\copy inning_score (match_id, team_id, inning, runs) FROM 'data/load/inning_score.csv' WITH (FORMAT csv, HEADER true)
\copy batter_match (match_id, player_id, team_id, lineup_seq, batting_order, positions, at_bats, hits, rbi, runs) FROM 'data/load/batter_match.csv' WITH (FORMAT csv, HEADER true)
\copy plate_appearance (match_id, player_id, inning, seq_in_inning, result_code) FROM 'data/load/plate_appearance.csv' WITH (FORMAT csv, HEADER true)
\copy pitcher_match (match_id, player_id, team_id, appearance_seq, decision, outs_recorded, batters_faced, at_bats, pitches, hits_allowed, home_runs_allowed, walks_hbp, strikeouts, runs_allowed, earned_runs) FROM 'data/load/pitcher_match.csv' WITH (FORMAT csv, HEADER true)
\copy match_event (match_id, event_type, seq, player_id, team_id, player_name_raw, inning, detail, raw_text) FROM 'data/load/match_event.csv' WITH (FORMAT csv, HEADER true)

CREATE TEMP TABLE stg_match_umpire (match_id text, umpire_name text, listed_order integer) ON COMMIT DROP;
\copy stg_match_umpire FROM 'data/load/match_umpire_stage.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO umpire (umpire_name)
SELECT DISTINCT umpire_name FROM stg_match_umpire
ON CONFLICT (umpire_name) DO NOTHING;
INSERT INTO match_umpire (match_id, umpire_id, listed_order)
SELECT s.match_id, u.umpire_id, s.listed_order
FROM stg_match_umpire s JOIN umpire u ON u.umpire_name = s.umpire_name;

-- FK·홈원정 트리거만으로는 누락된 팀을 찾을 수 없으므로 커밋 직전에 검사한다.
DO $$ BEGIN
    IF EXISTS (
        SELECT s.match_id FROM stg_match s LEFT JOIN match_team t USING (match_id)
        GROUP BY s.match_id HAVING count(t.team_id) <> 2
    ) THEN
        RAISE EXCEPTION '경기마다 홈·원정 팀경기기록이 각각 하나씩 필요합니다';
    END IF;
END $$;

COMMIT;

-- 4. 시즌 성적·순위 MV 다시 계산 -----------------------------------------
SELECT fn_refresh_stats();
