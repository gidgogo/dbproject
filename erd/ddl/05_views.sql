-- =====================================================================
-- KBO 야구 기록 DB · 05. 뷰 / 머티리얼라이즈드 뷰 / 함수
--
--   유도 속성(시즌 누적 성적, 순위)은 테이블에 저장하지 않고 경기 단위 기록에서 계산한다.
--     · 뷰(VIEW)            : 조회할 때마다 계산 → 항상 최신, 대신 느릴 수 있음
--     · 머티리얼라이즈드 뷰(MV): 계산 결과를 저장 → 빠름, 대신 fn_refresh_stats()로 갱신 필요
--   시즌 성적·순위처럼 화면에서 자주 읽고 데이터 적재 때만 바뀌는 값은 MV로 만들었다.
--
--   정규시즌(series_id = 0)만 집계한다.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. 경기 결과 화면
-- ---------------------------------------------------------------------
CREATE VIEW v_game_summary AS
SELECT g.game_id,
       g.kbo_game_id,
       g.game_date,
       g.season,
       g.series_id,
       g.doubleheader_no,
       g.away_team_id,
       ats.short_name                AS away_team_name,
       a.runs                        AS away_runs,
       g.home_team_id,
       hts.short_name                AS home_team_name,
       h.runs                        AS home_runs,
       CASE WHEN a.result = 'W' THEN g.away_team_id
            WHEN h.result = 'W' THEN g.home_team_id END AS winner_team_id,
       (a.result = 'D')              AS is_draw,
       s.stadium_name,
       g.attendance,
       g.start_time,
       g.end_time,
       g.duration_min
FROM game g
JOIN team_game a    ON a.game_id = g.game_id AND a.home_away = 'A'
JOIN team_game h    ON h.game_id = g.game_id AND h.home_away = 'H'
JOIN team_season ats ON ats.team_id = g.away_team_id AND ats.season = g.season
JOIN team_season hts ON hts.team_id = g.home_team_id AND hts.season = g.season
LEFT JOIN stadium s ON s.stadium_id = g.stadium_id;
COMMENT ON VIEW v_game_summary IS '경기요약: 경기 결과 화면용 (원정/홈 팀명·점수·승리팀·구장)';

-- 선발투수와 승리/패전/세이브 투수 (경기 결과 화면)
CREATE VIEW v_game_pitchers AS
SELECT pg.game_id,
       pg.team_id,
       max(pg.player_id) FILTER (WHERE pg.appearance_seq = 1) AS starter_id,
       max(pg.player_id) FILTER (WHERE pg.decision = 'W')     AS win_pitcher_id,
       max(pg.player_id) FILTER (WHERE pg.decision = 'L')     AS loss_pitcher_id,
       max(pg.player_id) FILTER (WHERE pg.decision = 'S')     AS save_pitcher_id
FROM pitcher_game pg
GROUP BY pg.game_id, pg.team_id;
COMMENT ON VIEW v_game_pitchers IS '경기투수: 팀별 선발·승리·패전·세이브 투수';

-- ---------------------------------------------------------------------
-- 2. 타자: 경기별 → 시즌별
-- ---------------------------------------------------------------------
CREATE VIEW v_batter_game_line AS
SELECT bg.game_id,
       g.game_date,
       g.season,
       g.series_id,
       bg.team_id,
       bg.player_id,
       bg.lineup_seq,
       bg.positions,
       bg.at_bats,
       bg.hits,
       bg.rbi,
       bg.runs,
       coalesce(pa.plate_appearances, 0) AS plate_appearances,
       coalesce(pa.ab_from_pa, 0)        AS ab_from_pa,
       coalesce(pa.h_from_pa, 0)         AS h_from_pa,
       coalesce(pa.doubles, 0)           AS doubles,
       coalesce(pa.triples, 0)           AS triples,
       coalesce(pa.home_runs, 0)         AS home_runs,
       coalesce(pa.walks, 0)             AS walks,
       coalesce(pa.intentional_walks, 0) AS intentional_walks,
       coalesce(pa.hbp, 0)               AS hbp,
       coalesce(pa.strikeouts, 0)        AS strikeouts,
       coalesce(pa.sac_flies, 0)         AS sac_flies,
       coalesce(pa.sac_bunts, 0)         AS sac_bunts,
       coalesce(pa.gidp, 0)              AS gidp
