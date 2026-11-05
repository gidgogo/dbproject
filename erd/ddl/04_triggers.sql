-- =====================================================================
-- KBO 야구 기록 DB · 04. 트리거 (선언적 제약으로 표현하기 어려운 업무 규칙)
-- =====================================================================

-- 규칙 1. 팀경기기록의 (팀ID, 홈원정구분)은 경기의 홈팀·원정팀과 일치해야 한다.
--   home_away는 game에서 유도 가능한 값이지만 조회 편의를 위해 저장했다(의도적 중복).
--   대신 트리거로 불일치를 막아 "갱신 이상"이 생기지 않게 한다.
CREATE OR REPLACE FUNCTION fn_team_game_check_side() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    g game%ROWTYPE;
BEGIN
    SELECT * INTO g FROM game WHERE game_id = NEW.game_id;
    IF NOT FOUND THEN
        RETURN NEW;  -- FK 검사가 처리한다
    END IF;
    IF (NEW.home_away = 'H' AND NEW.team_id <> g.home_team_id)
       OR (NEW.home_away = 'A' AND NEW.team_id <> g.away_team_id) THEN
        RAISE EXCEPTION '팀경기기록 불일치: 경기 % 의 %팀은 % 인데 % 가 입력됨',
            NEW.game_id, CASE NEW.home_away WHEN 'H' THEN '홈' ELSE '원정' END,
            CASE NEW.home_away WHEN 'H' THEN g.home_team_id ELSE g.away_team_id END,
            NEW.team_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_team_game_check_side
    BEFORE INSERT OR UPDATE OF game_id, team_id, home_away ON team_game
    FOR EACH ROW EXECUTE FUNCTION fn_team_game_check_side();

-- 참고: 홈/원정팀만 바꾸는 UPDATE는 game의 ck_game_id_parts(경기ID 구성 검사)가 막는다.
--   경기ID까지 함께 바꾸면 ON UPDATE CASCADE로 team_game.game_id가 바뀌고,
--   그때 위 트리거가 다시 실행되어 팀이 맞지 않으면 거부한다.
