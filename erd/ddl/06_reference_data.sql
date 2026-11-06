-- =====================================================================
-- KBO 야구 기록 DB · 06. 기준 데이터 적재 (data/reference/*.csv)
--   레포 최상위 폴더에서 실행해야 상대 경로가 맞는다.
--     psql -d kbo -f erd/ddl/06_reference_data.sql
--   CSV에는 DB에 넣지 않는 메모 컬럼(needs_check, note 등)이 있어서
--   임시 테이블에 먼저 받은 뒤 필요한 컬럼만 옮긴다.
-- =====================================================================
BEGIN;

CREATE TEMP TABLE stg_team (team_id text, team_name text, city text, first_season int, note text) ON COMMIT DROP;
\copy stg_team FROM 'data/reference/team.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO team (team_id, team_name, city, first_season)
SELECT team_id, team_name, city, first_season FROM stg_team
ON CONFLICT (team_id) DO UPDATE
   SET team_name = EXCLUDED.team_name, city = EXCLUDED.city, first_season = EXCLUDED.first_season;

CREATE TEMP TABLE stg_stadium (stadium_id int, stadium_name text, city text, is_dome boolean, capacity int, note text) ON COMMIT DROP;
\copy stg_stadium FROM 'data/reference/stadium.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO stadium (stadium_id, stadium_name, city, is_dome, capacity)
SELECT stadium_id, stadium_name, city, is_dome, capacity FROM stg_stadium
ON CONFLICT (stadium_id) DO UPDATE
   SET stadium_name = EXCLUDED.stadium_name, city = EXCLUDED.city,
       is_dome = EXCLUDED.is_dome, capacity = EXCLUDED.capacity;
-- 직접 넣은 ID 다음부터 자동 증가하도록 시퀀스를 맞춘다
DO $$ BEGIN PERFORM setval(pg_get_serial_sequence('stadium', 'stadium_id'), (SELECT max(stadium_id) FROM stadium)); END $$;

CREATE TEMP TABLE stg_team_season (team_id text, season int, team_name text, short_name text,
                                   home_stadium_id int, needs_check text, note text) ON COMMIT DROP;
\copy stg_team_season FROM 'data/reference/team_season.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO team_season (team_id, season, team_name, short_name, home_stadium_id)
SELECT team_id, season, team_name, short_name, home_stadium_id FROM stg_team_season
ON CONFLICT (team_id, season) DO UPDATE
   SET team_name = EXCLUDED.team_name, short_name = EXCLUDED.short_name,
       home_stadium_id = EXCLUDED.home_stadium_id;

CREATE TEMP TABLE stg_pa_type (result_type text, result_type_name text, batted_ball text,
    is_at_bat int, is_hit int, total_bases int, is_walk int, is_hbp int, is_sac_fly int,
    is_sac_bunt int, is_strikeout int, is_double_play int) ON COMMIT DROP;
\copy stg_pa_type FROM 'data/reference/pa_result_type.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO pa_result_type
SELECT result_type, result_type_name, nullif(batted_ball, ''),
       is_at_bat = 1, is_hit = 1, total_bases, is_walk = 1, is_hbp = 1, is_sac_fly = 1,
       is_sac_bunt = 1, is_strikeout = 1, is_double_play = 1
FROM stg_pa_type
ON CONFLICT (result_type) DO NOTHING;

CREATE TEMP TABLE stg_pa_code (result_code int, result_name text, result_type text,
    fielder_pos text, spray_dir text, aliases text) ON COMMIT DROP;
\copy stg_pa_code FROM 'data/reference/pa_result_code.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO pa_result_code (result_code, result_name, result_type, fielder_pos, spray_dir)
SELECT result_code, result_name, result_type, nullif(fielder_pos, '')::smallint, nullif(spray_dir, '')
FROM stg_pa_code
ON CONFLICT (result_code) DO NOTHING;

CREATE TEMP TABLE stg_event_type (event_type text, name_en text, note text) ON COMMIT DROP;
\copy stg_event_type FROM 'data/reference/game_event_type.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO game_event_type (event_type, name_en)
SELECT event_type, name_en FROM stg_event_type
ON CONFLICT (event_type) DO NOTHING;

COMMIT;