FROM batter_game bg
JOIN game g ON g.game_id = bg.game_id
LEFT JOIN (
    SELECT p.game_id,
           p.player_id,
           count(*)                                                AS plate_appearances,
           count(*) FILTER (WHERE t.is_at_bat)                     AS ab_from_pa,
           count(*) FILTER (WHERE t.is_hit)                        AS h_from_pa,
           count(*) FILTER (WHERE t.result_type = 'DOUBLE')        AS doubles,
           count(*) FILTER (WHERE t.result_type = 'TRIPLE')        AS triples,
           count(*) FILTER (WHERE t.result_type = 'HOME_RUN')      AS home_runs,
           count(*) FILTER (WHERE t.is_walk)                       AS walks,
           count(*) FILTER (WHERE t.result_type = 'INTENTIONAL_WALK') AS intentional_walks,
           count(*) FILTER (WHERE t.is_hbp)                        AS hbp,
           count(*) FILTER (WHERE t.is_strikeout)                  AS strikeouts,
           count(*) FILTER (WHERE t.is_sac_fly)                    AS sac_flies,
           count(*) FILTER (WHERE t.is_sac_bunt)                   AS sac_bunts,
           count(*) FILTER (WHERE t.is_double_play)                AS gidp
    FROM plate_appearance p
    JOIN pa_result_code c ON c.result_code = p.result_code
    JOIN pa_result_type t ON t.result_type = c.result_type
    GROUP BY p.game_id, p.player_id
) pa ON pa.game_id = bg.game_id AND pa.player_id = bg.player_id;
COMMENT ON VIEW v_batter_game_line IS '타자경기라인: 박스스코어(타수·안타·타점·득점) + 타석 집계(2루타·홈런·볼넷·삼진 등)';

CREATE MATERIALIZED VIEW mv_season_batting AS
WITH s AS (
    SELECT player_id, season, team_id,
           count(*)                AS games,
           sum(plate_appearances)  AS plate_appearances,
           sum(at_bats)            AS at_bats,
           sum(runs)               AS runs,
           sum(hits)               AS hits,
           sum(doubles)            AS doubles,
           sum(triples)            AS triples,
           sum(home_runs)          AS home_runs,
           sum(rbi)                AS rbi,
           sum(walks)              AS walks,
           sum(intentional_walks)  AS intentional_walks,
           sum(hbp)                AS hbp,
           sum(strikeouts)         AS strikeouts,
           sum(sac_flies)          AS sac_flies,
           sum(sac_bunts)          AS sac_bunts,
           sum(gidp)               AS gidp
    FROM v_batter_game_line
    WHERE series_id = 0
    GROUP BY player_id, season, team_id
)
SELECT s.*,
       hits + doubles + 2 * triples + 3 * home_runs                              AS total_bases,
       round(hits::numeric / nullif(at_bats, 0), 3)                                AS avg,
       round((hits + walks + hbp)::numeric / nullif(at_bats + walks + hbp + sac_flies, 0), 3) AS obp,
       round((hits + doubles + 2 * triples + 3 * home_runs)::numeric / nullif(at_bats, 0), 3) AS slg,
       round((hits + walks + hbp)::numeric / nullif(at_bats + walks + hbp + sac_flies, 0)
             + (hits + doubles + 2 * triples + 3 * home_runs)::numeric / nullif(at_bats, 0), 3) AS ops
FROM s;
CREATE UNIQUE INDEX ux_mv_season_batting ON mv_season_batting (player_id, season, team_id);
CREATE INDEX ix_mv_season_batting_season ON mv_season_batting (season, team_id);
COMMENT ON MATERIALIZED VIEW mv_season_batting IS '시즌타자성적(팀별): 경기 기록으로 계산. 타율=H/AB, 출루율=(H+BB+HBP)/(AB+BB+HBP+SF), 장타율=TB/AB';

