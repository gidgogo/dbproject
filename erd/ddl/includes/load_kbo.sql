-- 07_load_data.sql / 11_load_kbo.sql 내부에서 트랜잭션 안에 실행
-- 1. 선수 ---------------------------------------------------------------
CREATE TEMP TABLE stg_player (LIKE player INCLUDING DEFAULTS) ON COMMIT DROP;
ALTER TABLE stg_player ALTER COLUMN is_retired DROP NOT NULL;
\copy stg_player FROM 'data/load/player.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO player
SELECT player_id, player_name, birth_date, height_cm, weight_kg, throws, bats, position, career,
       draft_info, draft_year, join_info, join_year, signing_bonus_10k,
       coalesce(is_retired, false), profile_crawled_at, current_team_name, current_uniform_no, profile_source_url
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
    profile_crawled_at = coalesce(EXCLUDED.profile_crawled_at, player.profile_crawled_at),
    current_team_name = CASE WHEN EXCLUDED.profile_crawled_at IS NOT NULL THEN EXCLUDED.current_team_name ELSE player.current_team_name END,
    current_uniform_no = CASE WHEN EXCLUDED.profile_crawled_at IS NOT NULL THEN EXCLUDED.current_uniform_no ELSE player.current_uniform_no END,
    profile_source_url = coalesce(EXCLUDED.profile_source_url, player.profile_source_url);

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
