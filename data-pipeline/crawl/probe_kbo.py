"""KBO 홈페이지 구조 확인(probe) — 본격 수집 전에 맥에서 한 번 실행한다 (요청 약 12회, 1분 이내)

크롤러는 공개 오픈소스 코드에서 확인한 페이지 구조를 바탕으로 작성했다. 이 스크립트는
그 가정이 지금의 실제 페이지와 맞는지 하나씩 확인하고 결과를 문서로 남긴다.
  → docs/probe/kbo_probe_YYYYMMDD.md  (보고서 '수집한 업무 문서'의 근거로도 쓸 수 있음)
  → data/raw/probe/*.html               (받은 원본 HTML)

사용 예:
    python crawl/probe_kbo.py                    # 2025 시즌 기준
    python crawl/probe_kbo.py --season 2024 --retire-id 77147
"""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.aspnet import PostbackClient, form_fields, find_name, postback_targets, select_options, soup_of  # noqa: E402
from crawl.common import RAW, ROOT, PoliteSession, save_text, setup_logging  # noqa: E402
from crawl.kbo_parsers import (HITTER_COLUMNS, PITCHER_COLUMNS, pager_pages, parse_gamelog_dates,  # noqa: E402
                               parse_profile, parse_record_table, parse_team_rank)
from crawl.kbo_records import select_regular_season  # noqa: E402

BASE = "https://www.koreabaseball.com"