CREATE VIEW v_season_batting_total AS
WITH s AS (
    SELECT player_id, season,
           string_agg(team_id, '/' ORDER BY team_id) AS teams,
           sum(games) AS games, sum(plate_appearances) AS plate_appearances,
           sum(at_bats) AS at_bats, sum(runs) AS runs, sum(hits) AS hits,
           sum(doubles) AS doubles, sum(triples) AS triples, sum(home_runs) AS home_runs,
           sum(total_bases) AS total_bases, sum(rbi) AS rbi, sum(walks) AS walks,
           sum(intentional_walks) AS intentional_walks, sum(hbp) AS hbp,
           sum(strikeouts) AS strikeouts, sum(sac_flies) AS sac_flies,
           sum(sac_bunts) AS sac_bunts, sum(gidp) AS gidp
    FROM mv_season_batting
    GROUP BY player_id, season
)
SELECT s.*,
       round(hits::numeric / nullif(at_bats, 0), 3) AS avg,
       round((hits + walks + hbp)::numeric / nullif(at_bats + walks + hbp + sac_flies, 0), 3) AS obp,
       round(total_bases::numeric / nullif(at_bats, 0), 3) AS slg,
       round((hits + walks + hbp)::numeric / nullif(at_bats + walks + hbp + sac_flies, 0)
             + total_bases::numeric / nullif(at_bats, 0), 3) AS ops,
       round(100.0 * strikeouts / nullif(plate_appearances, 0), 1) AS k_pct,
       round(100.0 * walks / nullif(plate_appearances, 0), 1)      AS bb_pct
FROM s;
COMMENT ON VIEW v_season_batting_total IS '시즌타자성적(합계): 시즌 중 이적한 선수의 팀별 기록을 합친 값. 선수 프로필 시즌표·선수 비교용';

-- ---------------------------------------------------------------------
-- 3. 투수: 시즌별
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_ip_display(outs numeric) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN outs IS NULL THEN NULL
                WHEN outs % 3 = 0 THEN div(outs, 3)::text
                WHEN outs < 3     THEN (outs % 3)::text || '/3'
                ELSE div(outs, 3)::text || ' ' || (outs % 3)::text || '/3' END
$$;
COMMENT ON FUNCTION fn_ip_display(numeric) IS '이닝표기: 아웃카운트 → KBO 이닝 표기 (19 → 6 1/3)';

CREATE MATERIALIZED VIEW mv_season_pitching AS
WITH s AS (
    SELECT pg.player_id, g.season, pg.team_id,
           count(*)                                                   AS games,
           count(*) FILTER (WHERE pg.appearance_seq = 1)              AS games_started,
           count(*) FILTER (WHERE pg.decision = 'W')                  AS wins,
           count(*) FILTER (WHERE pg.decision = 'L')                  AS losses,
           count(*) FILTER (WHERE pg.decision = 'S')                  AS saves,
           count(*) FILTER (WHERE pg.decision = 'H')                  AS holds,
           count(*) FILTER (WHERE pg.appearance_seq = 1 AND pg.outs_recorded >= 18
                                  AND pg.earned_runs <= 3)            AS quality_starts,
           sum(pg.outs_recorded)     AS outs_recorded,
           sum(pg.batters_faced)     AS batters_faced,
           sum(pg.at_bats)           AS at_bats,
           sum(pg.pitches)           AS pitches,
           sum(pg.hits_allowed)      AS hits_allowed,
           sum(pg.home_runs_allowed) AS home_runs_allowed,
           sum(pg.walks_hbp)         AS walks_hbp,
           sum(pg.strikeouts)        AS strikeouts,
           sum(pg.runs_allowed)      AS runs_allowed,
           sum(pg.earned_runs)       AS earned_runs
    FROM pitcher_game pg
    JOIN game g ON g.game_id = pg.game_id
    WHERE g.series_id = 0
    GROUP BY pg.player_id, g.season, pg.team_id
)
SELECT s.*,
       fn_ip_display(outs_recorded)                                                  AS ip_display,
       round(earned_runs * 27.0 / nullif(outs_recorded, 0), 2)                        AS era,
       round((hits_allowed + walks_hbp) * 3.0 / nullif(outs_recorded, 0), 2)          AS whip_incl_hbp,
       round(strikeouts * 27.0 / nullif(outs_recorded, 0), 2)                         AS k_per_9,
       round(hits_allowed::numeric / nullif(at_bats, 0), 3)                           AS opp_avg
