"""PostgreSQL 카탈로그 → ERD·테이블 기술서 자동 생성 (DDL과 문서가 어긋나지 않게)

만드는 파일
  erd/kbo_erd.dbml               dbdiagram.io 에 붙여 넣으면 ERD가 그려진다
  erd/erd_logical.mmd            Mermaid 논리 ERD (모든 속성, PK/FK, 식별=실선/비식별=점선)
  docs/report/10_table_spec.md   보고서 10장 테이블 기술서 (Attribute, Data Type, NN, Key, Default, Description)
  docs/report/09_domain_usage.md 도메인별 사용 컬럼 목록 (보고서 9장 부록)
  docs/report/08_glossary_terms.md 표준 용어 목록 (논리명 ↔ 물리명, 보고서 8장 부록)

필요: Flyway 마이그레이션(backend/src/main/resources/db/migration)이 적용된 DB 와 psql
      도메인은 DB에 DOMAIN 타입으로 만들지 않으므로(JPA validate 호환) erd/domains.csv, erd/domain_columns.csv 에서 읽는다.
사용 예: PGHOST=localhost PGPORT=5434 PGUSER=kbo PGPASSWORD=kbo python tools/gen_erd_docs.py --db kbo
"""
from __future__ import annotations

import argparse
import csv
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEP = "\x1f"

# 표 순서 (보고서에 나오는 순서)
ORDER = ["team", "stadium", "team_season", "player", "player_season", "player_salary", "match", "match_team",
         "inning_score", "pa_result_type", "pa_result_code", "batter_match", "plate_appearance", "pitcher_match",
         "match_event_type", "match_event", "umpire", "match_umpire",
         "season_batting_official", "season_pitching_official", "team_rank_official"]
GROUPS = {
    "기준 정보": ["team", "stadium", "team_season"],
    "선수": ["player", "player_season", "player_salary"],
    "경기 기록 (kbodata)": ["match", "match_team", "inning_score", "batter_match", "plate_appearance",
                         "pa_result_code", "pa_result_type", "pitcher_match", "match_event", "match_event_type",
                         "umpire", "match_umpire"],
    "KBO 공식 시즌 기록·순위": ["season_batting_official", "season_pitching_official", "team_rank_official"],
}


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def q(db: str, sql: str) -> list[list[str]]:
    out = subprocess.run(["psql", "-X", "-At", "-F", SEP, "-d", db, "-c", sql],
                         capture_output=True, text=True, check=True).stdout
    return [line.split(SEP) for line in out.splitlines() if line]


def load(db: str):
    tables = {r[0]: r[1] for r in q(db, """
        select c.relname, coalesce(obj_description(c.oid, 'pg_class'), '')
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relkind = 'r' and c.relname <> 'flyway_schema_history'""")}
    cols = defaultdict(list)
    domain_of = {(r["table"], r["column"]): r["domain"] for r in read_csv(ROOT / "erd/domain_columns.csv")}
    for t, name, typ, notnull, default, comment, generated in q(db, """
        select c.relname, a.attname, format_type(a.atttypid, a.atttypmod),
               a.attnotnull::text, coalesce(pg_get_expr(d.adbin, d.adrelid), ''),
               coalesce(col_description(c.oid, a.attnum), ''),
               a.attgenerated
        from pg_attribute a
        join pg_class c on c.oid = a.attrelid
        join pg_namespace n on n.oid = c.relnamespace
        left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
        where n.nspname = 'public' and c.relkind = 'r' and a.attnum > 0 and not a.attisdropped
          and c.relname <> 'flyway_schema_history'
        order by c.relname, a.attnum"""):
        if generated == "s":
            default = "GENERATED: " + default
        cols[t].append({"name": name, "type": typ, "nn": notnull == "true", "default": default,
                        "comment": comment, "domain": domain_of.get((t, name), "")})
    pk = defaultdict(list)
    for t, col in q(db, """
        select tc.table_name, kcu.column_name from information_schema.table_constraints tc
        join information_schema.key_column_usage kcu on kcu.constraint_name = tc.constraint_name
             and kcu.table_name = tc.table_name
        where tc.constraint_type = 'PRIMARY KEY' and tc.table_schema = 'public'
        order by tc.table_name, kcu.ordinal_position"""):
        pk[t].append(col)
    uniques = defaultdict(list)
    bizkey = {}  # 복합 업무키 (uq_<표>_key). 물리 PK는 대리키 id
    for t, cons, colnames in q(db, """
        select c.relname, con.conname,
               (select string_agg(a.attname, ',' order by k.ord) from unnest(con.conkey) with ordinality k(n, ord)
                join pg_attribute a on a.attrelid = con.conrelid and a.attnum = k.n)
        from pg_constraint con join pg_class c on c.oid = con.conrelid
        where con.contype = 'u' and c.relnamespace = 'public'::regnamespace"""):
        uniques[t].append(colnames.split(","))
        if cons == f"uq_{t}_key":
            bizkey[t] = colnames.split(",")
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
    domains = [(r["domain"], r["base_type"], r["check"], r["description"])
               for r in read_csv(ROOT / "erd/domains.csv")]
    # 논리 식별자: 업무키가 있으면 업무키, 없으면 PK (대리키 id는 물리 설계에서 추가한 것)
    lkey = {t: bizkey.get(t, pk[t]) for t in tables}
    return tables, cols, pk, uniques, fks, checks, domains, lkey


