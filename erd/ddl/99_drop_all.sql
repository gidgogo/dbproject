-- 개발용: 이 프로젝트가 만든 객체를 모두 지운다 (데이터도 삭제됨, 주의)
DROP MATERIALIZED VIEW IF EXISTS mv_team_standings, mv_season_pitching, mv_season_batting CASCADE;
DROP TABLE IF EXISTS
    team_rank_official, season_pitching_official, season_batting_official,
    pitch, pitch_result, pitch_type,
    game_umpire, umpire, game_event, game_event_type,
    pitcher_game, plate_appearance, batter_game, pa_result_code, pa_result_type,
    inning_score, team_game, game,
    player_salary, player_season, player,
    team_season, stadium, team CASCADE;
DROP FUNCTION IF EXISTS fn_team_game_check_side(), fn_refresh_stats(),
    fn_ip_display(numeric), fn_strike_zone(numeric, numeric, numeric, numeric) CASCADE;
DROP DOMAIN IF EXISTS d_team_id, d_player_id, d_game_id, d_season, d_inning, d_count,
    d_total, d_outs, d_rate, d_slg, d_era, d_hand, d_person_name CASCADE;
