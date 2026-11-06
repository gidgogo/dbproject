-- 기존 DB를 KBO 중심 설계로 전환. 기존 네이버 자료는 삭제하지 않고 legacy_naver로 이동.
-- 실행 후 새 ETL로 data/load CSV를 다시 만들어야 한다. 재실행 가능.
\set ON_ERROR_STOP on
BEGIN;
CREATE SCHEMA IF NOT EXISTS legacy_naver;
DO $$
DECLARE obj text;
BEGIN
    FOREACH obj IN ARRAY ARRAY['v_pitch_mix', 'v_pitch_detail'] LOOP
        IF to_regclass('public.' || obj) IS NOT NULL THEN
            EXECUTE format('ALTER VIEW public.%I SET SCHEMA legacy_naver', obj);
        END IF;
    END LOOP;
    FOREACH obj IN ARRAY ARRAY['pitch', 'pitch_type', 'pitch_result'] LOOP
        IF to_regclass('public.' || obj) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I SET SCHEMA legacy_naver', obj);
        END IF;
    END LOOP;
    IF to_regprocedure('public.fn_strike_zone(numeric,numeric,numeric,numeric)') IS NOT NULL THEN
        ALTER FUNCTION public.fn_strike_zone(numeric,numeric,numeric,numeric) SET SCHEMA legacy_naver;
    END IF;
END $$;
ALTER TABLE player ADD COLUMN IF NOT EXISTS current_team_name varchar(60);
ALTER TABLE player ADD COLUMN IF NOT EXISTS current_uniform_no varchar(3);
ALTER TABLE player ADD COLUMN IF NOT EXISTS profile_source_url text;
ALTER TABLE player DROP CONSTRAINT IF EXISTS ck_player_current_uniform;
ALTER TABLE player ADD CONSTRAINT ck_player_current_uniform CHECK (current_uniform_no ~ '^[0-9]{1,3}$');
COMMENT ON COLUMN player.current_team_name IS '현재소속명: 프로필 수집 시점의 소속 원문. 상무 등 KBO 10개 구단 외 소속도 보존하며 과거 시즌 소속과 구분';
COMMENT ON COLUMN player.current_uniform_no IS '현재등번호: 프로필 수집 시점의 등번호. 과거 시즌에 소급하지 않음';
COMMENT ON COLUMN player.profile_source_url IS '프로필출처: KBO playerId가 포함된 상세 페이지 URL';
COMMENT ON COLUMN player_season.uniform_no IS '시즌등번호: 별도 시즌 근거가 있을 때만 입력. 현재 프로필의 등번호는 player.current_uniform_no에 저장';
COMMENT ON COLUMN game.kbo_game_id     IS 'KBO경기ID: KBO 게임센터 G_ID (밑줄 제거, 생성 컬럼)';
COMMENT ON TABLE  season_batting_official IS '시즌타자기록(공식): KBO 기록실 시즌 누적 값. 화면에 직접 조회하고 경기 집계와 비교·검증한다';
COMMENT ON TABLE  season_pitching_official IS '시즌투수기록(공식): KBO 기록실 시즌 누적 값 (화면 조회 및 경기 집계 검증용)';
COMMIT;
-- 최신 박스스코어 계산 뷰로 교체 (별도 트랜잭션, 원본 데이터 보존).
\ir 09_upgrade_views.sql