FROM s;
CREATE UNIQUE INDEX ux_mv_season_pitching ON mv_season_pitching (player_id, season, team_id);
CREATE INDEX ix_mv_season_pitching_season ON mv_season_pitching (season, team_id);
COMMENT ON MATERIALIZED VIEW mv_season_pitching IS '시즌투수성적(팀별): ERA=자책×27/아웃. WHIP은 kbodata가 볼넷·사구를 합쳐 주므로 사구 포함 근사값';

CREATE VIEW v_season_pitching_total AS
WITH s AS (
    SELECT player_id, season,
           string_agg(team_id, '/' ORDER BY team_id) AS teams,
           sum(games) AS games, sum(games_started) AS games_started,
           sum(wins) AS wins, sum(losses) AS losses, sum(saves) AS saves, sum(holds) AS holds,
           sum(quality_starts) AS quality_starts, sum(outs_recorded) AS outs_recorded,
           sum(batters_faced) AS batters_faced, sum(at_bats) AS at_bats, sum(pitches) AS pitches,
           sum(hits_allowed) AS hits_allowed, sum(home_runs_allowed) AS home_runs_allowed,
           sum(walks_hbp) AS walks_hbp, sum(strikeouts) AS strikeouts,
           sum(runs_allowed) AS runs_allowed, sum(earned_runs) AS earned_runs
    FROM mv_season_pitching
    GROUP BY player_id, season
)
SELECT s.*,
       fn_ip_display(outs_recorded)                                         AS ip_display,
       round(earned_runs * 27.0 / nullif(outs_recorded, 0), 2)               AS era,
       round((hits_allowed + walks_hbp) * 3.0 / nullif(outs_recorded, 0), 2) AS whip_incl_hbp,
       round(strikeouts * 27.0 / nullif(outs_recorded, 0), 2)                AS k_per_9,
       round(hits_allowed::numeric / nullif(at_bats, 0), 3)                  AS opp_avg
FROM s;
COMMENT ON VIEW v_season_pitching_total IS '시즌투수성적(합계): 이적 선수 팀별 기록 합계';

-- ---------------------------------------------------------------------
-- 4. 팀 순위·상대전적
-- ---------------------------------------------------------------------
CREATE MATERIALIZED VIEW mv_team_standings AS
WITH tg AS (
    SELECT g.season, t.team_id, t.result, t.runs, o.runs AS runs_against,
           row_number() OVER (PARTITION BY g.season, t.team_id
                              ORDER BY g.game_date DESC, g.doubleheader_no DESC) AS rn_desc
    FROM team_game t
    JOIN game g      ON g.game_id = t.game_id
    JOIN team_game o ON o.game_id = t.game_id AND o.team_id <> t.team_id
    WHERE g.series_id = 0
),
agg AS (
    SELECT season, team_id,
           count(*)                                              AS games,
           count(*) FILTER (WHERE result = 'W')                  AS wins,
           count(*) FILTER (WHERE result = 'L')                  AS losses,
           count(*) FILTER (WHERE result = 'D')                  AS draws,
           sum(runs)                                             AS runs_scored,
           sum(runs_against)                                     AS runs_allowed,
           count(*) FILTER (WHERE rn_desc <= 10 AND result = 'W') AS l10_w,
           count(*) FILTER (WHERE rn_desc <= 10 AND result = 'D') AS l10_d,
           count(*) FILTER (WHERE rn_desc <= 10 AND result = 'L') AS l10_l,
           max(result) FILTER (WHERE rn_desc = 1)                AS last_result
    FROM tg
    GROUP BY season, team_id
),
stk AS (  -- 최근 경기부터 결과가 처음 바뀌는 지점까지 = 연속 기록
    SELECT tg.season, tg.team_id,
           coalesce(min(tg.rn_desc) FILTER (WHERE tg.result <> a.last_result) - 1, count(*)) AS streak_len
    FROM tg
    JOIN agg a ON a.season = tg.season AND a.team_id = tg.team_id
    GROUP BY tg.season, tg.team_id
),
pct AS (
    SELECT a.*, s.streak_len,
           a.wins::numeric / nullif(a.wins + a.losses, 0) AS win_pct_raw
    FROM agg a JOIN stk s ON s.season = a.season AND s.team_id = a.team_id
),
ranked AS (
    SELECT p.*,
           rank() OVER w                                 AS rank,
           first_value(wins)   OVER w                    AS leader_wins,
           first_value(losses) OVER w                    AS leader_losses
    FROM pct p
    WINDOW w AS (PARTITION BY season ORDER BY win_pct_raw DESC NULLS LAST)
)
SELECT season, team_id, rank, games, wins, losses, draws, round(win_pct_raw, 3) AS win_pct,
       (((leader_wins - wins) + (losses - leader_losses)) / 2.0)::numeric(4,1) AS games_behind,
       runs_scored, runs_allowed, runs_scored - runs_allowed AS run_diff,
       l10_w || '승' || l10_d || '무' || l10_l || '패' AS last10,
       streak_len || CASE last_result WHEN 'W' THEN '승' WHEN 'L' THEN '패' ELSE '무' END AS streak
