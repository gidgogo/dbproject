-- =====================================================================
-- KBO 야구 기록 DB · 03. 인덱스
--   PK·UNIQUE 제약은 자동으로 인덱스를 만든다. 여기에는 화면별 조회 패턴에 맞춰
--   "PK의 첫 컬럼이 아닌 컬럼으로 찾는" 경우만 추가했다.
--   (복합 PK (game_id, player_id)는 game_id로는 빨리 찾지만 player_id만으로는 못 찾는다)
-- =====================================================================

-- 경기 결과 화면: 날짜별·시즌별·팀별 경기 목록
CREATE INDEX ix_game_date            ON game (game_date);
CREATE INDEX ix_game_season_series   ON game (season, series_id);
CREATE INDEX ix_game_home_team       ON game (home_team_id, season);
CREATE INDEX ix_game_away_team       ON game (away_team_id, season);

-- 팀 프로필·순위: 팀의 전체 경기 (PK가 (game_id, team_id)라 team_id 단독 검색용)
CREATE INDEX ix_team_game_team       ON team_game (team_id);

-- 선수 프로필: 선수의 경기별 기록 (시즌 기록 집계, 최근 경기 목록)
CREATE INDEX ix_batter_game_player   ON batter_game (player_id);
CREATE INDEX ix_pitcher_game_player  ON pitcher_game (player_id);

-- 선수 프로필: 한 선수의 타석 집계 (PK가 game_id로 시작해서 player_id만으로는 못 찾음)
--   tools/perf_check.sql 에서 순차 탐색(Seq Scan)을 발견해 추가했다.
CREATE INDEX ix_pa_player            ON plate_appearance (player_id);
-- 타석 결과별 집계(스프레이 차트 등)
CREATE INDEX ix_pa_result_code       ON plate_appearance (result_code);

-- 선수 검색·이름 매핑
CREATE INDEX ix_player_name          ON player (player_name);
CREATE INDEX ix_player_season_lookup ON player_season (season, team_id, name_in_season);

-- 기타 기록: 선수별 (예: 선수의 결승타 목록)
CREATE INDEX ix_game_event_player    ON game_event (player_id) WHERE player_id IS NOT NULL;

-- 심판별 경기
CREATE INDEX ix_game_umpire_umpire   ON game_umpire (umpire_id);

-- Savant식 시각화: 투수별·타자별 투구
CREATE INDEX ix_pitch_pitcher        ON pitch (pitcher_id, pitch_type_ko);
CREATE INDEX ix_pitch_batter         ON pitch (batter_id);
