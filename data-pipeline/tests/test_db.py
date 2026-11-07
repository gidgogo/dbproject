"""PostgreSQL 통합 테스트: Flyway 마이그레이션 적용 → 가상 데이터 변환·적재 → 뷰 값과 제약조건 확인

필요: psql 명령과 접속 가능한 PostgreSQL (환경변수 PGHOST, PGPORT, PGUSER, PGPASSWORD 사용).
팀 docker DB라면: PGHOST=localhost PGPORT=5434 PGUSER=kbo PGPASSWORD=kbo
테스트는 KBO_TEST_DB(기본 kbo_pytest) 데이터베이스를 매번 지우고 새로 만든다. 운영용 kbo DB 이름을 지정하지 말 것.
접속이 안 되면 건너뛴다. 실행(data-pipeline 폴더에서): python -m pytest tests/test_db.py -v
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]          # data-pipeline/
MIGRATIONS = ROOT.parent / "backend/src/main/resources/db/migration"
DB = os.environ.get("KBO_TEST_DB", "kbo_pytest")


def migration_files() -> list[Path]:
    """Flyway와 같은 순서(V 번호 오름차순)로 마이그레이션 파일을 돌려준다"""
    files = MIGRATIONS.glob("V*__*.sql")
    return sorted(files, key=lambda p: [int(x) for x in re.match(r"V([\d_.]+)__", p.name).group(1)
                                        .replace("_", ".").split(".") if x])


def psql(sql: str, db: str = DB, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["psql", "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1", "-d", db, "-c", sql],
                          cwd=cwd, capture_output=True, text=True, check=check)


def psql_file(path: Path, cwd: Path, single_transaction: bool = False) -> None:
    cmd = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", DB, "-f", str(path)]
    if single_transaction:  # Flyway도 마이그레이션 파일 하나를 트랜잭션 하나로 실행한다
        cmd.insert(1, "--single-transaction")
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, f"{path.name}: {r.stderr}"


def rows(sql: str) -> list[list[str]]:
    out = psql(sql).stdout.strip()
    return [line.split("|") for line in out.splitlines()] if out else []


@pytest.fixture(scope="module")
def load_work(tmp_path_factory):
    return tmp_path_factory.mktemp("load")


@pytest.fixture(scope="module")
def loaded_db(load_work):
    if not shutil.which("psql"):
        pytest.skip("psql 없음")
    probe = subprocess.run(["psql", "-X", "-Atc", "select 1", "-d", "postgres"], capture_output=True, text=True)
    if probe.returncode != 0:
        pytest.skip(f"PostgreSQL 접속 불가: {probe.stderr.strip()}")
    psql(f"DROP DATABASE IF EXISTS {DB}", db="postgres")
    psql(f"CREATE DATABASE {DB}", db="postgres")
    for migration in migration_files():
        psql_file(migration, cwd=ROOT, single_transaction=True)

    work = load_work
    load = work / "data" / "load"
    fx = ROOT / "tests/fixtures/synthetic"
    subprocess.run([sys.executable, str(ROOT / "tests/fixtures/make_synthetic.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "etl/crawl_to_tables.py"), "--data", str(fx / "data"),
                    "--out", str(load)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(ROOT / "etl/kbodata_to_tables.py"), str(fx / "raw_games.json"),
                    "--players", str(fx / "data/player_season_team.csv"), "--out", str(load)],
                   check=True, capture_output=True)
    psql_file(ROOT / "sql/load_data.sql", cwd=work)
    # 같은 파일을 두 번 적재해도 결과가 같아야 한다(재실행 안전)
    psql_file(ROOT / "sql/load_data.sql", cwd=work)

    return json.loads((fx / "raw_games.json").read_text(encoding="utf-8"))


def test_counts(loaded_db):
    assert rows("select count(*) from match") == [["3"]]
    assert rows("select count(*) from match_team") == [["6"]]
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
    assert rows("select * from v_check_match_result") == []
    # kbodata 'L' 버그가 있는 경기를 찾아내야 한다
    assert rows("select match_id from v_check_pitcher_decision") == [["20250101_OBWO0"]]
    # 기록실 값을 일부러 틀리게 넣은 선수
    assert rows("select player_id from v_compare_batting_official where not is_match") == [["900102"]]
    assert rows("select count(*) from v_compare_team_rank where is_match") == [["2"]]


def test_event_parsing_in_db(loaded_db):
    r = rows("select inning from match_event where match_id='20250103_WOOB0' and event_type='도루' order by seq")
    assert r == [["3"], ["8"]]
    assert rows("select coalesce(player_id::text, 'NULL') from match_event where event_type='보크'") == [["NULL"]]


@pytest.mark.parametrize("sql", [
    # 안타 > 타수
    "update batter_match set hits = at_bats + 1 where player_id = 900101 and match_id = '20250101_OBWO0'",
    # 홈팀이 아닌 팀을 홈으로 (트리거)
    "update match_team set team_id = 'LG' where match_id = '20250101_OBWO0' and home_away = 'H'",
    # 경기ID와 날짜 불일치 (지능형 키 CHECK)
    "update match set match_date = '2025-01-05' where match_id = '20250101_OBWO0'",
    # 팀코드 도메인 위반 (DOMAIN 대신 컬럼 CHECK)
    "insert into team (team_id, team_name, city, first_season) values ('ob', '소문자팀', '서울', 2000)",
    # 시즌 도메인 위반
    "insert into team (team_id, team_name, city, first_season) values ('ZZ', '옛날팀', '서울', 1970)",
    # 업무키 중복 (대리키 id가 생겨도 UNIQUE로 막혀야 한다)
    "insert into match_team (match_id, team_id, home_away, result, runs, hits, errors, walks_hbp) "
    "select match_id, team_id, home_away, result, runs, hits, errors, walks_hbp from match_team limit 1",
    # 자책점 > 실점
    "update pitcher_match set earned_runs = runs_allowed + 1 where player_id = 900111 and match_id = '20250101_OBWO0'",
    # 다른 기록이 참조하는 선수 삭제 (ON DELETE RESTRICT)
    "delete from player where player_id = 900101",
])
def test_constraints_reject_bad_data(loaded_db, sql):
    r = psql(sql, check=False)
    assert r.returncode != 0, f"거부되어야 하는데 성공함: {sql}"


def test_cascade_delete_match(loaded_db):
    psql("begin; delete from match where match_id = '20250102_OBWO0'; "
         "do $$ begin if exists (select 1 from batter_match where match_id = '20250102_OBWO0') "
         "or exists (select 1 from plate_appearance where match_id = '20250102_OBWO0') "
         "then raise exception 'cascade 실패'; end if; end $$; rollback;")


def test_reloading_box_scores_preserves_counts(loaded_db, load_work):
    before = rows("select count(*) from match union all select count(*) from match_event union all select count(*) from match_umpire")
    psql_file(ROOT / "sql/load_data.sql", cwd=load_work)
    assert rows("select count(*) from match union all select count(*) from match_event union all select count(*) from match_umpire") == before


def test_official_rates_are_weighted_across_teams(loaded_db):
    got = rows("""begin;
        update season_batting_official set at_bats=10,hits=1,avg=.100 where player_id=900101;
        insert into season_batting_official(player_id,season,team_id,at_bats,hits,avg)
          values(900101,2025,'WO',10,5,.500);
        update season_pitching_official set outs_recorded=27,earned_runs=1,era=1.00 where player_id=900211;
        insert into season_pitching_official(player_id,season,team_id,outs_recorded,earned_runs,era)
          values(900211,2025,'OB',54,6,3.00);
        select avg_off from v_compare_batting_official where player_id=900101;
        select era_off from v_compare_pitching_official where player_id=900211;
        rollback;""")
    assert got == [["0.300"], ["2.33"]]


def test_missing_team_is_reported(loaded_db):
    got = rows("""begin;
        delete from match_team where match_id='20250101_OBWO0' and home_away='H';
        select match_id from v_check_match_result;
        rollback;""")
    assert got == [["20250101_OBWO0"]]


def test_standings_use_unrounded_win_percentage(loaded_db):
    got = rows("""begin;
        insert into match(match_id,match_date,away_team_id,home_team_id)
        select to_char(date '2024-03-01'+n,'YYYYMMDD')||'_OBWO0',date '2024-03-01'+n,'OB','WO'
          from generate_series(1,120) n
        union all select to_char(date '2024-03-01'+n,'YYYYMMDD')||'_LGHT0',date '2024-03-01'+n,'LG','HT'
          from generate_series(1,113) n;
        insert into match_team(match_id,team_id,home_away,result,runs,hits,errors,walks_hbp)
        select match_id,away_team_id,'A',case when match_date-date '2024-03-01' <=
          case away_team_id when 'OB' then 67 else 63 end then 'W' else 'L' end,0,0,0,0 from match where season=2024
        union all select match_id,home_team_id,'H',case when match_date-date '2024-03-01' <=
          case away_team_id when 'OB' then 67 else 63 end then 'L' else 'W' end,0,0,0,0 from match where season=2024;
        refresh materialized view mv_team_standings;
        select team_id,rank,win_pct from mv_team_standings where season=2024 and team_id in ('OB','LG') order by rank;
        rollback;""")
    assert got == [["OB", "1", "0.558"], ["LG", "2", "0.558"]]



def test_incomplete_box_scores_roll_back_without_losing_data(loaded_db, load_work, tmp_path):
    shutil.copytree(load_work / "data", tmp_path / "data")
    # 경기만 있고 스코어보드·하위 기록이 없는 실패한 수집 결과.
    for name in ("match_team", "inning_score", "batter_match", "plate_appearance", "pitcher_match",
                 "match_event", "match_umpire_stage"):
        path = tmp_path / "data/load" / f"{name}.csv"
        path.write_text(path.read_text().splitlines()[0] + "\n")
    before = rows("select count(*) from player union all select count(*) from match_team")
    result = subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", DB,
                             "-f", str(ROOT / "sql/load_data.sql")],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0 and "팀경기기록" in result.stderr
    assert rows("select count(*) from player union all select count(*) from match_team") == before


def test_kbo_only_loader_needs_no_match_files(loaded_db, load_work, tmp_path):
    load = tmp_path / "data/load"
    load.mkdir(parents=True)
    for name in ("player", "player_season", "player_salary", "season_batting_official",
                 "season_pitching_official", "team_rank_official"):
        shutil.copyfile(load_work / "data/load" / f"{name}.csv", load / f"{name}.csv")
    before = rows("select count(*) from match union all select count(*) from batter_match")
    for _ in range(2):
        psql_file(ROOT / "sql/load_kbo.sql", cwd=tmp_path)
    assert rows("select count(*) from match union all select count(*) from batter_match") == before
    assert rows("select to_regclass('public.pitch'), to_regclass('public.v_pitch_mix')") == [["", ""]]




def test_profile_reloads_preserve_newest_profile_and_salary(loaded_db, tmp_path):
    from crawl.common import write_csv
    from etl.crawl_to_tables import build
    source = tmp_path / 'source'
    pid = 900101
    mapping = dict(player_id=pid, season=2025, team_id='OB', name='예전이름', is_batter=1, is_pitcher=0)
    write_csv(source / 'player_season_team.csv', [mapping], list(mapping))
    profile = dict(player_id=pid, player_name='현재이름', team_name='상무', uniform_no='01',
                   is_retired='true', crawled_at='2026-11-06T12:00:00+09:00',
                   salary_season=2026, salary_10k_krw=5000, salary_text='5000만원')
    def reload():
        build(source, tmp_path / 'data/load')
        psql_file(ROOT / 'sql/load_kbo.sql', tmp_path)
    def state():
        return rows(f"select player_name,is_retired,current_team_name,current_uniform_no,"
                    f"profile_crawled_at::date from player where player_id={pid}")
    write_csv(source / 'players.csv', [profile], list(profile))
    reload()
    expected = [['현재이름', 't', '상무', '01', '2026-11-06']]
    assert state() == expected
    (source / 'players.csv').unlink()
    reload()  # Missing profile cannot imply active status or a current name change.
    assert state() == expected
    profile.update(player_name='예전이름', team_name='두산 베어스', uniform_no='99',
                   is_retired='false', crawled_at='2025-06-01T12:00:00+09:00', salary_10k_krw=1000)
    write_csv(source / 'players.csv', [profile], list(profile))
    reload()
    assert state() == expected
    assert rows(f'select salary_10k_krw from player_salary where player_id={pid} and season=2026') == [['5000']]
    profile.update(player_name='최신이름', team_name='LG 트윈스', uniform_no='02',
                   is_retired='false', crawled_at='2026-11-07T12:00:00+09:00', salary_10k_krw=6000)
    write_csv(source / 'players.csv', [profile], list(profile))
    reload()
    assert state() == [['최신이름', 'f', 'LG 트윈스', '02', '2026-11-07']]
    assert rows(f'select salary_10k_krw from player_salary where player_id={pid} and season=2026') == [['6000']]


def test_schema_has_no_types_that_break_jpa_validate(loaded_db):
    """ddl-auto=validate 가 DOMAIN·smallint·char 를 엔티티 타입과 다르게 보므로 쓰지 않는다"""
    assert rows("select typname from pg_type where typtype = 'd' and typnamespace = 'public'::regnamespace") == []
    assert rows("""select c.relname || '.' || a.attname || ' ' || format_type(a.atttypid, a.atttypmod)
                   from pg_attribute a join pg_class c on c.oid = a.attrelid
                   where c.relnamespace = 'public'::regnamespace and c.relkind = 'r' and a.attnum > 0
                     and not a.attisdropped and format_type(a.atttypid, a.atttypmod) ~ '^(smallint|character\\()'
                """) == []


def test_composite_key_tables_have_surrogate_id(loaded_db):
    """복합 업무키 테이블은 id(bigint) PK + 업무키 UNIQUE"""
    got = rows("""select c.relname from pg_constraint con join pg_class c on c.oid = con.conrelid
                  where con.contype = 'p' and c.relnamespace = 'public'::regnamespace
                    and array_length(con.conkey, 1) > 1""")
    assert got == []
    assert rows("select count(*) from pg_constraint where conname = 'uq_match_team_key'") == [["1"]]
