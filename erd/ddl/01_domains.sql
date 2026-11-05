-- =====================================================================
-- KBO 야구 기록 DB · 01. 도메인 정의
--   도메인 정의서(보고서 9장)의 내용을 PostgreSQL DOMAIN으로 그대로 옮겼다.
--   같은 의미의 컬럼은 같은 도메인을 쓰기 때문에 자료형·허용 범위가 한곳에서 관리된다.
--   예) 모든 "선수ID" 컬럼은 d_player_id → 양의 정수만 허용
-- 대상: PostgreSQL 14 이상 (16에서 검증)
-- =====================================================================

-- 식별자 ---------------------------------------------------------------
CREATE DOMAIN d_team_id AS char(2)
    CHECK (VALUE ~ '^[A-Z]{2}$');
COMMENT ON DOMAIN d_team_id IS '팀ID: KBO 팀코드 2자리 영문 대문자 (OB, LT, SS, HH, LG, HT, SK, WO, NC, KT)';

CREATE DOMAIN d_player_id AS integer
    CHECK (VALUE > 0);
COMMENT ON DOMAIN d_player_id IS '선수ID: KBO 공식 홈페이지 playerId (예: 76232)';

CREATE DOMAIN d_game_id AS varchar(14)
    CHECK (VALUE ~ '^[0-9]{8}_[A-Z]{4}[0-9]$');
COMMENT ON DOMAIN d_game_id IS '경기ID: kbodata 형식 YYYYMMDD_원정팀코드홈팀코드더블헤더 (예: 20250601_OBWO0)';

-- 시간·순서 ------------------------------------------------------------
CREATE DOMAIN d_season AS smallint
    CHECK (VALUE BETWEEN 1982 AND 2100);
COMMENT ON DOMAIN d_season IS '시즌: KBO 리그 출범(1982) 이후 연도';

CREATE DOMAIN d_inning AS smallint
    CHECK (VALUE BETWEEN 1 AND 18);
COMMENT ON DOMAIN d_inning IS '이닝: 1~18 (kbodata가 18회까지 지원)';

-- 수량 ----------------------------------------------------------------
CREATE DOMAIN d_count AS smallint
    CHECK (VALUE >= 0);
COMMENT ON DOMAIN d_count IS '경기 단위 횟수: 0 이상 정수 (타수, 안타, 삼진 등)';

CREATE DOMAIN d_total AS integer
    CHECK (VALUE >= 0);
COMMENT ON DOMAIN d_total IS '시즌 누적 횟수: 0 이상 정수';

CREATE DOMAIN d_outs AS integer
    CHECK (VALUE >= 0);
COMMENT ON DOMAIN d_outs IS '아웃카운트: 투수 이닝을 아웃 수로 저장 (6⅓이닝 = 19)';

-- 비율 ----------------------------------------------------------------
CREATE DOMAIN d_rate AS numeric(4,3)
    CHECK (VALUE BETWEEN 0 AND 1);
COMMENT ON DOMAIN d_rate IS '비율(0~1): 타율, 출루율, 승률 등 소수 셋째 자리';

CREATE DOMAIN d_slg AS numeric(5,3)
    CHECK (VALUE BETWEEN 0 AND 5);
COMMENT ON DOMAIN d_slg IS '장타 비율: 장타율(최대 4.000), OPS(최대 5.000)';

CREATE DOMAIN d_era AS numeric(6,2)
    CHECK (VALUE >= 0);
COMMENT ON DOMAIN d_era IS '투수 비율 지표: 평균자책점, WHIP 등 소수 둘째 자리';

-- 코드·명칭 -----------------------------------------------------------
CREATE DOMAIN d_hand AS char(1)
    CHECK (VALUE IN ('L', 'R', 'S'));
COMMENT ON DOMAIN d_hand IS '투타 방향: L 좌, R 우, S 양(스위치히터, 타격에만 사용)';

CREATE DOMAIN d_person_name AS varchar(30)
    CHECK (length(btrim(VALUE)) > 0);
COMMENT ON DOMAIN d_person_name IS '인명: 공백만으로 된 값 금지';
