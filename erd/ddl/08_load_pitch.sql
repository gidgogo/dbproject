-- =====================================================================
-- KBO 야구 기록 DB · 08. 네이버 투구 데이터 적재 (data/load/pitch.csv)
--   python etl/pitches_to_tables.py data/pitches_2025_OB.csv
--   psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/08_load_pitch.sql   (레포 최상위 폴더에서)
--   경기(game)가 먼저 적재되어 있어야 한다. 없는 경기의 투구는 건너뛰고 개수를 알려 준다.
-- =====================================================================
\set ON_ERROR_STOP on
BEGIN;
CREATE TEMP TABLE stg_pitch (LIKE pitch) ON COMMIT DROP;
\copy stg_pitch FROM 'data/load/pitch.csv' WITH (FORMAT csv, HEADER true)

SELECT count(*) FILTER (WHERE g.game_id IS NULL)                         AS skipped_no_game,
       count(*) FILTER (WHERE g.game_id IS NOT NULL AND (pp.player_id IS NULL OR pb.player_id IS NULL))
                                                                         AS skipped_no_player,
       count(*) FILTER (WHERE g.game_id IS NOT NULL AND pp.player_id IS NOT NULL AND pb.player_id IS NOT NULL)
                                                                         AS to_load
FROM stg_pitch s
LEFT JOIN game g    ON g.game_id = s.game_id
LEFT JOIN player pp ON pp.player_id = s.pitcher_id
LEFT JOIN player pb ON pb.player_id = s.batter_id;

DELETE FROM pitch WHERE game_id IN (SELECT DISTINCT game_id FROM stg_pitch);
INSERT INTO pitch
SELECT s.* FROM stg_pitch s
WHERE EXISTS (SELECT 1 FROM game g WHERE g.game_id = s.game_id)
  AND EXISTS (SELECT 1 FROM player p WHERE p.player_id = s.pitcher_id)
  AND EXISTS (SELECT 1 FROM player p WHERE p.player_id = s.batter_id);
COMMIT;
