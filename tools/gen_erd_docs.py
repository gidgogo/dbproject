"""PostgreSQL 카탈로그 → ERD·테이블 기술서 자동 생성 (DDL과 문서가 어긋나지 않게)

만드는 파일
  erd/kbo_erd.dbml               dbdiagram.io 에 붙여 넣으면 ERD가 그려진다
  erd/erd_logical.mmd            Mermaid 논리 ERD (모든 속성, PK/FK, 식별=실선/비식별=점선)
  docs/report/10_table_spec.md   보고서 10장 테이블 기술서 (Attribute, Data Type, NN, Key, Default, Description)
  docs/report/09_domain_usage.md 도메인별 사용 컬럼 목록 (보고서 9장 부록)

필요: 스키마가 만들어진 DB (erd/ddl/00_create_all.sql) 와 psql
사용 예: python tools/gen_erd_docs.py --db kbo
"""
from __future__ import annotations

import argparse
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEP = "\x1f"

# 표 순서 (보고서에 나오는 순서)
ORDER = ["team", "stadium", "team_season", "player", "player_season", "player_salary", "game", "team_game",
         "inning_score", "pa_result_type", "pa_result_code", "batter_game", "plate_appearance", "pitcher_game",
         "game_event_type", "game_event", "umpire", "game_umpire", "pitch_type", "pitch_result", "pitch",
         "season_batting_official", "season_pitching_official", "team_rank_official"]
GROUPS = {
    "기준 정보": ["team", "stadium", "team_season"],
    "선수": ["player", "player_season", "player_salary"],
    "경기 기록 (kbodata)": ["game", "team_game", "inning_score", "batter_game", "plate_appearance",
                         "pa_result_code", "pa_result_type", "pitcher_game", "game_event", "game_event_type",
                         "umpire", "game_umpire"],
    "투구 (네이버 문자중계)": ["pitch", "pitch_type", "pitch_result"],
    "기록실 공식 기록 (검증용)": ["season_batting_official", "season_pitching_official", "team_rank_official"],
}


def q(db: str, sql: str) -> list[list[str]]:
    out = subprocess.run(["psql", "-X", "-At", "-F", SEP, "-d", db, "-c", sql],
                         capture_output=True, text=True, check=True).stdout
    return [line.split(SEP) for line in out.splitlines() if line]


def load(db: str):
    tables = {r[0]: r[1] for r in q(db, """
        select c.relname, coalesce(obj_description(c.oid, 'pg_class'), '')
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relkind = 'r'""")}
    cols = defaultdict(list)
    for t, name, typ, notnull, default, comment, domain, generated in q(db, """
        select c.relname, a.attname, format_type(a.atttypid, a.atttypmod),
               a.attnotnull::text, coalesce(pg_get_expr(d.adbin, d.adrelid), ''),
               coalesce(col_description(c.oid, a.attnum), ''),
               coalesce((select bt.typname || ' (' || format_type(bt.typbasetype, bt.typtypmod) || ')'
                         from pg_type bt where bt.oid = a.atttypid and bt.typtype = 'd'), ''),
               a.attgenerated
        from pg_attribute a
        join pg_class c on c.oid = a.attrelid
        join pg_namespace n on n.oid = c.relnamespace
        left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
        where n.nspname = 'public' and c.relkind = 'r' and a.attnum > 0 and not a.attisdropped
        order by c.relname, a.attnum"""):
        if generated == "s":
            default = "GENERATED: " + default
        cols[t].append({"name": name, "type": typ, "nn": notnull == "true", "default": default,
                        "comment": comment, "domain": domain})
    pk = defaultdict(list)
    for t, col in q(db, """
        select tc.table_name, kcu.column_name from information_schema.table_constraints tc
        join information_schema.key_column_usage kcu on kcu.constraint_name = tc.constraint_name
             and kcu.table_name = tc.table_name
        where tc.constraint_type = 'PRIMARY KEY' and tc.table_schema = 'public'
        order by tc.table_name, kcu.ordinal_position"""):
        pk[t].append(col)
    uniques = defaultdict(list)
    for t, cons, colnames in q(db, """
        select c.relname, con.conname,
               (select string_agg(a.attname, ',' order by k.ord) from unnest(con.conkey) with ordinality k(n, ord)
                join pg_attribute a on a.attrelid = con.conrelid and a.attnum = k.n)
        from pg_constraint con join pg_class c on c.oid = con.conrelid
        where con.contype = 'u' and c.relnamespace = 'public'::regnamespace"""):
        uniques[t].append(colnames.split(","))
    fks = []
    for t, cons, child_cols, parent, parent_cols, upd, dele in q(db, """
        select c.relname, con.conname,
               (select string_agg(a.attname, ',' order by k.ord) from unnest(con.conkey) with ordinality k(n, ord)
                join pg_attribute a on a.attrelid = con.conrelid and a.attnum = k.n),
               p.relname,
               (select string_agg(a.attname, ',' order by k.ord) from unnest(con.confkey) with ordinality k(n, ord)
                join pg_attribute a on a.attrelid = con.confrelid and a.attnum = k.n),
               con.confupdtype, con.confdeltype
        from pg_constraint con join pg_class c on c.oid = con.conrelid join pg_class p on p.oid = con.confrelid
        where con.contype = 'f' and c.relnamespace = 'public'::regnamespace
        order by c.relname, con.conname"""):
        fks.append({"child": t, "name": cons, "cols": child_cols.split(","), "parent": parent,
                    "pcols": parent_cols.split(","), "upd": ACTIONS[upd], "del": ACTIONS[dele]})
    checks = defaultdict(list)
    for t, cons, expr in q(db, """
        select c.relname, con.conname, pg_get_constraintdef(con.oid)
        from pg_constraint con join pg_class c on c.oid = con.conrelid
        where con.contype = 'c' and c.relnamespace = 'public'::regnamespace order by 1, 2"""):
        checks[t].append((cons, expr))
    domains = q(db, """
        select t.typname, format_type(t.typbasetype, t.typtypmod),
               coalesce((select string_agg(pg_get_constraintdef(c.oid), ' ') from pg_constraint c
                         where c.contypid = t.oid), ''),
               coalesce(obj_description(t.oid, 'pg_type'), '')
        from pg_type t where t.typtype = 'd' and t.typnamespace = 'public'::regnamespace order by 1""")
    return tables, cols, pk, uniques, fks, checks, domains