FROM ranked;
CREATE UNIQUE INDEX ux_mv_team_standings ON mv_team_standings (season, team_id);
COMMENT ON MATERIALIZED VIEW mv_team_standings IS '팀순위(계산): 승률=승/(승+패), 게임차=((1위승-승)+(패-1위패))/2. ❓ 2008~2010 무승부 처리 규정 확인 필요';

CREATE VIEW v_team_head_to_head AS
SELECT g.season, t.team_id, o.team_id AS opponent_id,
       count(*)                              AS games,
       count(*) FILTER (WHERE t.result = 'W') AS wins,
       count(*) FILTER (WHERE t.result = 'L') AS losses,
       count(*) FILTER (WHERE t.result = 'D') AS draws,
       sum(t.runs) AS runs_scored, sum(o.runs) AS runs_allowed
FROM team_game t
JOIN team_game o ON o.game_id = t.game_id AND o.team_id <> t.team_id
JOIN game g      ON g.game_id = t.game_id
WHERE g.series_id = 0
GROUP BY g.season, t.team_id, o.team_id;
COMMENT ON VIEW v_team_head_to_head IS '팀상대전적: 팀 프로필 화면의 상대 팀별 승패';

-- ---------------------------------------------------------------------
-- 5. Savant식 시각화
-- ---------------------------------------------------------------------
-- 5-1. 타구 방향 (스프레이 차트) — kbodata 타석 결과 코드의 수비 위치로 추정
CREATE VIEW v_spray_chart AS
SELECT p.player_id, g.season, c.spray_dir, t.result_type, t.result_type_name,
       count(*) AS events
FROM plate_appearance p
JOIN game g           ON g.game_id = p.game_id
JOIN pa_result_code c ON c.result_code = p.result_code
JOIN pa_result_type t ON t.result_type = c.result_type
WHERE c.spray_dir IS NOT NULL AND g.series_id = 0
GROUP BY p.player_id, g.season, c.spray_dir, t.result_type, t.result_type_name;
COMMENT ON VIEW v_spray_chart IS '스프레이차트: 타자·시즌·방향(L/LC/C/RC/R)·결과유형별 타구 수';

-- 5-2. 스트라이크존 구역 (Statcast 방식: 존 안 1~9, 존 밖 11~14)
CREATE OR REPLACE FUNCTION fn_strike_zone(px numeric, pz numeric, top numeric, bot numeric)
RETURNS smallint LANGUAGE sql IMMUTABLE AS $$
    -- 홈플레이트 폭 17인치 = ±0.708ft. 포수 시점에서 왼쪽(3루 쪽)이 음수.
    SELECT CASE
        WHEN px IS NULL OR pz IS NULL OR top IS NULL OR bot IS NULL OR top <= bot THEN NULL
        WHEN abs(px) <= 0.708 AND pz BETWEEN bot AND top THEN
            (3 * least(2, floor((top - pz) / ((top - bot) / 3)))::int
             + least(2, floor((px + 0.708) / (1.416 / 3)))::int + 1)::smallint
        WHEN pz >= (top + bot) / 2 THEN (CASE WHEN px < 0 THEN 11 ELSE 12 END)::smallint
        ELSE (CASE WHEN px < 0 THEN 13 ELSE 14 END)::smallint
    END
