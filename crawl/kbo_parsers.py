"""KBO 공식 홈페이지 HTML 파서 (순수 함수, 네트워크 없음)

근거로 삼은 페이지 구조 (공개 크롤러 코드·저장 HTML에서 확인, 맥에서 crawl/probe_kbo.py 로 재확인 필요)
  - 기록실 표: <table class="tData ..."> 안 thead th = 열 이름, tbody tr = 선수 한 명,
    선수명 셀의 <a href="/Record/Player/HitterDetail/Basic.aspx?playerId=76232">
  - 선수 상세: <span id="...playerProfile_lblName">, lblBackNo, lblBirthday('1998년 04월 07일'),
    lblPosition('투수(우투우타)'), lblHeightWeight('190cm/86kg'), lblCareer, lblPayment('7000만원'),
    lblSalary('52000만원'), lblDraft('17 KIA 2차 4라운드 34순위'), lblJoinInfo('19KIA')
    은퇴 선수 페이지는 접두어가 ucPlayerProfile_ 일 수 있다.
  - 팀 순위: 순위, 팀명, 경기, 승, 패, 무, 승률, 게임차, 최근10경기, 연속 ...
  - 선수 일자별 기록(Daily.aspx): 월별 표, 첫 열 'MM.DD'
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

# 기록실 열 이름 → 저장 컬럼명 (DB 컬럼명과 같게)
HITTER_COLUMNS = {
    "선수명": "name", "팀명": "team_name", "AVG": "avg", "G": "games", "PA": "plate_appearances",
    "AB": "at_bats", "R": "runs", "H": "hits", "2B": "doubles", "3B": "triples", "HR": "home_runs",
    "TB": "total_bases", "RBI": "rbi", "SAC": "sac_bunts", "SF": "sac_flies", "BB": "walks",
    "IBB": "intentional_walks", "HBP": "hbp", "SO": "strikeouts", "GDP": "gidp", "SLG": "slg",
    "OBP": "obp", "OPS": "ops", "MH": "multi_hits", "RISP": "risp_avg", "PH-BA": "pinch_hit_avg",
}
PITCHER_COLUMNS = {
    "선수명": "name", "팀명": "team_name", "ERA": "era", "G": "games", "W": "wins", "L": "losses",
    "SV": "saves", "HLD": "holds", "WPCT": "win_pct", "IP": "ip_text", "H": "hits_allowed",
    "HR": "home_runs_allowed", "BB": "walks", "HBP": "hbp", "SO": "strikeouts", "R": "runs_allowed",
    "ER": "earned_runs", "WHIP": "whip", "CG": "complete_games", "SHO": "shutouts", "QS": "quality_starts",
    "BSV": "blown_saves", "TBF": "batters_faced", "NP": "pitches", "AVG": "opp_avg", "2B": "doubles_allowed",
    "3B": "triples_allowed", "SAC": "sac_bunts_allowed", "SF": "sac_flies_allowed", "IBB": "intentional_walks",
    "WP": "wild_pitches", "BK": "balks",
}
RANK_COLUMNS = {"순위": "rank", "팀명": "team_name", "경기": "games", "승": "wins", "패": "losses", "무": "draws",
                "승률": "win_pct", "게임차": "games_behind", "최근10경기": "last10", "연속": "streak",
                "홈": "home_record", "방문": "away_record"}


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def player_id_from_href(href: str | None) -> int | None:
    if not href:
        return None
    q = parse_qs(urlparse(href).query)
    v = q.get("playerId") or q.get("playerid")
    if v and v[0].isdigit():
        return int(v[0])
    m = re.search(r"playerId=(\d+)", href, re.I)
    return int(m.group(1)) if m else None


def find_data_table(soup: BeautifulSoup):
    """기록 표 찾기: class에 tData가 있는 표 → 없으면 playerId 링크가 가장 많은 표"""
    t = soup.select_one("table.tData") or soup.select_one("div.record_result table")
    if t is not None:
        return t
    tables = soup.find_all("table")
    if not tables:
        return None
    return max(tables, key=lambda x: len(x.select("a[href*=playerId]")))


def parse_record_table(html: str, column_map: dict[str, str]) -> tuple[list[str], list[dict]]:
    """기록실 표 → (원래 열 이름 목록, 행 목록). 각 행에 player_id 와 detail_kind(hitter/pitcher)를 붙인다."""
    soup = _soup(html)
    table = find_data_table(soup)
    if table is None:
        return [], []
    head_row = table.select_one("thead tr") or table.find("tr")
    headers = [_clean(th.get_text()) for th in head_row.find_all(["th", "td"])]
    body_rows = table.select("tbody tr") or table.find_all("tr")[1:]
    out = []
    for tr in body_rows:
        cells = tr.find_all("td")
        if len(cells) < 2 or "기록이 없습니다" in tr.get_text():
            continue
        a = tr.find("a", href=re.compile("playerId", re.I))
        row = {"player_id": player_id_from_href(a.get("href")) if a else None,
               "detail_kind": ("pitcher" if a and "Pitcher" in a.get("href", "") else "hitter") if a else None}
        for h, td in zip(headers, cells):
            key = column_map.get(h)
            if key:
                row[key] = _clean(td.get_text())
        if row["player_id"]:
            out.append(row)
    return headers, out


def pager_pages(html: str) -> list[int]:
    """페이지 번호 링크(ucPager$btnNoN)에서 보이는 페이지 번호들"""
    nums = {int(n) for n in re.findall(r"btnNo(\d+)", html)}
    return sorted(nums)


def has_next_block(html: str) -> bool:
    return bool(re.search(r"ucPager\$btnNext", html))


# ---------------------------------------------------------------------------
# 값 변환
# ---------------------------------------------------------------------------
def to_number(s: str | None):
    s = (s or "").strip().replace(",", "")
    if s in ("", "-"):
        return None
    try:
        return int(s) if re.fullmatch(r"-?\d+", s) else float(s)
    except ValueError:
        return None


def ip_to_outs(ip: str | None) -> int | None:
    """'144 1/3' → 433, '2/3' → 2, '9' → 27"""
    s = (ip or "").strip()
    if not s or s == "-":
        return None
    whole, frac = 0, 0
    for part in s.split():
        if "/" in part:
            frac = int(part.split("/")[0])
        else:
            whole = int(part)
    return whole * 3 + frac


def parse_birthday(s: str | None) -> str | None:
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s or "")
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None


def parse_position(s: str | None) -> tuple[str | None, str | None, str | None]:
    """'투수(우투우타)' → ('투수', 'R', 'R'), '내야수(우투양타)' → ('내야수', 'R', 'S')"""
    s = _clean(s or "")
    pos = s.split("(")[0].strip() or None
    hand = {"좌": "L", "우": "R", "양": "S"}
    m = re.search(r"([좌우양])투([좌우양])타", s)
    if not m:
        return pos, None, None
    throws = hand[m.group(1)] if m.group(1) != "양" else None
    return pos, throws, hand[m.group(2)]


def parse_height_weight(s: str | None) -> tuple[int | None, int | None]:
    m = re.search(r"(\d+)\s*cm\s*/\s*(\d+)\s*kg", s or "", re.I)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def parse_money(s: str | None) -> tuple[int | None, int | None]:
    """'52000만원' → (52000, None) / '1000000달러' → (None, 1000000) / '30만달러' → (None, 300000)"""
    s = _clean(s or "").replace(",", "")
    m = re.fullmatch(r"(\d+)\s*만\s*원", s)
    if m:
        return int(m.group(1)), None
    m = re.fullmatch(r"(\d+)\s*(만)?\s*달러", s)
    if m:
        return None, int(m.group(1)) * (10000 if m.group(2) else 1)
    m = re.fullmatch(r"(\d+)\s*원", s)
    if m:
        return int(m.group(1)) // 10000, None
    return None, None


def two_digit_year(s: str | None) -> int | None:
    """'17 KIA 2차 4라운드' → 2017, '19KIA' → 2019, '99LG' → 1999"""
    m = re.match(r"\s*(\d{2})", s or "")
    if not m:
        return None
    yy = int(m.group(1))
    return 2000 + yy if yy <= 60 else 1900 + yy


def parse_profile(html: str) -> dict:
    """선수 상세(현역·은퇴) 페이지 → 프로필 dict. 프로필 영역이 없으면 빈 dict"""
    soup = _soup(html)

    def lbl(name: str) -> str | None:
        el = soup.find(id=re.compile(rf"(player|Player)Profile_{name}$"))
        return _clean(el.get_text()) if el else None

    name = lbl("lblName")
    if not name:
        return {}
    pos, throws, bats = parse_position(lbl("lblPosition"))
    h, w = parse_height_weight(lbl("lblHeightWeight"))
    bonus_text, salary_text = lbl("lblPayment"), lbl("lblSalary")
    bonus_krw, _ = parse_money(bonus_text)
    sal_krw, sal_usd = parse_money(salary_text)
    draft, join = lbl("lblDraft"), lbl("lblJoinInfo")
    team_el = soup.select_one("h4.team") or soup.find(id=re.compile(r"h4Team$"))
    # 은퇴 여부는 HTML이 아니라 "은퇴 선수 페이지에서 받았는가"로 정한다(kbo_profiles.py).
    # ucPlayerProfile_ 접두어는 퓨처스 선수 페이지에서도 보여서 은퇴 표시로 쓸 수 없다.
    return {
        "player_name": name,
        "uniform_no": (lbl("lblBackNo") or "").replace("No.", "").strip() or None,
        "birth_date": parse_birthday(lbl("lblBirthday")),
        "position": pos if pos in ("투수", "포수", "내야수", "외야수") else None,
        "position_text": lbl("lblPosition"),
        "throws": throws, "bats": bats,
        "height_cm": h, "weight_kg": w,
        "career": lbl("lblCareer"),
        "signing_bonus_text": bonus_text, "signing_bonus_10k": bonus_krw,
        "salary_text": salary_text, "salary_10k_krw": sal_krw, "salary_usd": sal_usd,
        "draft_info": draft, "draft_year": two_digit_year(draft),
        "join_info": join, "join_year": two_digit_year(join),
        "team_name": _clean(team_el.get_text()) if team_el else None,
    }


def parse_team_rank(html: str) -> list[dict]:
    soup = _soup(html)
    for table in soup.find_all("table"):
        head = table.select_one("thead tr") or table.find("tr")
        headers = [_clean(th.get_text()) for th in head.find_all(["th", "td"])] if head else []
        if "팀명" not in headers or "승률" not in headers:
            continue
        out = []
        for tr in table.select("tbody tr") or table.find_all("tr")[1:]:
            cells = [_clean(td.get_text()) for td in tr.find_all("td")]
            if len(cells) < len(headers) // 2:
                continue
            out.append({RANK_COLUMNS[h]: v for h, v in zip(headers, cells) if h in RANK_COLUMNS})
        return out
    return []


def parse_gamelog_dates(html: str, year: int) -> list[str]:
    """Daily.aspx 월별 표의 'MM.DD' → 'YYYY-MM-DD' 목록"""
    soup = _soup(html)
    dates = []
    for td in soup.select("table tbody tr td:first-child"):
        m = re.fullmatch(r"(\d{2})\.(\d{2})", _clean(td.get_text()))
        if m:
            dates.append(f"{year}-{m.group(1)}-{m.group(2)}")
    return sorted(set(dates))