ACTIONS = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}


def logical_name(comment: str) -> tuple[str, str]:
    if ":" in comment:
        a, b = comment.split(":", 1)
        return a.strip(), b.strip()
    return "", comment.strip()


def is_identifying(fk: dict, lkey: dict) -> bool:
    """부모 키가 자식의 논리 식별자(업무키)에 포함되면 식별 관계"""
    return set(fk["cols"]) <= set(lkey[fk["child"]])


def is_surrogate(t: str, c: dict, pk: dict, lkey: dict) -> bool:
    return pk[t] == [c["name"]] and lkey[t] != pk[t]


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
            # DB와 같은 기본 자료형을 쓰고, 논리 도메인은 note에 남긴다
            typ = short_type(c["type"])
            if c["domain"]:
                attrs[-1] = attrs[-1][:-1] + f" [도메인 {c['domain']}]'"
            out.append(f"  {c['name']} {typ} [{', '.join(attrs)}]")
        idx = []
        if len(pk[t]) > 1:
            idx.append(f"    ({', '.join(pk[t])}) [pk]")
        idx += [f"    ({', '.join(u)}) [unique]" for u in uniques[t]]
        if idx:
            out += ["  indexes {", *idx, "  }"]
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
    t = c["domain"] or short_type(c["type"])
    return t.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "_")


def gen_mermaid(tables, cols, pk, uniques, fks, lkey) -> str:
    out = ["%% KBO 야구 기록 DB 논리 ERD — tools/gen_erd_docs.py 자동 생성",
           "%% 실선 = 식별 관계(부모 키가 자식 식별자에 포함), 점선 = 비식별 관계",
           "%% 논리 모델이므로 식별자는 업무키로 표시하고, 물리 설계에서 추가한 대리키 id는 생략한다(10장 테이블 기술서 참고)",
           "erDiagram"]
    fk_cols = defaultdict(set)
    for fk in fks:
        fk_cols[fk["child"]] |= set(fk["cols"])
    for fk in fks:
        parent_side = "|o" if any(not next(c for c in cols[fk["child"]] if c["name"] == x)["nn"] for x in fk["cols"]) else "||"
        child_side = "o|" if child_is_unique(fk, lkey, uniques) else "o{"
        line = "--" if is_identifying(fk, lkey) else ".."
        out.append(f"    {fk['parent']} {parent_side}{line}{child_side} {fk['child']} : \"{','.join(fk['cols'])}\"")
    for t in ORDER:
        out.append(f"    {t} {{")
        for c in cols[t]:
            if is_surrogate(t, c, pk, lkey):
                continue
            keys = []
            if c["name"] in lkey[t]:
                keys.append("PK")
            if c["name"] in fk_cols[t]:
                keys.append("FK")
            ln, _ = logical_name(c["comment"])
            out.append(f"        {mermaid_type(c)} {c['name']} {','.join(keys)} \"{ln}\"".replace("  \"", " \""))
        out.append("    }")
    return "\n".join(out) + "\n"


