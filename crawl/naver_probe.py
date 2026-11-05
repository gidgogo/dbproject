"""2-4 가능성 확인: 네이버 문자중계 JSON 구조·제공 연도 확인 (요청: 연도당 약 2~3회)

확인 항목
  - 투구마다 구종(stuff)·구속(speed)·결과(pitchResult)·볼카운트(currentGameState)가 있는지
  - 투구 위치 좌표(ptsOptions.crossPlateX 등)가 있는지
  - 몇 년도 경기까지 제공되는지 (--years 로 여러 해를 한 번에 확인)
결과: docs/probe/naver_probe_YYYYMMDD.md (필드 트리 + 연도별 요약), 원본 data/raw/probe/naver_*.json

사용 예:
    python crawl/naver_probe.py --years 2025              # 2025 한 경기만
    python crawl/naver_probe.py --years 2018,2020,2022,2023,2025
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawl.common import RAW, ROOT, PoliteSession, save_text, setup_logging  # noqa: E402
from crawl.naver_parsers import pitch_rows, playable  # noqa: E402
from crawl.naver_relay import HEADERS, api_get  # noqa: E402


def field_tree(obj, prefix: str = "", depth: int = 0, out: list | None = None, max_depth: int = 5) -> list[str]:
    """JSON 키 구조를 '경로: 타입 = 예시' 줄로 (리스트는 첫 원소만)"""
    out = [] if out is None else out
    if depth > max_depth:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                out.append(f"{path}: {type(v).__name__}{f'[{len(v)}]' if isinstance(v, list) else ''}")
                field_tree(v, path, depth + 1, out, max_depth)
            else:
                out.append(f"{path}: {type(v).__name__} = {str(v)[:40]!r}")
    elif isinstance(obj, list) and obj:
        field_tree(obj[0], prefix + "[]", depth + 1, out, max_depth)
    return out


def probe_year(session: PoliteSession, year: int, lines: list[str]) -> dict:
    # 시즌 중반(6월 첫 주)부터 하루씩 찾아 끝난 정규시즌 경기를 하나 고른다
    for day in range(1, 15):
        d = f"{year}-06-{day:02d}"
        res = api_get(session, "/schedule/games", fields="basic,schedule,baseball", upperCategoryId="kbaseball",
                      categoryId="kbo", fromDate=d, toDate=d, size=50, page=1)
        games = [g for g in res.get("games") or [] if playable(g)]
        if games:
            break
    else:
        return {"year": year, "game": None}
    g = games[0]
    save_text(RAW / "probe" / f"naver_schedule_{year}.json", json.dumps(res, ensure_ascii=False, indent=1))
    relay = api_get(session, f"/schedule/games/{g['gameId']}/relay", inning=1)
    save_text(RAW / "probe" / f"naver_relay_{g['gameId']}_1.json", json.dumps(relay, ensure_ascii=False, indent=1))
    data = relay.get("textRelayData") or {}
    rows = pitch_rows({1: data})
    blocks = data.get("textRelays") or []
    pts = sum(len(b.get("ptsOptions") or []) for b in blocks)
    summary = {"year": year, "game": g["gameId"], "pitches_inning1": len(rows),
               "with_speed": sum(1 for r in rows if r["speed_kmh"]),
               "with_stuff": sum(1 for r in rows if r["pitch_type_ko"]),
               "with_location": sum(1 for r in rows if r["plate_x"] is not None), "pts_options": pts,
               "lineup": bool(data.get("homeLineup"))}
    if not lines:  # 첫 연도만 필드 트리를 자세히
        lines += ["## 일정 항목 필드 (첫 경기)", "", "```", *field_tree(g), "```", "",
                  "## 중계 textRelayData 필드 (1회)", "", "```", *field_tree(data), "```"]
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", default="2025")
    args = ap.parse_args(argv)
    setup_logging()
    session = PoliteSession(headers=HEADERS)
    tree: list[str] = []
    summaries = []
    for y in [int(x) for x in args.years.split(",") if x.strip()]:
        try:
            summaries.append(probe_year(session, y, tree))
        except Exception as e:
            summaries.append({"year": y, "error": str(e)})
    head = [f"# 네이버 문자중계 구조 확인 ({date.today().isoformat()})", "",
            f"- 요청 수: {session.count}, 원본: data/raw/probe/naver_*.json", "",
            "## 연도별 제공 여부 (6월 첫 정규시즌 경기, 1회 기준)", "",
            "| 연도 | 경기 | 투구 수 | 구속 있음 | 구종 있음 | 좌표 있음 | ptsOptions | 라인업 | 오류 |",
            "|---|---|---:|---:|---:|---:|---:|---|---|"]
    for s in summaries:
        head.append(f"| {s['year']} | {s.get('game') or '-'} | {s.get('pitches_inning1', '-')} | "
                    f"{s.get('with_speed', '-')} | {s.get('with_stuff', '-')} | {s.get('with_location', '-')} | "
                    f"{s.get('pts_options', '-')} | {s.get('lineup', '-')} | {s.get('error', '')} |")
    out = ROOT / "docs" / "probe" / f"naver_probe_{date.today():%Y%m%d}.md"
    save_text(out, "\n".join(head + [""] + tree) + "\n")
    print(f"결과: {out}")
    for s in summaries:
        print(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