$$;
COMMENT ON FUNCTION fn_strike_zone(numeric, numeric, numeric, numeric) IS '스트라이크존구역: 1~9 존 안(포수 시점 왼쪽 위가 1), 11~14 존 밖';

CREATE VIEW v_pitch_detail AS
SELECT p.*,
       g.season,
       r.call_type,
       fn_strike_zone(p.plate_x, p.plate_z, p.sz_top, p.sz_bot)              AS zone,
       (p.pitch_result_code IN ('S', 'F', 'H', 'V', 'W'))                    AS is_swing,
       (p.pitch_result_code IN ('S', 'V'))                                   AS is_whiff,
       t.statcast_code,
       t.pitch_group
FROM pitch p
JOIN game g              ON g.game_id = p.game_id
LEFT JOIN pitch_result r ON r.pitch_result_code = p.pitch_result_code
LEFT JOIN pitch_type t   ON t.pitch_type_ko = p.pitch_type_ko;
COMMENT ON VIEW v_pitch_detail IS '투구상세: 존 구역, 스윙·헛스윙 여부를 붙인 투구 (히트맵용)';

CREATE VIEW v_pitch_mix AS
SELECT pitcher_id, season, pitch_type_ko,
       count(*) AS pitches,
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY pitcher_id, season), 1) AS usage_pct,
       round(avg(speed_kmh), 1)  AS avg_speed_kmh,
       max(speed_kmh)            AS max_speed_kmh,
       round(100.0 * count(*) FILTER (WHERE is_whiff) / nullif(count(*) FILTER (WHERE is_swing), 0), 1) AS whiff_pct,
       round(100.0 * count(*) FILTER (WHERE zone BETWEEN 1 AND 9) / nullif(count(zone), 0), 1)          AS zone_pct
FROM v_pitch_detail
WHERE pitch_type_ko IS NOT NULL
GROUP BY pitcher_id, season, pitch_type_ko;
COMMENT ON VIEW v_pitch_mix IS '구종구성: 투수·시즌·구종별 비율, 평균/최고 구속, 헛스윙률, 존 투구율';

-- 5-3. 백분위 (Savant 퍼센타일 막대) — 규정타석(팀 경기 수 × 3.1) 이상 타자 대상
CREATE VIEW v_batting_percentile AS
WITH lg AS (
    SELECT season, max(games) AS team_games FROM mv_team_standings GROUP BY season
), q AS (
    SELECT b.*
    FROM v_season_batting_total b
    JOIN lg ON lg.season = b.season
    WHERE b.plate_appearances >= 3.1 * lg.team_games
)
SELECT player_id, season, plate_appearances, avg, obp, slg, ops, home_runs, k_pct, bb_pct,
       round(100 * percent_rank() OVER (PARTITION BY season ORDER BY avg))         AS avg_pctl,
       round(100 * percent_rank() OVER (PARTITION BY season ORDER BY obp))         AS obp_pctl,
       round(100 * percent_rank() OVER (PARTITION BY season ORDER BY slg))         AS slg_pctl,
       round(100 * percent_rank() OVER (PARTITION BY season ORDER BY ops))         AS ops_pctl,
       round(100 * percent_rank() OVER (PARTITION BY season ORDER BY home_runs))   AS hr_pctl,
       round(100 * percent_rank() OVER (PARTITION BY season ORDER BY k_pct DESC))  AS k_pct_pctl,
       round(100 * percent_rank() OVER (PARTITION BY season ORDER BY bb_pct))      AS bb_pct_pctl
FROM q;
COMMENT ON VIEW v_batting_percentile IS '타자백분위: 규정타석 이상 타자 중 백분위 (삼진율은 낮을수록 높은 백분위)';