class Probe:
    def __init__(self, season: int):
        self.season = season
        self.session = PoliteSession(BASE)
        self.lines: list[str] = []
        self.checks: list[tuple[str, bool, str]] = []
        self.first_player: int | None = None

    def save(self, name: str, html: str) -> None:
        save_text(RAW / "probe" / f"{name}.html", html)

    def check(self, label: str, ok: bool, note: str = "") -> None:
        self.checks.append((label, ok, note))

    def section(self, title: str) -> None:
        self.lines += ["", f"## {title}", ""]

    def describe_form(self, html: str) -> None:
        fields = form_fields(html)
        hidden = [n.split("$")[-1] for n in fields if "$" in n or n.startswith("__")]
        self.lines.append(f"- 폼 필드({len(fields)}개): `{', '.join(hidden[:40])}`")
        soup = soup_of(html)
        for sel in soup.find_all("select"):
            opts = [(o.get("value", ""), o.get_text(strip=True)) for o in sel.find_all("option")]
            self.lines.append(f"- select `…{(sel.get('name') or '')[-40:]}` 옵션 {len(opts)}개: "
                              + ", ".join(f"{v}={t}" for v, t in opts[:14]) + (" …" if len(opts) > 14 else ""))
        targets = [t.split("$")[-1] for t in postback_targets(html)]
        self.lines.append(f"- __doPostBack 대상: `{', '.join(dict.fromkeys(targets))}`")

    def describe_table(self, html: str, colmap: dict) -> int:
        headers, rows = parse_record_table(html, colmap)
        self.lines.append(f"- 표 열: `{' | '.join(headers)}`")
        self.lines.append(f"- 선수 행 {len(rows)}개, 페이지 링크 {pager_pages(html)}")
        for r in rows[:3]:
            self.lines.append(f"  - {r}")
        unknown = [h for h in headers if h not in colmap and h != "순위"]
        if unknown:
            self.lines.append(f"- ⚠️ 매핑에 없는 열: {unknown}")
        return len(rows)

    # ------------------------------------------------------------------
    def run(self, retire_id: int | None) -> None:
        steps = [self.step_records, self.step_profile, self.step_pitcher, self.step_rank, self.step_daily]
        if retire_id:
            steps.append(lambda: self.step_retire(retire_id))
        for step in steps:
            try:
                step()
            except Exception as e:  # 한 단계가 실패해도 나머지는 확인한다
                self.lines += [f"- ❌ 오류: `{e}`", "```", traceback.format_exc()[-1500:], "```"]
                self.check(step.__name__ if hasattr(step, "__name__") else "step", False, str(e))

    def step_records(self) -> None:
        self.section("1. 타자 기록실 Basic1 (선수 목록·playerId)")
        c = PostbackClient(self.session, "/Record/Player/HitterBasic/Basic1.aspx")
        html = c.get()
        self.save("hitter_basic1_get", html)
        self.describe_form(html)
        n0 = self.describe_table(html, HITTER_COLUMNS)
        fields = form_fields(html)
        for suffix in ("ddlSeason$ddlSeason", "ddlTeam$ddlTeam", "ddlSeries$ddlSeries", "hfOrderByCol", "hfPage"):
            self.check(f"기록실 폼에 *{suffix} 존재", bool(find_name(fields, suffix)))
        self.check("기록 표(tData)와 playerId 링크", n0 > 0, f"{n0}행")

        self.lines.append(f"\n**시즌 {self.season} 선택 포스트백**")
        select_regular_season(c, self.season)
        html = c.html
        self.save("hitter_basic1_season", html)
        teams = [(v, t) for v, t in select_options(html, "ddlTeam$ddlTeam") if v]
        self.lines.append(f"- 팀 옵션: {teams}")
        self.check("시즌 포스트백 후 팀 목록", len(teams) >= 8, str(len(teams)))
        if not teams:
            return
        value, text = teams[0]
        self.lines.append(f"\n**팀 '{text}'({value}) 선택 → 기본 정렬**")
        html = c.postback("ddlTeam$ddlTeam", {"ddlSeason$ddlSeason": str(self.season), "ddlTeam$ddlTeam": value})
        self.save("hitter_basic1_team", html)
        n_default = self.describe_table(html, HITTER_COLUMNS)

        self.lines.append("\n**경기수(GAME_CN) 정렬 포스트백**")
        html = c.postback("lbtnOrderBy", {"hfOrderByCol": "GAME_CN", "hfOrderBy": "DESC"})
        self.save("hitter_basic1_team_sorted", html)
        n_sorted = self.describe_table(html, HITTER_COLUMNS)
        pages = pager_pages(html)
        self.check("경기수 정렬 시 선수가 같거나 많아짐(규정타석 해제)", n_sorted >= n_default,
                   f"기본 {n_default}행 → 정렬 {n_sorted}행, 페이지 {pages}")
        _, rows = parse_record_table(html, HITTER_COLUMNS)
        self.first_player = rows[0]["player_id"] if rows else None
        if 2 in pages:
            self.lines.append("\n**2페이지 (ucPager$btnNo2)**")
            html = c.postback("ucPager$btnNo2")
            self.save("hitter_basic1_team_p2", html)
            n2 = self.describe_table(html, HITTER_COLUMNS)
            _, rows2 = parse_record_table(html, HITTER_COLUMNS)
            new_ids = {r["player_id"] for r in rows2} - {r["player_id"] for r in rows}
            self.check("2페이지에 새 선수", bool(new_ids), f"{n2}행, 새 선수 {len(new_ids)}명")

    def step_profile(self) -> None:
        self.section("2. 선수 상세 (현역 타자)")
        if not self.first_player:
            self.lines.append("- 1단계에서 playerId를 못 얻어 건너뜀")
            return
        url = f"/Record/Player/HitterDetail/Basic.aspx?playerId={self.first_player}"
        html = self.session.get(url).text
        self.save("hitter_detail", html)
        ids = sorted({t.get("id").split("_")[-1] for t in soup_of(html).find_all(id=True)
                      if "Profile_lbl" in t.get("id", "")})
        self.lines += [f"- URL: {BASE}{url}", f"- 프로필 라벨 id: `{', '.join(ids)}`"]
        prof = parse_profile(html)
        self.lines.append(f"- 파싱 결과: {prof}")
        self.check("선수 상세 프로필 파싱(이름·생년월일)", bool(prof.get("player_name") and prof.get("birth_date")))
        self.check("투타·신장체중 파싱", bool(prof.get("bats") and prof.get("height_cm")))

    def step_pitcher(self) -> None:
        self.section("3. 투수 기록실 Basic1·Basic2 열 이름")
        for page in ("Basic1", "Basic2"):
            c = PostbackClient(self.session, f"/Record/Player/PitcherBasic/{page}.aspx")
            c.get()
            select_regular_season(c, self.season)
            html = c.html
            self.save(f"pitcher_{page.lower()}", html)
            self.lines.append(f"\n**{page}**")
            n = self.describe_table(html, PITCHER_COLUMNS)
            self.check(f"투수 {page} 표", n > 0)
        c = PostbackClient(self.session, "/Record/Player/HitterBasic/Basic2.aspx")
        c.get()
        select_regular_season(c, self.season)
        html = c.html
        self.save("hitter_basic2", html)
        self.lines.append("\n**타자 Basic2**")
        self.check("타자 Basic2 표", self.describe_table(html, HITTER_COLUMNS) > 0)

    def step_rank(self) -> None:
        self.section("4. 팀 순위")
        html = self.session.get("/Record/TeamRank/TeamRank.aspx").text
        self.save("team_rank", html)
        rows = parse_team_rank(html)
        self.lines.append(f"- TeamRank.aspx: {len(rows)}개 팀, 첫 행 {rows[:1]}")
        self.check("TeamRank.aspx 순위 표", len(rows) >= 8)
        c = PostbackClient(self.session, "/Record/TeamRank/TeamRankDaily.aspx")
        html = c.get()
        self.describe_form(html)
        ymd = f"{self.season}0801"
        extra = {"btnCalendarSelect": ""} if find_name(html, "btnCalendarSelect") else None
        html = c.postback(None, {"hfSearchDate": ymd}, extra=extra)
        self.save("team_rank_daily", html)
        rows = parse_team_rank(html)
        shown = form_fields(html).get(find_name(form_fields(html), "hfSearchDate") or "", "")
        self.lines.append(f"- TeamRankDaily {ymd} 요청 → 표시 기준일 {shown}, {len(rows)}개 팀, 첫 행 {rows[:1]}")
        self.check("TeamRankDaily 날짜 지정", len(rows) >= 8 and shown == ymd, f"표시 {shown}")

    def step_daily(self) -> None:
        self.section("5. 선수 일자별 기록 (동명이인 구분용)")
        if not self.first_player:
            return
        html = self.session.get(f"/Record/Player/HitterDetail/Daily.aspx?playerId={self.first_player}").text
        self.save("hitter_daily", html)
        self.describe_form(html)
        dates = parse_gamelog_dates(html, self.season)
        self.lines.append(f"- 출전 일자 {len(dates)}개: {dates[:5]} …")
        self.check("일자별 기록 날짜(MM.DD)", len(dates) > 0)

    def step_retire(self, pid: int) -> None:
        self.section("6. 은퇴 선수 페이지")
        html = self.session.get(f"/Record/Retire/Hitter.aspx?playerId={pid}").text
        self.save("retire_hitter", html)
        prof = parse_profile(html)
        self.lines.append(f"- 파싱 결과: {prof}")
        self.check("은퇴 선수 프로필", bool(prof.get("player_name")))

    def report(self) -> str:
        head = [f"# KBO 홈페이지 구조 확인 결과 ({date.today().isoformat()})", "",
                f"- 대상 시즌: {self.season}, 요청 수: {self.session.count}",
                "- 생성: `python crawl/probe_kbo.py` (원본 HTML: data/raw/probe/)", "",
                "## 가정 확인 요약", "", "| 확인 항목 | 결과 | 비고 |", "|---|:---:|---|"]
        head += [f"| {label} | {'✅' if ok else '❌'} | {note} |" for label, ok, note in self.checks]
        return "\n".join(head + self.lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--retire-id", type=int, help="은퇴 선수 playerId (선택)")
    args = ap.parse_args(argv)
    setup_logging()
    p = Probe(args.season)
    p.run(args.retire_id)
    out = ROOT.parent / "docs" / "probe" / f"kbo_probe_{date.today():%Y%m%d}.md"  # 레포 최상위 docs/
    save_text(out, p.report())
    bad = [c for c in p.checks if not c[1]]
    print(f"결과: {out}  (확인 {len(p.checks)}개 중 실패 {len(bad)}개)")
    for label, _, note in bad:
        print(f"  ❌ {label} {note}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