ACTIONS = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}


def logical_name(comment: str) -> tuple[str, str]:
    if ":" in comment:
        a, b = comment.split(":", 1)
        return a.strip(), b.strip()
    return "", comment.strip()


def is_identifying(fk: dict, pk: dict) -> bool:
    return set(fk["cols"]) <= set(pk[fk["child"]])


def child_is_unique(fk: dict, pk: dict, uniques: dict) -> bool:
    keys = [pk[fk["child"]]] + uniques[fk["child"]]
    return any(set(k) == set(fk["cols"]) for k in keys)


def short_type(t: str) -> str:
    """format_type 결과를 DBML·SQL에서 그대로 쓸 수 있는 짧은 이름으로"""
    for long, short in (("character varying", "varchar"), ("character", "char"),
                        ("timestamp with time zone", "timestamptz"), ("time without time zone", "time")):
        if t.startswith(long):
            return short + t[len(long):]
    return t


def gen_dbml(tables, cols, pk, uniques, fks) -> str:
    out = ["// KBO 야구 기록 DB — tools/gen_erd_docs.py 가 PostgreSQL 카탈로그에서 자동 생성", "// dbdiagram.io 에 붙여 넣기", ""]
    for g, ts in GROUPS.items():
        out.append(f"TableGroup \"{g}\" {{")
        out += [f"  {t}" for t in ts]
        out.append("}")
    out.append("")
    for t in ORDER:
        lname, desc = logical_name(tables[t])
        out.append(f"Table {t} [note: '{(lname + ': ' + desc).replace(chr(39), '')}'] {{")
        for c in cols[t]:
            attrs = []
            if c["nn"]:
                attrs.append("not null")
            if len(pk[t]) == 1 and c["name"] == pk[t][0]:
                attrs.append("pk")
            ln, d = logical_name(c["comment"])
            attrs.append(f"note: '{(ln + ' - ' + d).replace(chr(39), '')}'")
            # dbdiagram 에서 SQL로 내보낼 수 있도록 도메인 대신 기본 자료형을 쓰고, 도메인은 note에 남긴다
            typ = short_type(c["domain"].split(" (", 1)[1][:-1] if c["domain"] else c["type"])
            if c["domain"]:
                attrs[-1] = attrs[-1][:-1] + f" [도메인 {c['domain'].split(' (')[0]}]'"
            out.append(f"  {c['name']} {typ} [{', '.join(attrs)}]")
        if len(pk[t]) > 1:
            out += ["  indexes {", f"    ({', '.join(pk[t])}) [pk]", "  }"]
        out.append("}")
        out.append("")
    for fk in fks:
        rel = "-" if child_is_unique(fk, pk, uniques) else ">"
        if len(fk["cols"]) == 1:
            out.append(f"Ref {fk['name']}: {fk['child']}.{fk['cols'][0]} {rel} {fk['parent']}.{fk['pcols'][0]} "
                       f"[update: {fk['upd'].lower()}, delete: {fk['del'].lower()}]")
        else:
            out.append(f"Ref {fk['name']}: {fk['child']}.({', '.join(fk['cols'])}) {rel} "
                       f"{fk['parent']}.({', '.join(fk['pcols'])}) [update: {fk['upd'].lower()}, delete: {fk['del'].lower()}]")
    return "\n".join(out) + "\n"


def mermaid_type(c: dict) -> str:
    t = c["domain"].split(" (")[0] if c["domain"] else short_type(c["type"])
    return t.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "_")