-- ---------------------------------------------------------------------
-- 6. 데이터 검증 뷰 (행이 나오면 문제가 있는 것)
-- ---------------------------------------------------------------------
CREATE VIEW v_check_team_runs AS
SELECT t.game_id, t.team_id, t.runs, coalesce(sum(i.runs), 0) AS inning_runs_sum
FROM team_game t
LEFT JOIN inning_score i ON i.game_id = t.game_id AND i.team_id = t.team_id
GROUP BY t.game_id, t.team_id, t.runs
HAVING t.runs <> coalesce(sum(i.runs), 0);
COMMENT ON VIEW v_check_team_runs IS '검증: 팀 득점(R) ≠ 이닝 득점 합';

CREATE VIEW v_check_team_hits AS
SELECT t.game_id, t.team_id, t.hits, t.runs,
       coalesce(sum(b.hits), 0) AS batter_hits_sum,
       coalesce(sum(b.runs), 0) AS batter_runs_sum
FROM team_game t
LEFT JOIN batter_game b ON b.game_id = t.game_id AND b.team_id = t.team_id
GROUP BY t.game_id, t.team_id, t.hits, t.runs
HAVING t.hits <> coalesce(sum(b.hits), 0) OR t.runs <> coalesce(sum(b.runs), 0);
COMMENT ON VIEW v_check_team_hits IS '검증: 팀 안타·득점 ≠ 타자 안타·득점 합';

CREATE VIEW v_check_batter_pa AS
SELECT game_id, player_id, at_bats, ab_from_pa, hits, h_from_pa
FROM v_batter_game_line
WHERE at_bats <> ab_from_pa OR hits <> h_from_pa;
COMMENT ON VIEW v_check_batter_pa IS '검증: 박스스코어 타수·안타 ≠ 타석 결과로 센 타수·안타 (1NF 변환 검증)';

CREATE VIEW v_check_game_result AS
SELECT g.game_id, a.result AS away_result, a.runs AS away_runs, h.result AS home_result, h.runs AS home_runs
FROM game g
LEFT JOIN team_game a ON a.game_id = g.game_id AND a.home_away = 'A'
LEFT JOIN team_game h ON h.game_id = g.game_id AND h.home_away = 'H'
WHERE a.game_id IS NULL OR h.game_id IS NULL
   OR NOT (   (a.result = 'W' AND h.result = 'L' AND a.runs > h.runs)
           OR (a.result = 'L' AND h.result = 'W' AND a.runs < h.runs)
           OR (a.result = 'D' AND h.result = 'D' AND a.runs = h.runs));
COMMENT ON VIEW v_check_game_result IS '검증: 홈·원정 기록이 누락되거나 승패와 점수가 맞지 않는 경기';

CREATE VIEW v_check_pitcher_decision AS
SELECT g.game_id,
       count(*) FILTER (WHERE pg.decision = 'W') AS w_cnt,
       count(*) FILTER (WHERE pg.decision = 'L') AS l_cnt,
       bool_or(t.result = 'D')                    AS is_draw
FROM game g
JOIN pitcher_game pg ON pg.game_id = g.game_id
JOIN team_game t     ON t.game_id = g.game_id AND t.team_id = pg.team_id
GROUP BY g.game_id
HAVING (bool_or(t.result = 'D') AND (count(*) FILTER (WHERE pg.decision IN ('W', 'L')) > 0))
    OR (NOT bool_or(t.result = 'D') AND (count(*) FILTER (WHERE pg.decision = 'W') <> 1
                                         OR count(*) FILTER (WHERE pg.decision = 'L') <> 1));
COMMENT ON VIEW v_check_pitcher_decision IS '검증: 승리/패전 투수가 정확히 1명씩이 아닌 경기 (kbodata 결과 변환 버그 탐지)';

