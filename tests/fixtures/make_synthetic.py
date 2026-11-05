"""테스트용 **가상** 데이터 생성기 (실제 KBO 경기·선수가 아님)

- 1월 1~3일(실제 KBO 경기가 없는 날짜), 선수 ID 900000번대, 이름은 '가상'을 붙여서
  실제 데이터와 섞일 수 없게 했다.
- 세 경기를 kbodata의 세 가지 저장 형식으로 만든다.
    1) 20250101_OBWO0 : kbodata 0.2.3 변환 후 형식 (결정 없는 투수도 'L' → 버그 재현)
    2) 20250102_OBWO0 : 변환 후 형식 + crawl/kbodata_patch.py 적용 (결정 없으면 '', 타순 bat_order 포함)
    3) 20250103_WOOB0 : 변환 전 원본 형식(한글 키), 12회 무승부
- 크롤링 결과 CSV(선수 목록·상세·기록실·순위)도 같은 가상 선수로 만든다.

실행: python tests/fixtures/make_synthetic.py  → tests/fixtures/synthetic/ 에 파일 생성
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "synthetic"

PLAYERS = [  # player_id, team, name, is_batter, is_pitcher
    (900101, "OB", "OB가상타자갑", 1, 0), (900102, "OB", "OB가상타자을", 1, 0), (900103, "OB", "OB가상타자병", 1, 0),
    (900111, "OB", "OB가상투수갑", 0, 1), (900112, "OB", "OB가상투수을", 0, 1), (900113, "OB", "OB가상투수병", 0, 1),
    (900201, "WO", "WO가상타자갑", 1, 0), (900202, "WO", "WO가상타자을", 1, 0), (900203, "WO", "WO가상타자병", 1, 0),
    (900211, "WO", "WO가상투수갑", 0, 1), (900212, "WO", "WO가상투수을", 0, 1),
]


def innings(**cells):
    """i_1 ~ i_18 채우기 (없는 이닝은 '-')"""
    return {f"i_{i}": cells.get(f"i{i}", "-") for i in range(1, 19)}


def board(team, result, runs_by_inning, r, h, e, b, extra):
    row = {"idx": "x", "team": team, "result": result}
    row.update({f"i_{i}": (runs_by_inning[i - 1] if i <= len(runs_by_inning) else "-") for i in range(1, 19)})
    row.update({"r": r, "h": h, "e": e, "b": b, **extra})
    return row


def batter(name, team, pos, ab, h, rbi, r, **cells):
    return {"idx": "x", "name": name, "team": team, "position": pos, **innings(**cells),
            "hit": h, "bat_num": ab, "hit_get": rbi, "own_get": r}


def pitcher(name, team, starter, inning, result, so, bb, r, er, np, h, hr, ab, bf):
    return {"idx": "x", "name": name, "team": team, "mound": "1" if starter else "0", "inning": inning,
            "result": result, "strikeout": so, "dead4ball": bb, "losescore": r, "earnedrun": er,
            "pitchnum": np, "hitted": h, "homerun": hr, "battednum": ab, "batternum": bf}


def game1():
    etc = {"결승타": "OB가상타자갑(4회 1사 1루서 좌월 홈런)",
           "홈런": ["OB가상타자갑1호(4회2점 WO가상투수갑", "WO가상타자을1호(1회2점 OB가상투수갑)"],
           "2루타": "OB가상타자을(4회)", "도루": "WO가상타자갑(6회)", "실책": "OB가상타자을(5회)",
           "심판": ["가상심판갑", "가상심판을", "가상심판병", "가상심판정"],
           "구장": "고척", "관중": "12,345", "개시": "14:00", "종료": "17:05", "경기시간": "3:05"}
    extra = {"year": 2025, "month": 1, "day": 1, "week": 2, "home": "키움", "away": "두산", "dbheader": 0,
             "place": "고척", "audience": 12345, "starttime": "14:00", "endtime": "17:05", "gametime": "3:05"}
    return {"id": "20250101_OBWO0", "contents": {
        "scoreboard": [board("두산", 1, [0, 1, 0, 2, 0, 0, 0, 0, 0], 3, 4, 1, 2, extra),
                       board("키움", -1, [2, 0, 0, 0, 0, 0, 0, 0, 0], 2, 2, 0, 2, extra)],
        "ETC_info": etc,
        "away_batter": [
            batter("OB가상타자갑", "두산", "8", 3, 2, 2, 1, i1="1019", i4="1303", i7="2000"),
            batter("OB가상타자을", "두산", "6", 2, 1, 0, 1, i1="7104", i4="1116", i8="3000"),
            batter("OB가상타자병", "두산", "D", 2, 1, 1, 1, i2="5005", i5="10137000"),
        ],
        "home_batter": [
            batter("WO가상타자갑", "키움", "4", 2, 1, 0, 1, i1="1021", i3="2100", i6="3100"),
            batter("WO가상타자을", "키움", "2", 2, 1, 2, 1, i1="1300", i3="7212", i6="4101"),
            batter("WO가상타자병", "키움", "H9", 1, 0, 0, 0, i9="7400"),
        ],
        "away_pitcher": [
            pitcher("OB가상투수갑", "두산", True, "60", "W", 5, 1, 2, 2, 95, 2, 1, 19, 22),
            pitcher("OB가상투수을", "두산", False, "30", "S", 3, 1, 0, 0, 40, 0, 0, 9, 10),
        ],
        "home_pitcher": [
            pitcher("WO가상투수갑", "키움", True, "52", "L", 6, 1, 3, 3, 101, 4, 1, 21, 24),
            pitcher("WO가상투수을", "키움", False, "31", "L", 2, 1, 0, 0, 38, 0, 0, 11, 12),  # 버그: 결정 없음인데 L
        ],
    }}


def game2():
    etc = {"결승타": "OB가상타자갑(9회 솔로 홈런)", "홈런": "OB가상타자갑2호(9회1점 WO가상투수갑)",
           "2루타": "WO가상타자갑(9회)", "실책": "OB가상투수갑(1회)",
           "심판": ["가상심판을", "가상심판병", "가상심판정", "가상심판무"],
           "구장": "고척", "관중": "0", "개시": "18:30", "종료": "20:58", "경기시간": "2:28"}
    extra = {"place": "고척"}
    away_b = [batter("OB가상타자갑", "두산", "8", 2, 2, 1, 1, i1="1019", i9="1303"),
              batter("OB가상타자을", "두산", "6", 1, 0, 0, 0, i1="7104", i9="3200")]
    home_b = [batter("WO가상타자갑", "키움", "4", 2, 1, 0, 0, i1="2000", i9="1114"),
              batter("WO가상타자을", "키움", "2", 2, 0, 0, 0, i1="6000", i9="7300")]
    for i, b in enumerate(away_b, 1):
        b["bat_order"] = i
    for i, b in enumerate(home_b, 1):
        b["bat_order"] = i
    return {"id": "20250102_OBWO0", "contents": {
        "scoreboard": [board("두산", 1, [0] * 8 + [1], 1, 2, 1, 1, extra),
                       board("키움", -1, [0] * 9, 0, 1, 0, 0, extra)],
        "ETC_info": etc, "away_batter": away_b, "home_batter": home_b,
        "away_pitcher": [
            pitcher("OB가상투수갑", "두산", True, "70", "W", 7, 0, 0, 0, 92, 1, 0, 23, 24),
            pitcher("OB가상투수병", "두산", False, "10", "H", 1, 0, 0, 0, 12, 0, 0, 3, 3),
            pitcher("OB가상투수을", "두산", False, "10", "S", 2, 0, 0, 0, 14, 0, 0, 3, 3),
        ],
        "home_pitcher": [
            pitcher("WO가상투수갑", "키움", True, "90", "L", 8, 1, 1, 1, 110, 2, 1, 30, 31),
        ],
    }}


def game3_raw():
    """변환 전 원본(한글 키). WO 원정 @ OB 홈, 12회 2-2 무승부"""
    def sb(team, runs, R, H, E, B):
        row = {"팀": team, "승패": "무"}
        row.update({str(i): runs[i - 1] for i in range(1, 13)})
        row.update({"R": R, "H": H, "E": E, "B": B})
        return row

    def b(pos, name, team, ab, h, rbi, r, **cells):
        row = {"포지션": pos, "선수명": name}
        row.update({str(i): cells.get(f"i{i}", 0) for i in range(1, 13)})
        row.update({"타수": ab, "안타": h, "타점": rbi, "득점": r, "타율": "0.000", "팀": team})
        return row

    def p(name, team, start, result, ip, bf, np, ab, h, hr, bb, so, r, er):
        return {"선수명": name, "등판": "선발" if start else "구원", "결과": result, "승": 0, "패": 0, "세": 0,
                "이닝": ip, "타자": bf, "투구수": np, "타수": ab, "피안타": h, "홈런": hr, "4사구": bb,
                "삼진": so, "실점": r, "자책": er, "평균자책점": "0.00", "팀": team}

    etc = {"홈런": "WO가상타자을2호(2회2점 OB가상투수갑)", "도루": ["OB가상타자갑2(3 8회)"],
           "병살타": "WO가상타자갑(11회)", "보크": "가상외부인(5회)",
           "심판": ["가상심판갑", "가상심판병", "가상심판무", "가상심판기"],
           "구장": "잠실", "관중": "23,750", "개시": "17:00", "종료": "21:31", "경기시간": "4:31"}
    return {"id": "20250103_WOOB0", "contents": {
        "scoreboard": [sb("키움", [0, 2] + [0] * 10, 2, 3, 0, 1),
                       sb("두산", [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0], 2, 2, 1, 0)],
        "ETC_info": etc,
        "away_batter": [
            b("二", "WO가상타자갑", "키움", 5, 1, 0, 1, i1="좌안", i4="유땅", i7="삼진", i9="중비", i11="2병"),
            b("포", "WO가상타자을", "키움", 4, 2, 2, 1, i2="우중홈", i5="4구", i8="좌2", i10="삼진", i12="3땅"),
            b("타", "WO가상타자병", "키움", 1, 0, 0, 0, i12="1파"),
        ],
        "home_batter": [
            b("중", "OB가상타자갑", "두산", 5, 1, 1, 1, i1="중안/삼진", i3="삼진", i8="우희비", i10="유땅"),
            b("유", "OB가상타자을", "두산", 4, 1, 1, 1, i1="좌3", i4="2땅", i6="1희번", i9="삼진", i12="4구"),
        ],
        "away_pitcher": [
            p("WO가상투수갑", "키움", True, 0, "7", 27, 102, 25, 2, 0, 0, 9, 2, 2),
            p("WO가상투수을", "키움", False, 0, "5", 16, 58, 15, 0, 0, 1, 4, 0, 0),
        ],
        "home_pitcher": [
            p("OB가상투수갑", "두산", True, 0, "8 2/3", 33, 108, 31, 3, 1, 1, 6, 2, 2),
            p("OB가상투수병", "두산", False, 0, "1/3", 1, 4, 1, 0, 0, 0, 1, 0, 0),
            p("OB가상투수을", "두산", False, 0, "3", 10, 35, 9, 0, 0, 0, 2, 0, 0),
        ],
    }}


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    games = [game1(), game2(), game3_raw()]
    (OUT / "raw_games.json").write_text(json.dumps(games, ensure_ascii=False, indent=1), encoding="utf-8")

    data = OUT / "data"
    data.mkdir(exist_ok=True)
    write_csv(data / "player_season_team.csv", [
        {"season": 2025, "team_id": t, "player_id": pid, "name": n, "is_batter": ib, "is_pitcher": ip}
        for pid, t, n, ib, ip in PLAYERS])
    write_csv(data / "players.csv", [
        {"player_id": 900101, "player_name": "OB가상타자갑", "birth_date": "1999-04-07", "height_cm": 183,
         "weight_kg": 85, "throws": "R", "bats": "L", "position": "외야수", "career": "가상초-가상중-가상고",
         "draft_info": "18 두산 2차 1라운드 3순위", "draft_year": 2018, "join_info": "18두산", "join_year": 2018,
         "signing_bonus_10k": 15000, "uniform_no": "51", "team_id": "OB", "salary_season": 2025,
         "salary_text": "32000만원", "salary_10k_krw": 32000, "salary_usd": "", "is_retired": "false",
         "crawled_at": "2025-11-05T12:00:00+09:00"},
        {"player_id": 900211, "player_name": "WO가상투수갑", "birth_date": "1994-10-01", "height_cm": 191,
         "weight_kg": 95, "throws": "L", "bats": "L", "position": "투수", "career": "가상대학",
         "draft_info": "", "draft_year": "", "join_info": "25키움", "join_year": 2025,
         "signing_bonus_10k": "", "uniform_no": "40", "team_id": "WO", "salary_season": 2025,
         "salary_text": "800000달러", "salary_10k_krw": "", "salary_usd": 800000, "is_retired": "false",
         "crawled_at": "2025-11-05T12:00:00+09:00"},
    ])
    # 기록실 값: 일부러 한 선수(OB가상타자을)는 안타 1개를 다르게 → 비교 뷰가 불일치를 잡는지 확인
    write_csv(data / "season_batting.csv", [
        {"season": 2025, "team_id": "OB", "player_id": 900101, "name": "OB가상타자갑", "games": 3,
         "plate_appearances": 12, "at_bats": 10, "runs": 3, "hits": 5, "doubles": 0, "triples": 0, "home_runs": 2,
         "total_bases": 11, "rbi": 4, "sac_bunts": 0, "sac_flies": 1, "walks": 0, "intentional_walks": 0, "hbp": 0,
         "strikeouts": 3, "gidp": 0, "avg": 0.500, "obp": 0.455, "slg": 1.100, "ops": 1.555},
        {"season": 2025, "team_id": "OB", "player_id": 900102, "name": "OB가상타자을", "games": 3,
         "plate_appearances": 11, "at_bats": 7, "runs": 2, "hits": 4, "doubles": 1, "triples": 1, "home_runs": 0,
         "total_bases": 7, "rbi": 1, "sac_bunts": 1, "sac_flies": 0, "walks": 3, "intentional_walks": 1, "hbp": 0,
         "strikeouts": 1, "gidp": 0, "avg": 0.571, "obp": 0.700, "slg": 1.000, "ops": 1.700},
    ])
    write_csv(data / "season_pitching.csv", [
        {"season": 2025, "team_id": "WO", "player_id": 900211, "name": "WO가상투수갑", "games": 3, "wins": 0,
         "losses": 2, "saves": 0, "holds": 0, "outs_recorded": 65, "hits_allowed": 8, "home_runs_allowed": 2,
         "walks": 2, "hbp": 0, "strikeouts": 23, "runs_allowed": 6, "earned_runs": 6, "batters_faced": 82,
         "pitches": 313, "complete_games": 1, "shutouts": 0, "quality_starts": 2, "blown_saves": 0,
         "era": 2.49, "whip": 1.02},
    ])
    write_csv(data / "team_rank.csv", [
        {"season": 2025, "as_of_date": "2025-01-03", "rank": 1, "team_id": "OB", "team_name": "두산", "games": 3,
         "wins": 2, "losses": 0, "draws": 1, "win_pct": 1.000, "games_behind": 0.0, "last10": "2승1무0패",
         "streak": "1무"},
        {"season": 2025, "as_of_date": "2025-01-03", "rank": 2, "team_id": "WO", "team_name": "키움", "games": 3,
         "wins": 0, "losses": 2, "draws": 1, "win_pct": 0.000, "games_behind": 2.0, "last10": "0승1무2패",
         "streak": "1무"},
    ])
    print(f"가상 데이터 생성 → {OUT}")


if __name__ == "__main__":
    main()
