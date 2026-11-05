"""PostgreSQL 통합 테스트: DDL 생성 → 가상 데이터 변환·적재 → 뷰 값과 제약조건 확인

필요: psql 명령과 접속 가능한 PostgreSQL (환경변수 PGHOST, PGPORT, PGUSER 사용).
접속이 안 되면 건너뛴다. 실행: python -m pytest tests/test_db.py -v
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DB = os.environ.get("KBO_TEST_DB", "kbo_pytest")


def psql(sql: str, db: str = DB, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["psql", "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1", "-d", db, "-c", sql],
                          cwd=cwd, capture_output=True, text=True, check=check)


def psql_file(path: Path, cwd: Path) -> None:
    r = subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", DB, "-f", str(path)],
                       cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def rows(sql: str) -> list[list[str]]:
    out = psql(sql).stdout.strip()
    return [line.split("|") for line in out.splitlines()] if out else []


@pytest.fixture(scope="module")
def loaded_db(tmp_path_factory):
    if not shutil.which("psql"):
        pytest.skip("psql 없음")
    probe = subprocess.run(["psql", "-X", "-Atc", "select 1", "-d", "postgres"], capture_output=True, text=True)
    if probe.returncode != 0:
        pytest.skip(f"PostgreSQL 접속 불가: {probe.stderr.strip()}")
    psql(f"DROP DATABASE IF EXISTS {DB}", db="postgres")
    psql(f"CREATE DATABASE {DB}", db="postgres")
    psql_file(ROOT / "erd/ddl/00_create_all.sql", cwd=ROOT)

    work = tmp_path_factory.mktemp("load")
    load = work / "data" / "load"
    fx = ROOT / "tests/fixtures/synthetic"
    subprocess.run([sys.executable, str(ROOT / "tests/fixtures/make_synthetic.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "etl/crawl_to_tables.py"), "--data", str(fx / "data"),
                    "--out", str(load)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(ROOT / "etl/kbodata_to_tables.py"), str(fx / "raw_games.json"),
                    "--players", str(fx / "data/player_season_team.csv"), "--out", str(load)],
                   check=True, capture_output=True)
    psql_file(ROOT / "erd/ddl/07_load_data.sql", cwd=work)
    # 같은 파일을 두 번 적재해도 결과가 같아야 한다(재실행 안전)
    psql_file(ROOT / "erd/ddl/07_load_data.sql", cwd=work)
    return json.loads((fx / "raw_games.json").read_text(encoding="utf-8"))


def test_counts(loaded_db):
    assert rows("select count(*) from game") == [["3"]]
    assert rows("select count(*) from team_game") == [["6"]]
    assert rows("select count(*) from umpire") == [["6"]]


def test_season_batting_matches_box_scores(loaded_db):
    """시즌 타수·안타 = 박스스코어 경기별 값의 합 (가상 데이터에서 직접 계산한 값과 비교)"""
    expected = {}
    for g in loaded_db:
        for side in ("away_batter", "home_batter"):
            for b in g["contents"][side]:
                name = b.get("name") or b.get("선수명")
                ab = b.get("bat_num", b.get("타수"))
                h = b.get("hit", b.get("안타"))
                e = expected.setdefault(name, [0, 0])
                e[0] += ab
                e[1] += h
    got = {r[0]: [int(r[1]), int(r[2])] for r in rows(
        "select p.player_name, b.at_bats, b.hits from v_season_batting_total b join player p using (player_id)")}
    assert got == expected


def test_rates(loaded_db):
    # OB가상타자갑: 10타수 5안타, 홈런 2, 희생플라이 1, 볼넷·사구 0 → AVG .500 OBP 5/11 SLG 11/10
    r = rows("select avg, obp, slg, home_runs from v_season_batting_total where player_id = 900101")
    assert r == [["0.500", "0.455", "1.100", "2"]]


def test_standings(loaded_db):
    r = rows("select team_id, rank, wins, losses, draws, win_pct, games_behind, last10, streak "
             "from mv_team_standings order by rank")
    assert r == [["OB", "1", "2", "0", "1", "1.000", "0.0", "2승1무0패", "1무"],
                 ["WO", "2", "0", "2", "1", "0.000", "2.0", "0승1무2패", "1무"]]


def test_pitching(loaded_db):
    r = rows("select ip_display, era, quality_starts from v_season_pitching_total where player_id = 900111")
    assert r == [["21 2/3", "1.66", "3"]]


def test_check_views(loaded_db):
    assert rows("select * from v_check_team_runs") == []
    assert rows("select * from v_check_team_hits") == []
    assert rows("select * from v_check_game_result") == []
    # kbodata 'L' 버그가 있는 경기를 찾아내야 한다
    assert rows("select game_id from v_check_pitcher_decision") == [["20250101_OBWO0"]]
    # 기록실 값을 일부러 틀리게 넣은 선수
    assert rows("select player_id from v_compare_batting_official where not is_match") == [["900102"]]
    assert rows("select count(*) from v_compare_team_rank where is_match") == [["2"]]


def test_event_parsing_in_db(loaded_db):
    r = rows("select inning from game_event where game_id='20250103_WOOB0' and event_type='도루' order by seq")
    assert r == [["3"], ["8"]]
    assert rows("select coalesce(player_id::text, 'NULL') from game_event where event_type='보크'") == [["NULL"]]


@pytest.mark.parametrize("sql", [
    # 안타 > 타수
    "update batter_game set hits = at_bats + 1 where player_id = 900101 and game_id = '20250101_OBWO0'",
    # 홈팀이 아닌 팀을 홈으로 (트리거)
    "update team_game set team_id = 'LG' where game_id = '20250101_OBWO0' and home_away = 'H'",
    # 경기ID와 날짜 불일치 (지능형 키 CHECK)
    "update game set game_date = '2025-01-05' where game_id = '20250101_OBWO0'",
    # 팀코드 도메인 위반
    "insert into team values ('ob', '소문자팀', '서울', 2000)",
    # 자책점 > 실점
    "update pitcher_game set earned_runs = runs_allowed + 1 where player_id = 900111 and game_id = '20250101_OBWO0'",
    # 다른 기록이 참조하는 선수 삭제 (ON DELETE RESTRICT)
    "delete from player where player_id = 900101",
])
def test_constraints_reject_bad_data(loaded_db, sql):
    r = psql(sql, check=False)
    assert r.returncode != 0, f"거부되어야 하는데 성공함: {sql}"


def test_cascade_delete_game(loaded_db):
    psql("begin; delete from game where game_id = '20250102_OBWO0'; "
         "do $$ begin if exists (select 1 from batter_game where game_id = '20250102_OBWO0') "
         "or exists (select 1 from plate_appearance where game_id = '20250102_OBWO0') "
         "then raise exception 'cascade 실패'; end if; end $$; rollback;")