-- 기록실 공식 값과 계산 값 비교 (보고서 "일치율" 근거)
CREATE VIEW v_compare_batting_official AS
WITH o AS (
    SELECT player_id, season, sum(games) AS games, sum(plate_appearances) AS pa,
           sum(at_bats) AS ab, sum(hits) AS h, sum(home_runs) AS hr, sum(rbi) AS rbi,
           sum(walks) AS bb, sum(strikeouts) AS so,
           round(sum(hits)::numeric / nullif(sum(at_bats), 0), 3) AS avg
    FROM season_batting_official
    GROUP BY player_id, season
)
SELECT o.player_id, o.season,
       o.games AS games_off, c.games AS games_calc,
       o.pa AS pa_off, c.plate_appearances AS pa_calc,
       o.ab AS ab_off, c.at_bats AS ab_calc,
       o.h AS h_off, c.hits AS h_calc,
       o.hr AS hr_off, c.home_runs AS hr_calc,
       o.rbi AS rbi_off, c.rbi AS rbi_calc,
       o.bb AS bb_off, c.walks AS bb_calc,
       o.so AS so_off, c.strikeouts AS so_calc,
       o.avg AS avg_off, c.avg AS avg_calc,
       (c.player_id IS NOT NULL
        AND o.ab = c.at_bats AND o.h = c.hits AND o.hr = c.home_runs
        AND o.rbi = c.rbi AND o.bb = c.walks AND o.so = c.strikeouts) AS is_match
FROM o
LEFT JOIN v_season_batting_total c ON c.player_id = o.player_id AND c.season = o.season;
COMMENT ON VIEW v_compare_batting_official IS '검증: 기록실 시즌 타격 vs 경기 기록 집계 (is_match = 주요 항목 모두 일치)';

CREATE VIEW v_compare_pitching_official AS
WITH o AS (
    SELECT player_id, season, sum(games) AS games, sum(wins) AS w, sum(losses) AS l,
           sum(saves) AS sv, sum(holds) AS hld, sum(outs_recorded) AS outs,
           sum(hits_allowed) AS h, sum(strikeouts) AS so, sum(earned_runs) AS er,
           round(sum(earned_runs) * 27.0 / nullif(sum(outs_recorded), 0), 2) AS era
    FROM season_pitching_official
    GROUP BY player_id, season
)
SELECT o.player_id, o.season,
       o.games AS games_off, c.games AS games_calc,
       o.w AS w_off, c.wins AS w_calc, o.l AS l_off, c.losses AS l_calc,
       o.sv AS sv_off, c.saves AS sv_calc, o.hld AS hld_off, c.holds AS hld_calc,
       o.outs AS outs_off, c.outs_recorded AS outs_calc,
       o.h AS h_off, c.hits_allowed AS h_calc, o.so AS so_off, c.strikeouts AS so_calc,
       o.er AS er_off, c.earned_runs AS er_calc, o.era AS era_off, c.era AS era_calc,
       (c.player_id IS NOT NULL
        AND o.outs = c.outs_recorded AND o.h = c.hits_allowed AND o.so = c.strikeouts
        AND o.er = c.earned_runs) AS is_match
FROM o
LEFT JOIN v_season_pitching_total c ON c.player_id = o.player_id AND c.season = o.season;
COMMENT ON VIEW v_compare_pitching_official IS '검증: 기록실 시즌 투구 vs 경기 기록 집계';

CREATE VIEW v_compare_team_rank AS
SELECT o.season, o.team_id, o.as_of_date,
       o.rank AS rank_off, c.rank AS rank_calc,
       o.wins AS w_off, c.wins AS w_calc, o.losses AS l_off, c.losses AS l_calc,
       o.draws AS d_off, c.draws AS d_calc, o.win_pct AS pct_off, c.win_pct AS pct_calc,
       (o.wins = c.wins AND o.losses = c.losses AND o.draws = c.draws) AS is_match
FROM team_rank_official o
LEFT JOIN mv_team_standings c ON c.season = o.season AND c.team_id = o.team_id
WHERE o.as_of_date = (SELECT max(as_of_date) FROM team_rank_official x WHERE x.season = o.season);
COMMENT ON VIEW v_compare_team_rank IS '검증: 기록실 팀 순위(시즌 마지막 기준일) vs 경기 기록으로 계산한 순위';

-- ---------------------------------------------------------------------
-- 7. MV 갱신 (데이터 적재 후 한 번 호출: SELECT fn_refresh_stats();)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_refresh_stats() RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    REFRESH MATERIALIZED VIEW mv_season_batting;
    REFRESH MATERIALIZED VIEW mv_season_pitching;
    REFRESH MATERIALIZED VIEW mv_team_standings;
END;
$$;
COMMENT ON FUNCTION fn_refresh_stats() IS 'MV갱신: 경기 데이터 적재 후 시즌 성적·순위 MV를 다시 계산';
