"""kbodata(0.2.2 / 0.2.3) 보정 패치 — 수집 스크립트(kbo_fetch.py) 맨 위에서 apply() 한 번 호출

kbodata 소스를 읽다가 발견한 두 가지 문제를 고친다. kbodata 파일 자체는 건드리지 않고,
실행 중에 함수만 바꿔 끼운다(monkey patch).

1) 투수 결과(승/패/세/홀) 오류
   kbodata.parser.pitcher.change_result 는 '세이브'·'홀드'·'승'이 아니면 전부 'L'을 돌려준다.
   결정이 없는 투수(빈 칸 → 0)도 'L'(패전)이 되어 시즌 패 수가 크게 부풀려진다.
   → 승 W, 패 L, 세/세이브 S, 홀드 H, 그 외는 '' 로 바꾼다.

2) 타순 누락
   kbodata.parser.html.away_batter/home_batter 는 박스스코어 첫 열(타순, 'Unnamed: 0')을 지운다.
   → '타순'으로 남겨 두고, batter_modify 결과의 각 타자에 bat_order(1~9)를 붙인다.
   (❓ 첫 열이 정말 타순인지 2025-06-01 테스트 데이터로 확인할 것: 값이 1~9 이고 선발 순서대로면 맞음)

사용법 (kbo_fetch.py 맨 위, import kbodata 보다 먼저 또는 바로 뒤):
    import sys; sys.path.insert(0, "/Users/<맥 사용자명>/Desktop/프로젝트/crawl")   # 이 파일이 있는 폴더
    import kbodata_patch; kbodata_patch.apply()

적용 여부 확인: python crawl/kbodata_patch.py  → "패치 적용됨" 출력
"""
from __future__ import annotations

import logging

log = logging.getLogger("kbodata_patch")
_APPLIED = False

DECISIONS = {"승": "W", "패": "L", "세": "S", "세이브": "S", "홀드": "H", "홀": "H"}


def change_result_fixed(result) -> str:
    return DECISIONS.get(str(result).strip(), "")


def _to_order(v):
    try:
        n = int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 9 else None


def apply() -> None:
    """kbodata 함수 교체. 여러 번 불러도 한 번만 적용된다."""
    global _APPLIED
    if _APPLIED:
        return
    import kbodata
    import kbodata.get.game as game_mod
    import kbodata.parser.html as html_mod
    import kbodata.parser.page as page_mod
    import kbodata.parser.pitcher as pitcher_mod
    import pandas as pd

    if getattr(kbodata, "__version__", "") not in ("0.2.2", "0.2.3"):
        log.warning("kbodata %s 버전은 패치를 확인하지 않았습니다(0.2.2/0.2.3 기준)", kbodata.__version__)

    # 1) 투수 결과 ------------------------------------------------------------
    pitcher_mod.change_result = change_result_fixed  # pitcher_modify 가 모듈 전역에서 찾으므로 이걸로 충분

    # 2) 타순 -----------------------------------------------------------------
    read_html = html_mod._read_html

    def _batter(tables, team, idx: int, side: int):
        t1 = read_html(str(tables[idx])).dropna()
        t1 = t1.rename(columns={"Unnamed: 1": "포지션", "Unnamed: 0": "타순"})
        t2 = read_html(str(tables[idx + 1]))[:-1]
        t3 = read_html(str(tables[idx + 2]))[:-1]
        df = pd.concat([t1, t2, t3], axis=1)
        df["팀"] = team[side]
        return df.fillna(0)

    def away_batter(tables, team):
        return _batter(tables, team, 4, 0)

    def home_batter(tables, team):
        return _batter(tables, team, 7, 1)

    for mod in (html_mod, page_mod):  # page.py 는 from ... import 로 이름을 따로 가지고 있다
        mod.away_batter = away_batter
        mod.home_batter = home_batter

    original_batter_modify = game_mod.batter_modify

    def batter_modify_with_order(data):
        orders = {k: [_to_order(r.get("타순")) for r in data["contents"].get(k, [])]
                  for k in ("away_batter", "home_batter")}
        out = original_batter_modify(data)
        for k, lst in orders.items():
            for row, order in zip(out["contents"].get(k, []), lst):
                row["bat_order"] = order
        return out

    game_mod.batter_modify = batter_modify_with_order
    _APPLIED = True
    log.info("kbodata 패치 적용됨 (투수 결과, 타순)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    apply()
    import kbodata.parser.pitcher as p
    print("패치 적용됨:", p.change_result(0) == "" and p.change_result("승") == "W")
