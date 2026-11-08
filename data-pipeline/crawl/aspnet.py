"""ASP.NET WebForms 포스트백 도우미 (KBO 기록실 페이지용)

KBO 기록실은 시즌·팀 선택, 정렬, 페이지 이동을 __doPostBack 으로 처리한다.
브라우저가 하는 일을 그대로 흉내 낸다:
  1. 페이지의 모든 hidden input + select(선택값) + text input 값을 모은다
     (__VIEWSTATE, __EVENTVALIDATION 등 하나라도 빠지면 서버가 에러 페이지를 준다)
  2. 바꿀 값(시즌, 팀, 정렬 기준, 페이지 번호)을 덮어쓰고
  3. __EVENTTARGET 에 "어떤 컨트롤이 이벤트를 일으켰는지"를 넣어 POST 한다.

컨트롤 이름은 'ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ddlSeason$ddlSeason'
처럼 길고 페이지마다 접두어가 다를 수 있어서, 끝부분(접미어)으로 찾는다.
근거: 공개 크롤러 kbo-data-portal/collector(scrapers/player.py), icedo724/kbo-bayes(collect/fetch.py)
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from crawl.common import PoliteSession


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def form_fields(html: str) -> dict[str, str]:
    """브라우저가 POST 할 폼 값 (submit/button/체크 안 된 checkbox 제외)"""
    soup = soup_of(html)
    form = soup.find("form") or soup
    fields: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        typ = (inp.get("type") or "text").lower()
        if not name or typ in ("submit", "button", "image", "reset", "file"):
            continue
        if typ in ("checkbox", "radio") and not inp.has_attr("checked"):
            continue
        fields[name] = inp.get("value", "")
    for sel in form.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        opt = sel.find("option", selected=True) or sel.find("option")
        fields[name] = opt.get("value", opt.get_text(strip=True)) if opt else ""
    return fields


_POSTBACK_RE = re.compile(r"__doPostBack\(\s*['\"]([^'\"]+)['\"]")


def postback_targets(html: str) -> list[str]:
    """페이지 안의 __doPostBack('이름', ...) 호출에 나오는 컨트롤 이름들 (링크 버튼, 페이지 번호 등)"""
    return list(dict.fromkeys(_POSTBACK_RE.findall(html)))


def find_name(fields_or_html: dict | str, suffix: str) -> str | None:
    """접미어로 컨트롤 전체 이름 찾기. 예: find_name(fields, 'ddlSeason$ddlSeason')

    HTML을 주면 input/select 이름과 __doPostBack 대상 이름을 모두 뒤진다.
    그래도 없으면 같은 페이지 다른 컨트롤의 공통 접두어(ctl00$...$cphContents$)를 붙여 추정한다."""
    if isinstance(fields_or_html, str):
        soup = soup_of(fields_or_html)
        names = [t.get("name") for t in soup.find_all(["input", "select"]) if t.get("name")]
        names += postback_targets(fields_or_html)
    else:
        names = list(fields_or_html)
    hits = [n for n in names if n and n.endswith(suffix)]
    if hits:
        return min(hits, key=len)
    if isinstance(fields_or_html, str):
        prefix = guess_prefix(names)
        if prefix:
            return prefix + suffix
    return None


def guess_prefix(names: list[str]) -> str | None:
    for n in names:
        if n and "cphContents$" in n:
            return n[: n.rindex("cphContents$") + len("cphContents$")]
    return None


def select_options(html: str, suffix: str) -> list[tuple[str, str]]:
    """select 의 (value, 표시 글자) 목록"""
    soup = soup_of(html)
    for sel in soup.find_all("select"):
        if (sel.get("name") or "").endswith(suffix):
            return [(o.get("value", ""), o.get_text(strip=True)) for o in sel.find_all("option")]
    return []


def selected_value(html: str, suffix: str) -> str | None:
    soup = soup_of(html)
    for sel in soup.find_all("select"):
        if (sel.get("name") or "").endswith(suffix):
            opt = sel.find("option", selected=True) or sel.find("option")
            return opt.get("value") if opt else None
    return None


def looks_like_error_page(html: str) -> bool:
    soup = soup_of(html)
    title = soup.title.get_text(strip=True) if soup.title else ""
    return (soup.find("form") is None
            or bool(re.search(r"에러|오류|error", title, re.I))
            or "Runtime Error" in html)


class PostbackClient:
    """한 페이지(URL)에 대해 GET → 포스트백을 이어 가는 클라이언트. 마지막 HTML을 기억한다."""

    def __init__(self, session: PoliteSession, path: str):
        self.session = session
        self.path = path
        self.html = ""

    def get(self) -> str:
        html = self.session.get(self.path).text
        if looks_like_error_page(html):
            raise RuntimeError(f"정상적인 폼 페이지가 아닙니다: {self.path}")
        self.html = html
        return self.html

    def postback(self, target_suffix: str | None, overrides_by_suffix: dict[str, str] | None = None,
                 extra: dict[str, str] | None = None) -> str:
        """target_suffix: 이벤트를 일으킨 컨트롤의 이름 접미어 (None 이면 __EVENTTARGET 비움, submit 버튼은 extra 로)"""
        if not self.html:
            self.get()
        fields = form_fields(self.html)
        for suffix, value in (overrides_by_suffix or {}).items():
            name = find_name(fields, suffix) or find_name(self.html, suffix)
            if name is None:
                raise KeyError(f"폼에서 컨트롤을 찾지 못함: *{suffix}")
            fields[name] = value
        if extra:
            for suffix, value in extra.items():
                fields[find_name(self.html, suffix) or suffix] = value
        target = ""
        if target_suffix:
            target = find_name(fields, target_suffix) or find_name(self.html, target_suffix)
            if target is None:
                raise KeyError(f"이벤트 대상 컨트롤을 찾지 못함: *{target_suffix}")
        fields["__EVENTTARGET"] = target
        fields["__EVENTARGUMENT"] = ""
        r = self.session.post(self.path, data=fields, headers={"Referer": self.session.base + self.path})
        if looks_like_error_page(r.text):
            raise RuntimeError(f"포스트백이 거부됨(에러 페이지): target={target_suffix}")
        self.html = r.text
        return self.html
