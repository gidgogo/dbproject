"""부분 수집·잘못된 응답이 기존 공유 CSV를 손상하지 않는지 확인한다."""
import pytest
import requests

from crawl.common import Checkpoint, read_csv, write_csv
from crawl import kbo_records as records, kbo_team_rank as ranks
from etl.reference import Reference


def unit(root, kind, page, rows, done=True):
    write_csv(root / '2025' / f'OB_{kind}_{page}.csv', rows, records.UNIT_COLS)
    if done:
        Checkpoint(root / '_done.json').mark(f'2025|OB|{kind}|{page}')


def record(pid='100', **extra):
    return dict(season='2025', team_id='OB', player_id=pid, name='가상선수',
                team_name='두산', games='30', avg='0.300', **extra)


@pytest.fixture
def merge_paths(tmp_path, monkeypatch):
    data, raw = tmp_path / 'data', tmp_path / 'raw'
    monkeypatch.setattr(records, 'DATA', data)
    monkeypatch.setattr(records, 'OUT_DIR', raw)
    return data, raw


@pytest.mark.parametrize('kind,filename,cols', [
    ('hitter', 'season_batting.csv', records.BAT_COLS),
    ('pitcher', 'season_pitching.csv', records.PIT_COLS),
])
def test_partial_merge_keeps_official_record_and_mapping_roles(merge_paths, kind, filename, cols):
    data, raw = merge_paths
    old = record(walks='5', ip_text='6 1/3', outs_recorded='19')
    write_csv(data / filename, [old], cols)
    write_csv(data / 'player_season_team.csv', [dict(old, is_batter=1, is_pitcher=1)], records.PST_COLS)
    before = (data / filename).read_bytes()
    unit(raw, kind, 'basic1', [record()])
    records.merge()  # ID-only mode is supported but cannot replace complete statistics.
    assert (data / filename).read_bytes() == before
    player = read_csv(data / 'player_season_team.csv')[0]
    assert player['is_batter'] == player['is_pitcher'] == '1'
    with pytest.raises(RuntimeError, match='일부만 완료'):
        records.merge(require_complete=True)
    assert (data / filename).read_bytes() == before


@pytest.mark.parametrize('fault', ['missing_checkpoint', 'different_players', 'different_values'])
def test_inconsistent_pair_is_not_published(merge_paths, fault):
    data, raw = merge_paths
    write_csv(data / 'season_batting.csv', [record(walks='5')], records.BAT_COLS)
    before = (data / 'season_batting.csv').read_bytes()
    unit(raw, 'hitter', 'basic1', [record()])
    second = record(walks='8')
    if fault == 'different_players':
        second['player_id'] = '101'
    if fault == 'different_values':
        second['avg'] = '0.400'
    unit(raw, 'hitter', 'basic2', [second], done=fault != 'missing_checkpoint')
    with pytest.raises(RuntimeError):
        records.merge(require_complete=True)
    assert (data / 'season_batting.csv').read_bytes() == before


def test_completed_pair_updates_statistics(merge_paths):
    data, raw = merge_paths
    unit(raw, 'hitter', 'basic1', [record(at_bats='10', hits='3')])
    unit(raw, 'hitter', 'basic2', [record(walks='5', ops='0.900')])
    records.merge(require_complete=True)
    got = read_csv(data / 'season_batting.csv')[0]
    assert (got['at_bats'], got['hits'], got['walks'], got['ops']) == ('10', '3', '5', '0.9')


def test_network_failure_returns_failure_and_keeps_existing_csv(merge_paths, monkeypatch):
    data, raw = merge_paths
    write_csv(data / 'season_batting.csv', [record(walks='5')], records.BAT_COLS)
    before = (data / 'season_batting.csv').read_bytes()
    def fail(*args):
        raise requests.Timeout('synthetic timeout')
    monkeypatch.setattr(records, 'crawl', fail)
    assert records.main(['--seasons', '2025']) == 1
    assert (data / 'season_batting.csv').read_bytes() == before


def rank_html(year=2025, fault=None):
    teams = sorted(Reference.load().teams_for_season(year))
    if fault == 'empty':
        teams = []
    elif fault == 'missing_team':
        teams = teams[:-1]
    elif fault == 'duplicate_team':
        teams[-1] = teams[0]
    elif fault == 'unknown_team':
        teams[-1] = '알수없는팀'
    shown = f'{year}1030' if fault == 'wrong_date' else f'{year}1031'
    wins = '' if fault == 'missing_number' else '1'
    games = '2' if fault == 'bad_sum' else '1'
    body = ''.join(f'<tr><td>1</td><td>{t}</td><td>{games}</td><td>{wins}</td>'
                   '<td>0</td><td>0</td><td>1.000</td><td>0</td></tr>' for t in teams)
    return (f'<html><form><input name="hfSearchDate" value="{shown}">'
            '<table><thead><tr><th>순위</th><th>팀명</th><th>경기</th><th>승</th><th>패</th>'
            f'<th>무</th><th>승률</th><th>게임차</th></tr></thead><tbody>{body}</tbody></table></form></html>')


def fake_client(html):
    class Client:
        def __init__(self, *args): self.html = html
        def get(self): return self.html
        def postback(self, *args, **kwargs): return self.html
    return Client


@pytest.mark.parametrize('fault', ['empty', 'missing_team', 'duplicate_team', 'unknown_team',
                                  'wrong_date', 'missing_number', 'bad_sum'])
def test_bad_rank_response_fails_without_changing_previous_file(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(ranks, 'DATA', tmp_path)
    monkeypatch.setattr(ranks, 'RAW', tmp_path / 'raw')
    monkeypatch.setattr(ranks, 'PostbackClient', fake_client(rank_html(fault=fault)))
    old = tmp_path / 'team_rank.csv'
    old.write_text('previous complete ranking\n')
    assert ranks.main(['--dates', '2025-10-31']) == 1
    assert old.read_text() == 'previous complete ranking\n'


@pytest.mark.parametrize('year,count', [(2012, 8), (2013, 9), (2025, 10)])
def test_complete_rank_response_uses_season_team_count(tmp_path, monkeypatch, year, count):
    monkeypatch.setattr(ranks, 'DATA', tmp_path)
    monkeypatch.setattr(ranks, 'RAW', tmp_path / 'raw')
    monkeypatch.setattr(ranks, 'PostbackClient', fake_client(rank_html(year)))
    assert ranks.main(['--dates', f'{year}-10-31']) == 0
    assert len(read_csv(tmp_path / 'team_rank.csv')) == count
