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
--   kbodata_to_tables.py 가 선수ID 실패·모르는 타석 코드 때문에 멈췄으면(_load_status.csv = blocked)
--   아무것도 바꾸지 않고 중단한다. 다른 변환기로 CSV를 만들면 _load_status.csv(status,detail / ok,…)도 같이 만든다.
--   커밋 직전에 경기마다 홈·원정 기록, 타자·투수가 1명 이상이고 행 번호(lineup_seq·appearance_seq)가 1..n으로 연속인지,
--   팀 안타·득점 = 타자 합을 검사해서 하나라도 어긋나면 전체를 되돌린다(기존 기록 보존).
--   마지막에 fn_refresh_stats()로 시즌 성적·순위 MV를 갱신한다(MV 갱신은 적재 담당 몫).
--   복합키 테이블의 id(대리키)는 DB가 자동으로 매기므로 CSV에 없다.
-- =====================================================================
\set ON_ERROR_STOP on
BEGIN;

-- 0. 경기 변환이 끝까지 성공했는지 먼저 확인 -----------------------------------
CREATE TEMP TABLE stg_load_status (status text, detail text) ON COMMIT DROP;
\copy stg_load_status FROM 'data/load/_load_status.csv' WITH (FORMAT csv, HEADER true)
DO $$
DECLARE d text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM stg_load_status WHERE status = 'ok') THEN
        SELECT string_agg(coalesce(detail, ''), '; ') INTO d FROM stg_load_status;
        RAISE EXCEPTION '경기 변환이 불완전해 적재를 중단합니다 (%). data/load/_kbodata_report.md 를 확인하세요', d;
    END IF;
END $$;

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

-- FK·트리거만으로는 빠진 팀·선수를 찾을 수 없으므로 커밋 직전에 검사한다.
-- 하나라도 걸리면 예외 → 트랜잭션 전체가 되돌아가서 기존 기록이 그대로 남는다.
DO $$
DECLARE bad text;
BEGIN
    SELECT string_agg(match_id, ', ') INTO bad FROM (
        SELECT s.match_id FROM stg_match s LEFT JOIN match_team t USING (match_id)
        GROUP BY s.match_id HAVING count(t.team_id) <> 2 ORDER BY 1 LIMIT 20) x;
    IF bad IS NOT NULL THEN
        RAISE EXCEPTION '경기마다 홈·원정 팀경기기록이 각각 하나씩 필요합니다: %', bad;
    END IF;

    -- 타자: 팀마다 1명 이상, 박스스코어 행 번호(lineup_seq)가 1부터 빈 번호 없이 이어져야 한다
    -- (변환기는 원본 행마다 번호를 매기므로 중간 선수가 빠지면 번호가 빈다)
    SELECT string_agg(match_id || ' ' || team_id, ', ') INTO bad FROM (
        SELECT t.match_id, t.team_id
        FROM match_team t JOIN stg_match s USING (match_id)
        LEFT JOIN batter_match b ON b.match_id = t.match_id AND b.team_id = t.team_id
        GROUP BY t.match_id, t.team_id
        HAVING count(b.lineup_seq) = 0 OR min(b.lineup_seq) <> 1
            OR max(b.lineup_seq) <> count(b.lineup_seq) OR count(DISTINCT b.lineup_seq) <> count(b.lineup_seq)
        ORDER BY 1, 2 LIMIT 20) x;
    IF bad IS NOT NULL THEN
        RAISE EXCEPTION '타자 기록이 빠졌습니다(lineup_seq가 1..n이 아님): %', bad;
    END IF;

    -- 투수: 팀마다 1명 이상, 등판 순서(appearance_seq)가 1부터 빈 번호 없이 이어져야 한다
    SELECT string_agg(match_id || ' ' || team_id, ', ') INTO bad FROM (
        SELECT t.match_id, t.team_id
        FROM match_team t JOIN stg_match s USING (match_id)
        LEFT JOIN pitcher_match p ON p.match_id = t.match_id AND p.team_id = t.team_id
        GROUP BY t.match_id, t.team_id
        HAVING count(p.appearance_seq) = 0 OR min(p.appearance_seq) <> 1
            OR max(p.appearance_seq) <> count(p.appearance_seq)
            OR count(DISTINCT p.appearance_seq) <> count(p.appearance_seq)
        ORDER BY 1, 2 LIMIT 20) x;
    IF bad IS NOT NULL THEN
        RAISE EXCEPTION '투수 기록이 빠졌습니다(등판 순서가 1..n이 아님): %', bad;
    END IF;

    -- 팀 안타·득점 = 타자 안타·득점 합 (마지막 타자가 빠진 경우도 여기서 걸린다)
    SELECT string_agg(v.match_id || ' ' || v.team_id, ', ') INTO bad FROM (
        SELECT v.match_id, v.team_id FROM v_check_team_hits v JOIN stg_match s USING (match_id)
        ORDER BY 1, 2 LIMIT 20) v;
    IF bad IS NOT NULL THEN
        RAISE EXCEPTION '팀 안타·득점과 타자 기록 합이 다릅니다(v_check_team_hits): %', bad;
    END IF;
END $$;

COMMIT;

-- 4. 시즌 성적·순위 MV 다시 계산 -----------------------------------------
SELECT fn_refresh_stats();
