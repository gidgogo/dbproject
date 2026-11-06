-- 기존 DB에 검토 수정본 뷰를 적용한다. 원본 테이블·수집 데이터는 보존한다.
-- psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/09_upgrade_views.sql
-- 외부에서 추가한 종속 뷰가 있으면 CASCADE로 지우지 않고 전체 작업을 롤백한다.
\set ON_ERROR_STOP on
BEGIN;
DROP VIEW v_batting_percentile, v_compare_batting_official, v_compare_pitching_official,
          v_compare_team_rank, v_season_batting_total, v_season_pitching_total;
DROP MATERIALIZED VIEW mv_team_standings, mv_season_batting, mv_season_pitching;
DROP VIEW v_game_summary, v_game_pitchers, v_batter_game_line, v_team_head_to_head,
          v_spray_chart, v_check_team_runs,
          v_check_team_hits, v_check_batter_pa, v_check_game_result, v_check_pitcher_decision;
\ir 05_views.sql
COMMIT;
