"""crawl/ KBO 파서·포스트백 테스트

여기 HTML은 공개 크롤러 코드에서 확인한 KBO 페이지 구조(요소 id, 컨트롤 이름, 표 열)를 흉내 낸
**가상 HTML**이다. 실제 페이지와 맞는지는 맥에서 crawl/probe_kbo.py 로 확인한다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawl.aspnet import PostbackClient, find_name, form_fields, select_options  # noqa: E402
from crawl.kbo_parsers import (HITTER_COLUMNS, PITCHER_COLUMNS, ip_to_outs, pager_pages, parse_gamelog_dates,  # noqa: E402
                               parse_money, parse_position, parse_profile, parse_record_table, parse_team_rank)

P = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$"


def record_page(rows, pages=(1, 2), season="2025", team=""):
    opts = "".join(f'<option value="{s}"{" selected" if str(s) == season else ""}>{s}</option>' for s in (2024, 2025))
    teams = "".join(f'<option value="{v}"{" selected" if v == team else ""}>{t}</option>'
                    for v, t in (("", "팀 선택"), ("OB", "두산"), ("WO", "키움")))
    pager = "".join(f"<a href=\"javascript:__doPostBack('{P}ucPager$btnNo{n}','')\">{n}</a>" for n in pages)
    trs = "".join(
        f'<tr><td>{i}</td><td><a href="/Record/Player/HitterDetail/Basic.aspx?playerId={pid}">{name}</a></td>'
        f"<td>{team_name}</td><td>{avg}</td><td>{g}</td><td>{pa}</td></tr>"
        for i, (pid, name, team_name, avg, g, pa) in enumerate(rows, 1))
    return f"""<html><head><title>KBO 기록실</title></head><body><form method="post" id="mainForm">
<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="VS{season}{team}" />
<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="EV" />
<input type="hidden" name="{P}hfOrderByCol" value="HRA_RT" />
<input type="hidden" name="{P}hfOrderBy" value="DESC" />
<select name="{P}ddlSeason$ddlSeason">{opts}</select>
<select name="{P}ddlSeries$ddlSeries"><option value="0" selected>KBO 정규시즌</option></select>
<select name="{P}ddlTeam$ddlTeam">{teams}</select>
<a href="javascript:sort('GAME_CN');">G</a>
<script>function sort(c){{__doPostBack('{P}lbtnOrderBy','');}}</script>
<div class="record_result"><table class="tData01 tt"><thead><tr>
<th>순위</th><th>선수명</th><th>팀명</th><th>AVG</th><th>G</th><th>PA</th></tr></thead>
<tbody>{trs}</tbody></table></div><div class="paging">{pager}</div>
{"x" * 3000}</form></body></html>"""


def test_record_table_and_pager():
    html = record_page([(76232, "가상선수갑", "두산", "0.333", "120", "480"),
                        (50705, "가상선수을", "두산", "0.250", "30", "60")])
    headers, rows = parse_record_table(html, HITTER_COLUMNS)
    assert headers == ["순위", "선수명", "팀명", "AVG", "G", "PA"]
    assert rows[0] == {"player_id": 76232, "detail_kind": "hitter", "name": "가상선수갑", "team_name": "두산",
                       "avg": "0.333", "games": "120", "plate_appearances": "480"}
    assert pager_pages(html) == [1, 2]
    assert select_options(html, "ddlTeam$ddlTeam")[1] == ("OB", "두산")
    assert find_name(html, "lbtnOrderBy") == P + "lbtnOrderBy"  # <script> 안 __doPostBack 에서 찾음
    assert find_name(form_fields(html), "ddlSeason$ddlSeason") == P + "ddlSeason$ddlSeason"


class FakeSession:
    """POST 된 폼을 기록하고, 정해진 순서대로 HTML을 돌려주는 가짜 세션"""
    base = "https://www.koreabaseball.com"
    count = 0

    def __init__(self, pages):
        self.pages = list(pages)
        self.posts = []

    def get(self, path):
        return type("R", (), {"text": self.pages.pop(0)})

    def post(self, path, data=None, headers=None):
        self.posts.append(dict(data))
        return type("R", (), {"text": self.pages.pop(0)})


def test_postback_sends_all_fields_and_overrides():
    html = record_page([(1, "가", "두산", "0.1", "1", "1")])
    fake = FakeSession([html, html])
    c = PostbackClient(fake, "/Record/Player/HitterBasic/Basic1.aspx")
    c.get()
    c.postback("lbtnOrderBy", {"hfOrderByCol": "GAME_CN", "ddlTeam$ddlTeam": "OB"})
    sent = fake.posts[0]
    assert sent["__EVENTTARGET"] == P + "lbtnOrderBy"
    assert sent["__VIEWSTATE"] == "VS2025" and sent["__EVENTVALIDATION"] == "EV"
    assert sent[P + "hfOrderByCol"] == "GAME_CN"
    assert sent[P + "ddlTeam$ddlTeam"] == "OB"
    assert sent[P + "ddlSeason$ddlSeason"] == "2025"  # 건드리지 않은 select 는 현재 선택값 그대로


def test_records_crawl_flow_with_fake_site(tmp_path, monkeypatch):
    """시즌 선택 → 팀 선택 → 경기수 정렬 → 2페이지까지 받고 CSV로 합치는 흐름"""
    import crawl.kbo_records as kr
    p1 = record_page([(100, "가상갑", "두산", "0.3", "10", "40")], pages=(1, 2), team="OB")
    p2 = record_page([(101, "가상을", "두산", "0.2", "3", "5")], pages=(1, 2), team="OB")
    fake = FakeSession([record_page([]), record_page([]), p1, p1, p2])
    monkeypatch.setattr(kr, "PoliteSession", lambda base: fake)
    monkeypatch.setattr(kr, "OUT_DIR", tmp_path / "records")
    monkeypatch.setattr(kr, "DATA", tmp_path)
    from etl.reference import Reference
    kr.crawl([2025], ["OB"], ["hitter"], ["basic1"], Reference.load())
    targets = [p["__EVENTTARGET"].split("$")[-1] for p in fake.posts]
    assert targets == ["ddlSeason", "ddlTeam", "lbtnOrderBy", "btnNo2"]
    assert fake.posts[2][P + "hfOrderByCol"] == "GAME_CN"
    counts = kr.merge()
    assert counts["player_season_team"] == 2
    lines = (tmp_path / "player_season_team.csv").read_text(encoding="utf-8").splitlines()
    assert lines[1].startswith("2025,OB,100,가상갑,1,0")


def test_profile_parsing():
    html = """<div class="player_basic"><ul>