def gen_mermaid(tables, cols, pk, uniques, fks) -> str:
    out = ["%% KBO 야구 기록 DB 논리 ERD — tools/gen_erd_docs.py 자동 생성",
           "%% 실선 = 식별 관계(부모 키가 자식 PK에 포함), 점선 = 비식별 관계", "erDiagram"]
    fk_cols = defaultdict(set)
    for fk in fks:
        fk_cols[fk["child"]] |= set(fk["cols"])
    for fk in fks:
        parent_side = "|o" if any(not next(c for c in cols[fk["child"]] if c["name"] == x)["nn"] for x in fk["cols"]) else "||"
        child_side = "o|" if child_is_unique(fk, pk, uniques) else "o{"
        line = "--" if is_identifying(fk, pk) else ".."
        out.append(f"    {fk['parent']} {parent_side}{line}{child_side} {fk['child']} : \"{','.join(fk['cols'])}\"")
    for t in ORDER:
        out.append(f"    {t} {{")
        for c in cols[t]:
            keys = []
            if c["name"] in pk[t]:
                keys.append("PK")
            if c["name"] in fk_cols[t]:
                keys.append("FK")
            ln, _ = logical_name(c["comment"])
            out.append(f"        {mermaid_type(c)} {c['name']} {','.join(keys)} \"{ln}\"".replace("  \"", " \""))
        out.append("    }")
    return "\n".join(out) + "\n"


def gen_table_spec(tables, cols, pk, uniques, fks, checks) -> str:
    out = ["# 10. 테이블 기술서", "",
           "> `tools/gen_erd_docs.py` 가 PostgreSQL 카탈로그(컬럼 COMMENT·제약조건)에서 자동 생성했다.",
           "> 내용을 고칠 때는 `erd/ddl/02_tables.sql` 의 COMMENT를 고친 뒤 다시 생성한다.", ""]
    fk_by_col = defaultdict(dict)
    for fk in fks:
        for c, pc in zip(fk["cols"], fk["pcols"]):
            fk_by_col[fk["child"]][c] = f"FK→{fk['parent']}.{pc}"
    for i, t in enumerate(ORDER, 1):
        lname, desc = logical_name(tables[t])
        out += [f"## 10.{i} {lname} ({t})", "", desc, "",
                "| Attribute | 논리명 | Data Type | NN | Key | Default | Description |",
                "|---|---|---|:---:|---|---|---|"]
        for c in cols[t]:
            key = []
            if c["name"] in pk[t]:
                key.append("PK")
            if c["name"] in fk_by_col[t]:
                key.append(fk_by_col[t][c["name"]])
            for u in uniques[t]:
                if c["name"] in u:
                    key.append("UQ")
                    break
            ln, d = logical_name(c["comment"])
            typ = c["domain"] or c["type"]
            dflt = c["default"].replace("|", "\\|")
            out.append(f"| {c['name']} | {ln} | {typ} | {'Y' if c['nn'] else ''} | {', '.join(key)} | {dflt} | {d} |")
        rel = [fk for fk in fks if fk["child"] == t]
        if rel:
            out += ["", "**참조 무결성 (FK)**", ""]
            out += [f"- `{fk['name']}`: ({', '.join(fk['cols'])}) → {fk['parent']}({', '.join(fk['pcols'])}) "
                    f"ON UPDATE {fk['upd']} ON DELETE {fk['del']}"
                    + (" — 식별 관계" if is_identifying(fk, pk) else " — 비식별 관계") for fk in rel]
        if checks[t]:
            out += ["", "**CHECK 제약**", ""]
            out += [f"- `{name}`: `{expr}`" for name, expr in checks[t]]
        out.append("")
    return "\n".join(out)


def gen_domain_usage(cols, domains) -> str:
    used = defaultdict(list)
    for t in ORDER:
        for c in cols[t]:
            if c["domain"]:
                used[c["domain"].split(" (")[0]].append(f"{t}.{c['name']}")
    out = ["# 9-부록. 도메인별 사용 컬럼 (자동 생성)", "",
           "| 도메인 | 기본 자료형 | 제약 | 설명 | 사용 컬럼 |", "|---|---|---|---|---|"]
    for name, base, cons, comment in domains:
        out.append(f"| {name} | {base} | `{cons}` | {comment} | {', '.join(used[name])} |")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="kbo")
    args = ap.parse_args()
    tables, cols, pk, uniques, fks, checks, domains = load(args.db)
    missing = set(tables) ^ set(ORDER)
    if missing:
        raise SystemExit(f"ORDER 목록과 DB 테이블이 다름: {missing}")
    (ROOT / "erd/kbo_erd.dbml").write_text(gen_dbml(tables, cols, pk, uniques, fks), encoding="utf-8")
    (ROOT / "erd/erd_logical.mmd").write_text(gen_mermaid(tables, cols, pk, uniques, fks), encoding="utf-8")
    (ROOT / "docs/report").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/report/10_table_spec.md").write_text(gen_table_spec(tables, cols, pk, uniques, fks, checks),
                                                       encoding="utf-8")
    (ROOT / "docs/report/09_domain_usage.md").write_text(gen_domain_usage(cols, domains), encoding="utf-8")
    print(f"테이블 {len(tables)}개, FK {len(fks)}개 → erd/kbo_erd.dbml, erd/erd_logical.mmd, "
          "docs/report/10_table_spec.md, docs/report/09_domain_usage.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
