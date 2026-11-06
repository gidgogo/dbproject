-- =====================================================================
-- KBO 야구 기록 DB · 07. 수집 데이터 적재 (data/load/*.csv)
--   먼저 CSV를 만든다:
--     python etl/crawl_to_tables.py          # 선수·기록실 → data/load
--     python etl/kbodata_to_tables.py <raw.json ...>   # 경기 → data/load
--   그다음 레포 최상위 폴더에서:
--     psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/07_load_data.sql
--   같은 파일을 다시 적재해도 된다(경기는 갱신, 박스스코어만 교체).
-- =====================================================================
\set ON_ERROR_STOP on
BEGIN;

\ir includes/load_kbo.sql

-- 3. 경기 (경기 자체는 보존하고 이 수집기가 소유한 박스스코어만 교체) -----------
CREATE TEMP TABLE stg_game (
    game_id text, game_date date, away_team_id text, home_team_id text, doubleheader_no smallint,
    series_id smallint, stadium_id smallint, attendance integer, start_time time, end_time time,
    duration_min smallint) ON COMMIT DROP;
\copy stg_game FROM 'data/load/game.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO game (game_id, game_date, away_team_id, home_team_id, doubleheader_no, series_id,
                  stadium_id, attendance, start_time, end_time, duration_min)
SELECT * FROM stg_game
ON CONFLICT (game_id) DO UPDATE SET
    game_date = EXCLUDED.game_date,
    away_team_id = EXCLUDED.away_team_id,
    home_team_id = EXCLUDED.home_team_id,
    doubleheader_no = EXCLUDED.doubleheader_no,
    series_id = EXCLUDED.series_id,
    stadium_id = EXCLUDED.stadium_id,
    attendance = EXCLUDED.attendance,
    start_time = EXCLUDED.start_time,
    end_time = EXCLUDED.end_time,
    duration_min = EXCLUDED.duration_min;

DELETE FROM game_event WHERE game_id IN (SELECT game_id FROM stg_game);
DELETE FROM game_umpire WHERE game_id IN (SELECT game_id FROM stg_game);
-- 이닝·타자·투수·타석은 team_game에서 CASCADE. 경기 자체는 삭제하지 않는다.
DELETE FROM team_game WHERE game_id IN (SELECT game_id FROM stg_game);

\copy team_game FROM 'data/load/team_game.csv' WITH (FORMAT csv, HEADER true)
\copy inning_score FROM 'data/load/inning_score.csv' WITH (FORMAT csv, HEADER true)
\copy batter_game FROM 'data/load/batter_game.csv' WITH (FORMAT csv, HEADER true)
\copy plate_appearance FROM 'data/load/plate_appearance.csv' WITH (FORMAT csv, HEADER true)
\copy pitcher_game FROM 'data/load/pitcher_game.csv' WITH (FORMAT csv, HEADER true)
\copy game_event (game_id, event_type, seq, player_id, team_id, player_name_raw, inning, detail, raw_text) FROM 'data/load/game_event.csv' WITH (FORMAT csv, HEADER true)

CREATE TEMP TABLE stg_game_umpire (game_id text, umpire_name text, listed_order smallint) ON COMMIT DROP;
\copy stg_game_umpire FROM 'data/load/game_umpire_stage.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO umpire (umpire_name)
SELECT DISTINCT umpire_name FROM stg_game_umpire
ON CONFLICT (umpire_name) DO NOTHING;
INSERT INTO game_umpire (game_id, umpire_id, listed_order)
SELECT s.game_id, u.umpire_id, s.listed_order
FROM stg_game_umpire s JOIN umpire u ON u.umpire_name = s.umpire_name;

-- FK·홈원정 트리거만으로는 누락된 팀을 찾을 수 없으므로 커밋 직전에 검사한다.
DO $$ BEGIN
    IF EXISTS (
        SELECT s.game_id FROM stg_game s LEFT JOIN team_game t USING (game_id)
        GROUP BY s.game_id HAVING count(t.team_id) <> 2
    ) THEN
        RAISE EXCEPTION '경기마다 홈·원정 팀경기기록이 각각 하나씩 필요합니다';
    END IF;
END $$;

COMMIT;

-- 4. 시즌 성적·순위 MV 다시 계산 -----------------------------------------
SELECT fn_refresh_stats();