def gen_table_spec(tables, cols, pk, uniques, fks, checks, lkey) -> str:
    out = ["# 10. 테이블 기술서", "",
           "> `tools/gen_erd_docs.py` 가 PostgreSQL 카탈로그(컬럼 COMMENT·제약조건)에서 자동 생성했다.",
           "> 내용을 고칠 때는 새 Flyway 마이그레이션(V{n}__*.sql)에서 COMMENT ON 을 고친 뒤 다시 생성한다.",
           "> Data Type 괄호 안은 논리 도메인(보고서 9장). DB에는 기본 자료형 + CHECK 로 들어가 있다.", ""]
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
            if lkey[t] != pk[t] and c["name"] in lkey[t]:
                key.append("UQ(업무키)")
            elif any(c["name"] in u for u in uniques[t]):
                key.append("UQ")
            ln, d = logical_name(c["comment"])
            typ = f"{short_type(c['type'])} ({c['domain']})" if c["domain"] else short_type(c["type"])
            dflt = c["default"].replace("|", "\\|")
            out.append(f"| {c['name']} | {ln} | {typ} | {'Y' if c['nn'] else ''} | {', '.join(key)} | {dflt} | {d} |")
        rel = [fk for fk in fks if fk["child"] == t]
        if rel:
            out += ["", "**참조 무결성 (FK)**", ""]
            out += [f"- `{fk['name']}`: ({', '.join(fk['cols'])}) → {fk['parent']}({', '.join(fk['pcols'])}) "
                    f"ON UPDATE {fk['upd']} ON DELETE {fk['del']}"
                    + (" — 식별 관계" if is_identifying(fk, lkey) else " — 비식별 관계") for fk in rel]
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
                used[c["domain"]].append(f"{t}.{c['name']}")
    out = ["# 9-부록. 도메인별 사용 컬럼 (자동 생성)", "",
           "> 논리 도메인은 `erd/domains.csv`, 사용 컬럼은 `erd/domain_columns.csv`. DB에는 DOMAIN 타입 대신",
           "> 기본 자료형 + 컬럼 CHECK 로 구현했다(JPA `ddl-auto: validate` 호환). FK 컬럼은 부모 키가 값을 보장하므로 CHECK를 생략.",
           "", "| 도메인 | 기본 자료형 | 제약 (VALUE = 컬럼 값) | 설명 | 사용 컬럼 |", "|---|---|---|---|---|"]
    for name, base, cons, comment in domains:
        out.append(f"| {name} | {base} | `CHECK ({cons})` | {comment} | {', '.join(used[name])} |")
    return "\n".join(out) + "\n"


def gen_terms(cols) -> str:
    """같은 논리명이 여러 테이블에 나오면 한 줄로 묶는다 (물리명·도메인이 다르면 경고 표시)"""
    terms: dict[str, dict] = {}
    for t in ORDER:
        for c in cols[t]:
            ln, desc = logical_name(c["comment"])
            if not ln:
                continue
            e = terms.setdefault(ln, {"phys": set(), "types": set(), "desc": desc, "tables": []})
            e["phys"].add(c["name"])
            e["types"].add(c["domain"] or short_type(c["type"]))
            e["tables"].append(t)
    out = ["# 8-부록. 표준 용어 목록 (자동 생성)", "",
           "> 컬럼 COMMENT의 '논리명'을 모은 것. 같은 논리명에 물리명이나 자료형이 둘 이상이면 ⚠️ 표시 → 통일 검토",
           "", "| 논리명(용어) | 물리명 | 도메인/자료형 | 설명(대표) | 사용 테이블 |", "|---|---|---|---|---|"]
    for ln in sorted(terms):
        e = terms[ln]
        # 경기 단위(d_count)·시즌 누적(d_total)은 같은 의미의 다른 집계 수준이라 경고하지 않는다
        types = {"횟수" if x in ("d_count", "d_total") else x for x in e["types"]}
        warn = " ⚠️" if len(e["phys"]) > 1 or len(types) > 1 else ""
        out.append(f"| {ln}{warn} | {', '.join(sorted(e['phys']))} | {', '.join(sorted(e['types']))} | "
                   f"{e['desc']} | {', '.join(dict.fromkeys(e['tables']))} |")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="kbo")
    args = ap.parse_args()
    tables, cols, pk, uniques, fks, checks, domains, lkey = load(args.db)
    missing = set(tables) ^ set(ORDER)
    if missing:
        raise SystemExit(f"ORDER 목록과 DB 테이블이 다름: {missing}")
    (ROOT / "erd/kbo_erd.dbml").write_text(gen_dbml(tables, cols, pk, uniques, fks), encoding="utf-8")
    (ROOT / "erd/erd_logical.mmd").write_text(gen_mermaid(tables, cols, pk, uniques, fks, lkey), encoding="utf-8")
    (ROOT / "docs/report").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/report/10_table_spec.md").write_text(gen_table_spec(tables, cols, pk, uniques, fks, checks, lkey),
                                                       encoding="utf-8")
    (ROOT / "docs/report/09_domain_usage.md").write_text(gen_domain_usage(cols, domains), encoding="utf-8")
    (ROOT / "docs/report/08_glossary_terms.md").write_text(gen_terms(cols), encoding="utf-8")
    print(f"테이블 {len(tables)}개, FK {len(fks)}개 → erd/kbo_erd.dbml, erd/erd_logical.mmd, "
          "docs/report/10_table_spec.md, 09_domain_usage.md, 08_glossary_terms.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