<li><strong>선수명: </strong><span id="cphContents_cphContents_cphContents_playerProfile_lblName">가상선수</span></li>
<li><strong>등번호: </strong>No.<span id="cphContents_cphContents_cphContents_playerProfile_lblBackNo">48</span></li>
<li><strong>생년월일: </strong><span id="cphContents_cphContents_cphContents_playerProfile_lblBirthday">1998년 04월 07일</span></li>
<li><strong>포지션: </strong><span id="cphContents_cphContents_cphContents_playerProfile_lblPosition">투수(우투좌타)</span></li>
<li><strong>신장/체중: </strong><span id="cphContents_cphContents_cphContents_playerProfile_lblHeightWeight">190cm/86kg</span></li>
<li><strong>경력: </strong><span id="cphContents_cphContents_cphContents_playerProfile_lblCareer">가상초-가상중-가상고</span></li>
<li><strong>입단 계약금: </strong><span id="cphContents_cphContents_cphContents_playerProfile_lblPayment">7000만원</span></li>
<li><strong>연봉: </strong><span id="cphContents_cphContents_cphContents_playerProfile_lblSalary">2800만원</span></li>
<li><strong>지명순위: </strong><span id="cphContents_cphContents_cphContents_playerProfile_lblDraft">17 KIA 2차 4라운드 34순위</span></li>
<li><strong>입단년도: </strong><span id="cphContents_cphContents_cphContents_playerProfile_lblJoinInfo">19KIA</span></li>
</ul></div><h4 class="team">KIA 타이거즈</h4>"""
    p = parse_profile(html)
    assert p["player_name"] == "가상선수" and p["uniform_no"] == "48"
    assert p["birth_date"] == "1998-04-07"
    assert (p["position"], p["throws"], p["bats"]) == ("투수", "R", "L")
    assert (p["height_cm"], p["weight_kg"]) == (190, 86)
    assert p["signing_bonus_10k"] == 7000 and p["salary_10k_krw"] == 2800
    assert p["draft_year"] == 2017 and p["join_year"] == 2019
    assert p["is_retired"] is False
    retired = html.replace("playerProfile_", "ucPlayerProfile_")
    assert parse_profile(retired)["is_retired"] is True
    assert parse_profile("<html></html>") == {}


def test_value_parsers():
    assert parse_money("100000달러") == (None, 100000)
    assert parse_money("30만달러") == (None, 300000)
    assert parse_position("내야수(우투양타)") == ("내야수", "R", "S")
    assert ip_to_outs("144 1/3") == 433 and ip_to_outs("2/3") == 2
    assert PITCHER_COLUMNS["IP"] == "ip_text"


def test_team_rank_and_gamelog():
    rank = """<table class="tData"><thead><tr><th>순위</th><th>팀명</th><th>경기</th><th>승</th><th>패</th>
<th>무</th><th>승률</th><th>게임차</th><th>최근10경기</th><th>연속</th></tr></thead><tbody>
<tr><td>1</td><td>LG</td><td>144</td><td>85</td><td>56</td><td>3</td><td>0.603</td><td>0</td><td>6승0무4패</td><td>1패</td></tr>
</tbody></table>"""
    r = parse_team_rank(rank)
    assert r[0]["team_name"] == "LG" and r[0]["wins"] == "85" and r[0]["last10"] == "6승0무4패"
    daily = """<table><thead><tr><th>3월</th><th>상대</th></tr></thead><tbody>
<tr><td>03.22</td><td>KT</td></tr><tr><td>03.23</td><td>KT</td></tr></tbody></table>"""
    assert parse_gamelog_dates(daily, 2025) == ["2025-03-22", "2025-03-23"]
