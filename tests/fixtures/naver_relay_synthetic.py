"""가상 네이버 문자중계 JSON (실제 경기가 아님). tests/fixtures/make_synthetic.py 의 1번 가상 경기와 같은 팀·선수.

공개 코드에서 확인한 구조를 따른다: textRelays는 최신 블록이 앞, 블록 안 textOptions는 오래된 것이 앞.
일부러 넣은 상황
  - 같은 투구 재전송(pitchNum 중복) → 1개만 남아야 함
  - 타석 도중 대타 → 같은 타석, 카운트 유지
  - 반이닝 재전송(seqno 되감김) → 버려야 함
  - 트래킹(ptsOptions)이 없는 투구 → 좌표 NULL
"""


def st(ball=0, strike=0, out=0, batter="", pitcher="", home=0, away=0, base1=0):
    return {"ball": str(ball), "strike": str(strike), "out": str(out), "batter": batter, "pitcher": pitcher,
            "homeScore": str(home), "awayScore": str(away), "base1": str(base1), "base2": "0", "base3": "0"}


def pitch(seq, num, result, stuff, speed, pid, state, text=None):
    return {"seqno": seq, "type": 1, "text": text or f"{num}구", "pitchNum": num, "pitchResult": result,
            "stuff": stuff, "speed": str(speed), "ptsPitchId": pid, "currentGameState": state}


def pts(pid, x):
    return {"pitchId": pid, "crossPlateX": x, "crossPlateY": 0.7083, "topSz": 3.4, "bottomSz": 1.6,
            "x0": -1.8, "y0": 50.0, "z0": 5.6, "vx0": 5.0, "vy0": -130.0, "vz0": -6.0,
            "ax": -8.0, "ay": 26.0, "az": -15.0, "stance": "L"}


OB_B1, OB_B2, OB_B3, OB_P1 = "900101", "900102", "900103", "900111"
WO_B1, WO_P1 = "900201", "900211"

block_t1 = {"title": "1번타자 OB가상타자갑", "homeOrAway": "0", "textOptions": [
    {"seqno": 2, "type": 8, "text": "1번타자 OB가상타자갑", "currentGameState": st(batter=OB_B1, pitcher=WO_P1)},
    pitch(3, 1, "B", "직구", 145, "p1", st(1, 0, batter=OB_B1, pitcher=WO_P1)),
    pitch(4, 2, "T", "슬라이더", 132, "p2", st(1, 1, batter=OB_B1, pitcher=WO_P1)),
    pitch(5, 3, "H", "직구", 146, "p3", st(1, 1, batter=OB_B1, pitcher=WO_P1)),
    {"seqno": 6, "type": 13, "text": "OB가상타자갑 : 좌익수 앞 1루타",
     "currentGameState": st(batter=OB_B1, pitcher=WO_P1, base1=1)},
], "ptsOptions": [pts("p1", -0.9), pts("p2", 0.2), pts("p3", 0.1)]}

block_t2 = {"title": "2번타자 OB가상타자을", "homeOrAway": "0", "textOptions": [
    {"seqno": 7, "type": 8, "text": "2번타자 OB가상타자을", "currentGameState": st(batter=OB_B2, pitcher=WO_P1)},
    pitch(8, 1, "S", "포크", 130, "p4", st(0, 1, batter=OB_B2, pitcher=WO_P1)),
    pitch(9, 1, "S", "포크", 130, "p4", st(0, 1, batter=OB_B2, pitcher=WO_P1)),  # 재전송
    {"seqno": 10, "type": 2, "text": "대타 OB가상타자병", "currentGameState": st(0, 1, batter=OB_B2, pitcher=WO_P1)},
    {"seqno": 11, "type": 8, "text": "대타 OB가상타자병", "currentGameState": st(0, 1, batter=OB_B3, pitcher=WO_P1)},
    pitch(12, 2, "B", "직구", 144, "p5", st(1, 1, batter=OB_B3, pitcher=WO_P1)),
    {"seqno": 13, "type": 23, "text": "OB가상타자병 : 우익수 뒤 2루타",
     "currentGameState": st(batter=OB_B3, pitcher=WO_P1, away=1)},
    {"seqno": 14, "type": 24, "text": "1루주자 OB가상타자갑 : 홈인", "currentGameState": st(away=1)},
], "ptsOptions": [pts("p4", 0.5), pts("p5", -0.3)]}

resent = {**block_t1, "title": "재전송된 블록"}  # seqno 2부터 다시 → 버려야 함

block_b1 = {"title": "1번타자 WO가상타자갑", "homeOrAway": "1", "textOptions": [
    {"seqno": 20, "type": 8, "text": "1번타자 WO가상타자갑", "currentGameState": st(batter=WO_B1, pitcher=OB_P1, away=1)},
    pitch(21, 1, "F", "커브", 120, "q1", st(0, 1, batter=WO_B1, pitcher=OB_P1, away=1)),
    pitch(22, 2, "B", "직구", 147, "q2", st(1, 1, batter=WO_B1, pitcher=OB_P1, away=1)),
    {"seqno": 23, "type": 13, "text": "WO가상타자갑 : 유격수 땅볼 아웃",
     "currentGameState": st(out=1, batter=WO_B1, pitcher=OB_P1, away=1)},
], "ptsOptions": [pts("q1", 0.0)]}

LINEUPS = {
    "homeLineup": {"batter": [{"pcode": WO_B1, "name": "WO가상타자갑", "batOrder": 1, "seqno": 1}],
                   "pitcher": [{"pcode": WO_P1, "name": "WO가상투수갑"}]},
    "awayLineup": {"batter": [{"pcode": OB_B1, "name": "OB가상타자갑", "batOrder": 1, "seqno": 1},
                              {"pcode": OB_B2, "name": "OB가상타자을", "batOrder": 2, "seqno": 1},
                              {"pcode": OB_B3, "name": "OB가상타자병", "batOrder": 2, "seqno": 2}],
                   "pitcher": [{"pcode": OB_P1, "name": "OB가상투수갑"}]},
}

INNINGS = {1: {"inn": 1, "textRelays": [block_b1, resent, block_t2, block_t1], **LINEUPS}}

SCHEDULE_GAME = {"gameId": "20250101OBWO02025", "gameDate": "2025-01-01", "homeTeamCode": "WO",
                 "awayTeamCode": "OB", "statusInfo": "9회말", "roundCode": "kbo_r", "cancel": False}
