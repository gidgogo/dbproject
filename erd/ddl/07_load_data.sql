-- =====================================================================
-- KBO 야구 기록 DB · 07. 수집 데이터 적재 (data/load/*.csv)
--   먼저 CSV를 만든다:
--     python etl/crawl_to_tables.py          # 선수·기록실 → data/load
--     python etl/kbodata_to_tables.py <raw.json ...>   # 경기 → data/load
--   그다음 레포 최상위 폴더에서:
--     psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/07_load_data.sql
--   같은 파일을 다시 적재해도 된다(경기는 갱신, 박스스코어만 교체, 투구는 보존).
-- =====================================================================
\set ON_ERROR_STOP on
BEGIN;

-- 1. 선수 ---------------------------------------------------------------
CREATE TEMP TABLE stg_player (LIKE player INCLUDING DEFAULTS) ON COMMIT DROP;
ALTER TABLE stg_player ALTER COLUMN is_retired DROP NOT NULL;
\copy stg_player FROM 'data/load/player.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO player
SELECT player_id, player_name, birth_date, height_cm, weight_kg, throws, bats, position, career,
       draft_info, draft_year, join_info, join_year, signing_bonus_10k,
       coalesce(is_retired, false), profile_crawled_at
FROM stg_player
ON CONFLICT (player_id) DO UPDATE SET
    player_name        = EXCLUDED.player_name,
    birth_date         = coalesce(EXCLUDED.birth_date, player.birth_date),
    height_cm          = coalesce(EXCLUDED.height_cm, player.height_cm),
    weight_kg          = coalesce(EXCLUDED.weight_kg, player.weight_kg),
    throws             = coalesce(EXCLUDED.throws, player.throws),
    bats               = coalesce(EXCLUDED.bats, player.bats),
    position           = coalesce(EXCLUDED.position, player.position),
    career             = coalesce(EXCLUDED.career, player.career),
    draft_info         = coalesce(EXCLUDED.draft_info, player.draft_info),
    draft_year         = coalesce(EXCLUDED.draft_year, player.draft_year),
    join_info          = coalesce(EXCLUDED.join_info, player.join_info),
    join_year          = coalesce(EXCLUDED.join_year, player.join_year),
    signing_bonus_10k  = coalesce(EXCLUDED.signing_bonus_10k, player.signing_bonus_10k),
    is_retired         = EXCLUDED.is_retired,
    profile_crawled_at = coalesce(EXCLUDED.profile_crawled_at, player.profile_crawled_at);

CREATE TEMP TABLE stg_player_season (LIKE player_season) ON COMMIT DROP;
\copy stg_player_season FROM 'data/load/player_season.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO player_season SELECT * FROM stg_player_season
ON CONFLICT (player_id, season, team_id) DO UPDATE SET
    name_in_season = EXCLUDED.name_in_season,
    is_batter      = player_season.is_batter OR EXCLUDED.is_batter,
    is_pitcher     = player_season.is_pitcher OR EXCLUDED.is_pitcher,
    uniform_no     = coalesce(EXCLUDED.uniform_no, player_season.uniform_no);

CREATE TEMP TABLE stg_player_salary (LIKE player_salary) ON COMMIT DROP;
\copy stg_player_salary FROM 'data/load/player_salary.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO player_salary SELECT * FROM stg_player_salary
ON CONFLICT (player_id, season) DO UPDATE SET
    salary_10k_krw = EXCLUDED.salary_10k_krw, salary_usd = EXCLUDED.salary_usd,
    source_text = EXCLUDED.source_text;

-- 2. 기록실 공식 기록 ---------------------------------------------------
CREATE TEMP TABLE stg_sbo (LIKE season_batting_official) ON COMMIT DROP;
ALTER TABLE stg_sbo ALTER COLUMN crawled_at DROP NOT NULL;
\copy stg_sbo FROM 'data/load/season_batting_official.csv' WITH (FORMAT csv, HEADER true)
DELETE FROM season_batting_official s USING stg_sbo t
 WHERE s.player_id = t.player_id AND s.season = t.season AND s.team_id = t.team_id;
INSERT INTO season_batting_official
SELECT player_id, season, team_id, games, plate_appearances, at_bats, runs, hits, doubles, triples,
       home_runs, total_bases, rbi, sac_bunts, sac_flies, walks, intentional_walks, hbp, strikeouts,
       gidp, avg, obp, slg, ops, coalesce(crawled_at, now())
FROM stg_sbo;

CREATE TEMP TABLE stg_spo (LIKE season_pitching_official) ON COMMIT DROP;
ALTER TABLE stg_spo ALTER COLUMN crawled_at DROP NOT NULL;
\copy stg_spo FROM 'data/load/season_pitching_official.csv' WITH (FORMAT csv, HEADER true)
DELETE FROM season_pitching_official s USING stg_spo t
 WHERE s.player_id = t.player_id AND s.season = t.season AND s.team_id = t.team_id;
INSERT INTO season_pitching_official
SELECT player_id, season, team_id, games, wins, losses, saves, holds, outs_recorded, hits_allowed,
       home_runs_allowed, walks, hbp, strikeouts, runs_allowed, earned_runs, batters_faced, pitches,
       complete_games, shutouts, quality_starts, blown_saves, era, whip, coalesce(crawled_at, now())
FROM stg_spo;

CREATE TEMP TABLE stg_tro (LIKE team_rank_official) ON COMMIT DROP;
ALTER TABLE stg_tro ALTER COLUMN crawled_at DROP NOT NULL;
\copy stg_tro FROM 'data/load/team_rank_official.csv' WITH (FORMAT csv, HEADER true)
DELETE FROM team_rank_official s USING stg_tro t
 WHERE s.season = t.season AND s.team_id = t.team_id AND s.as_of_date = t.as_of_date;
INSERT INTO team_rank_official
SELECT season, team_id, as_of_date, rank, games, wins, losses, draws, win_pct, games_behind,
       last10, streak, coalesce(crawled_at, now())
FROM stg_tro;

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
-- 이닝·타자·투수·타석은 team_game에서 CASCADE. game을 참조하는 pitch는 유지된다.
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
