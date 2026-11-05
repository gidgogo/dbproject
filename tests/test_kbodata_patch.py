"""crawl/kbodata_patch.py 테스트 — kbodata가 설치된 환경에서만 실행 (없으면 건너뜀)

KBO 박스스코어 리뷰 화면의 표 구성을 흉내 낸 가상 HTML 표로 kbodata 함수를 직접 돌린다.
  tables[4]  원정 타자(타순, 포지션, 선수명)   tables[5] 원정 이닝별 결과   tables[6] 원정 타수/안타/타점/득점
  tables[7~9] 홈 타자                         tables[10] 원정 투수        tables[11] 홈 투수
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "crawl"))
kbodata = pytest.importorskip("kbodata")
from bs4 import BeautifulSoup  # noqa: E402

import kbodata_patch  # noqa: E402


def _table(header, rows):
    th = "".join(f"<th>{h}</th>" for h in header)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def _tables():
    batter1 = _table(["", "", "선수명"], [["1", "중", "가상타자갑"], ["1", "타우", "가상타자을"], ["2", "유", "가상타자병"]])
    batter2 = _table(["1", "2"], [["좌안", ""], ["", "삼진"], ["유땅", ""], ["", ""]])
    batter3 = _table(["타수", "안타", "타점", "득점", "타율"], [[1, 1, 0, 0, ".300"], [1, 0, 0, 0, ".200"],
                                                         [1, 0, 0, 0, ".250"], [3, 1, 0, 0, ""]])
    pit_header = ["선수명", "등판", "결과", "승", "패", "세", "이닝", "타자", "투구수", "타수", "피안타", "홈런",
                  "4사구", "삼진", "실점", "자책", "평균자책점"]
    pit = _table(pit_header, [["가상투수갑", "선발", "승", 1, 0, 0, "5 1/3", 20, 80, 18, 3, 0, 1, 4, 1, 1, "1.69"],
                              ["가상투수을", "구원", "", 0, 0, 0, "2/3", 3, 12, 3, 0, 0, 0, 1, 0, 0, "0.00"],
                              ["TOTAL", "", "", "", "", "", "6", 23, 92, 21, 3, 0, 1, 5, 1, 1, ""]])
    html = "".join(["<table></table>"] * 4 + [batter1, batter2, batter3, batter1, batter2, batter3, pit, pit])
    return BeautifulSoup(html, "lxml").find_all("table")


def test_patch_fixes_result_and_keeps_batting_order():
    import kbodata.get.game as game_mod
    import kbodata.parser.page as page_mod
    import kbodata.parser.pitcher as pitcher_mod

    raw_before = pitcher_mod.change_result(0)
    assert raw_before == "L", "패치 전에는 결정 없음도 L (버그 재현)"

    kbodata_patch.apply()
    tables = _tables()
    teams = ("두산", "키움")
    data = {"id": "20250101_OBWO0", "contents": {
        "scoreboard": [], "ETC_info": {},
        "away_batter": page_mod.away_batter(tables, teams).to_dict("records"),
        "home_batter": page_mod.home_batter(tables, teams).to_dict("records"),
        "away_pitcher": [], "home_pitcher": [],
    }}
    out = game_mod.batter_modify(data)
    away = out["contents"]["away_batter"]
    assert [b["bat_order"] for b in away] == [1, 1, 2]
    assert [b["position"] for b in away] == ["8", "H9", "6"]
    assert away[0]["i_1"] == "1019" and away[1]["i_2"] == "2000"

    import json
    import pandas as pd
    pit_df = pd.read_html(__import__("io").StringIO(str(tables[10])))[0][:-1].fillna(0)
    pit_df["팀"] = "두산"
    pdata = {"id": "20250101_OBWO0", "contents": {"away_pitcher": json.loads(pit_df.to_json(orient="records")),
                                                  "home_pitcher": []}}
    pout = pitcher_mod.pitcher_modify(pdata)
    assert [p["result"] for p in pout["contents"]["away_pitcher"]] == ["W", ""]
    assert [p["inning"] for p in pout["contents"]["away_pitcher"]] == ["51", "02"]
