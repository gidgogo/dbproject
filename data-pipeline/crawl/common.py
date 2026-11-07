"""크롤러 공통 도구: 예의 바른 HTTP 세션, 원본 저장, 이어받기 체크포인트, CSV 병합

크롤링 예의(작업지시서 0장)
  - 요청 사이 1~2초 간격 (REQUEST_DELAY 범위에서 무작위)
  - 시즌·팀 단위로 나눠 받고, 끝난 단위는 체크포인트에 기록 → 중간에 끊겨도 이어받기
  - User-Agent에 개인정보(이메일 등)를 넣지 않는다. 기본값은 일반 브라우저 문자열이고
    환경변수 KBO_CRAWL_UA 로 바꿀 수 있다.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Iterable

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"

REQUEST_DELAY = (1.0, 2.0)  # 초
TIMEOUT = 20
DEFAULT_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

log = logging.getLogger("crawl")


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")


class PoliteSession:
    """요청마다 1~2초 쉬고, 네트워크 오류·5xx는 지수 백오프로 최대 4번 다시 시도한다."""

    def __init__(self, base: str = "", headers: dict | None = None,
                 delay: tuple[float, float] = REQUEST_DELAY, retries: int = 4):
        self.base = base
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": os.environ.get("KBO_CRAWL_UA", DEFAULT_UA),
                               "Accept-Language": "ko-KR,ko;q=0.9"})
        if headers:
            self.s.headers.update(headers)
        self.delay = delay
        self.retries = retries
        self._last = 0.0
        self.count = 0

    def _wait(self) -> None:
        gap = random.uniform(*self.delay)
        elapsed = time.monotonic() - self._last
        if elapsed < gap:
            time.sleep(gap - elapsed)

    def request(self, method: str, url: str, **kw) -> requests.Response:
        full = url if url.startswith("http") else self.base + url
        kw.setdefault("timeout", TIMEOUT)
        for attempt in range(self.retries + 1):
            self._wait()
            try:
                r = self.s.request(method, full, **kw)
                self._last = time.monotonic()
                self.count += 1
                if r.status_code >= 500 or r.status_code == 429:
                    raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
                r.raise_for_status()
                # KBO 오류 페이지는 charset 헤더 없이 UTF-8 HTML을 주기도 한다.
                # requests의 ISO-8859-1 기본값으로 읽으면 에러 문구가 깨진다.
                if "text/html" in r.headers.get("Content-Type", "") and "charset=" not in r.headers.get("Content-Type", "").lower():
                    r.encoding = "utf-8"
                return r
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                self._last = time.monotonic()
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status is not None and status < 500 and status != 429:
                    raise
                if attempt == self.retries:
                    raise
                wait = 2 ** (attempt + 1)
                log.warning("요청 실패(%s) %s → %d초 후 재시도", e, full, wait)
                time.sleep(wait)
        raise RuntimeError("unreachable")

    def get(self, url: str, **kw) -> requests.Response:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw) -> requests.Response:
        return self.request("POST", url, **kw)


# ---------------------------------------------------------------------------
# 원본 저장 / 체크포인트
# ---------------------------------------------------------------------------
def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)  # 원자적 교체: 중간에 끊겨도 반쪽 파일이 남지 않음


class Checkpoint:
    """끝난 작업 단위(문자열 키)를 JSON 파일에 기록한다."""

    def __init__(self, path: Path):
        self.path = path
        self.done: set[str] = set()
        if path.exists():
            self.done = set(json.loads(path.read_text(encoding="utf-8")))

    def __contains__(self, key: str) -> bool:
        return key in self.done

    def mark(self, key: str) -> None:
        self.done.add(key)
        save_text(self.path, json.dumps(sorted(self.done), ensure_ascii=False, indent=0))


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------
def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Iterable[dict], columns: list[str]) -> int:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})
    tmp.replace(path)
    return len(rows)


def upsert_csv(path: Path, new_rows: list[dict], key: tuple[str, ...], columns: list[str]) -> int:
    """기존 CSV에 새 행을 키 기준으로 덮어쓰며 합친다."""
    if not new_rows and path.exists():
        return len(read_csv(path))
    merged = {tuple(str(r.get(k, "")) for k in key): r for r in read_csv(path)}
    for r in new_rows:
        merged[tuple(str(r.get(k, "")) for k in key)] = r
    return write_csv(path, sorted(merged.values(), key=lambda r: tuple(str(r.get(k, "")) for k in key)), columns)


def season_list(spec: str) -> list[int]:
    """'2025' / '2021-2025' / '2023,2025' → [연도...]"""
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out
