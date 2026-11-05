# KBO 야구 기록 DB — 데이터베이스응용 텀프로젝트

KBO 경기 기록과 선수 통계를 관리하는 PostgreSQL 데이터베이스입니다. 구현 범위는 다섯 화면이에요.
경기 결과, 선수 프로필·비교, 팀 프로필, 순위, Savant식 시각화를 지원합니다.
백엔드는 Spring(김경주), 데이터 전처리는 배인표, ERD 설계와 추가 크롤링은 이성수 담당입니다.

이 브랜치에는 **이성수 담당 작업**(ERD·DDL, 크롤러, 보고서 데이터 모델 파트)이 들어 있습니다.

## 폴더 구조

| 폴더 | 내용 |
|---|---|
| `erd/` | ERD 그림(`img/`), DBML(dbdiagram.io), Mermaid, **PostgreSQL DDL**(`ddl/`) |
| `crawl/` | 크롤러: KBO 기록실·선수 상세·순위, 네이버 문자중계, kbodata 보정 패치 → [crawl/README.md](crawl/README.md) |
| `etl/` | 수집 결과 → DB 적재용 CSV 변환 (kbodata 변환은 배인표 작업의 참고 구현) |
| `data/` | `reference/` 기준 데이터(팀·팀시즌·구장·타석결과코드·구종), 크롤링 결과 CSV (`raw/`, `load/`는 git 제외) |
| `docs/` | 보고서 초안(`report/`), 사이트 구조·네이버 필드 정리, 메일, 회의 안건, 인수인계 |
| `tools/` | ERD·테이블 기술서 자동 생성, ERD 그림 렌더링, 성능 확인 SQL |
| `tests/` | pytest: 파서·변환기·DB 통합 테스트 (가상 데이터) |

## 빠른 시작

DB 만들기 (레포 최상위 폴더에서):

```bash
createdb kbo
```

```bash
psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/00_create_all.sql
```

테스트 (PostgreSQL 접속 정보는 `PGHOST`/`PGPORT`/`PGUSER` 환경변수):

```bash
python -m pytest tests -q
```

크롤링·적재 순서는 [crawl/README.md](crawl/README.md) 에 있습니다.

## 산출물 현황 (2026-11-05)

| 작업지시서 항목 | 산출물 | 상태 |
|---|---|---|
| 2-0 교수님 문의 | [docs/email_professor.md](docs/email_professor.md) | 메일 발송은 성수가 직접 |
| 2-1 ERD | [개념 ERD](erd/img/erd_conceptual.png) · [논리 ERD](erd/img/erd_logical.svg) · [DBML](erd/kbo_erd.dbml) · [DDL](erd/ddl/) | ✅ v0 (PostgreSQL 16 테스트 통과) · 🟡 11/10 확정 |
| 2-1 뷰 | 시즌 타자(타율·출루율·장타율·OPS)·투수(ERA·WHIP)·팀 순위 MV + 시각화·검증 뷰 | ✅ |
| 2-2 playerId·선수 상세 | `crawl/kbo_records.py`, `crawl/kbo_profiles.py`, 매핑 검증 `etl/kbodata_to_tables.py --check-only` | ✅ 코드 · ⏳ 맥에서 수집 |
| 2-3 기록실 시즌 기록·순위 | `crawl/kbo_records.py`, `crawl/kbo_team_rank.py`, 비교 뷰 `v_compare_*` | ✅ 코드 · ⏳ 수집 |
| 2-4 네이버 문자중계 | [docs/naver_relay_fields.md](docs/naver_relay_fields.md), `crawl/naver_probe.py`, `crawl/naver_relay.py` | ✅ 코드·문서 · ⏳ 실측 |
| 보고서 5~10장 | [docs/report/](docs/report/) | 🟡 초안 |
| 11/10 회의 | [docs/meeting_1110_agenda.md](docs/meeting_1110_agenda.md) | ✅ |
| 인수인계 | [백엔드(김경주)](docs/handoff/backend_kimkyungju.md) · [전처리(배인표)](docs/handoff/preprocessing_baeinpyo.md) | ✅ |

## 확인이 필요한 것 (❓)

클라우드 환경에서는 koreabaseball.com과 네이버에 접속할 수 없었습니다. 그래서 페이지 구조는 실제로 그 사이트를 크롤링하는
공개 오픈소스 코드로 확인하고([docs/kbo_site_structure.md](docs/kbo_site_structure.md)), 맥에서 다시 확인하는
probe 스크립트를 만들었습니다. 수집 전에 `crawl/probe_kbo.py`, `crawl/naver_probe.py`부터 실행하세요.

## 데이터 출처

- KBO 공식 홈페이지 (www.koreabaseball.com) — 경기·선수 기록
- kbo-data (GitHub dev-bearabbit/kbo-data, MIT License) — 박스스코어 수집 도구.
  `data/reference/kbodata_batter_codes.ini` 는 이 도구의 결과 코드표 발췌 (라이선스: `data/reference/LICENSE.kbodata`)
- 네이버 스포츠 문자중계 — 투구 데이터
- 데이터는 수업 프로젝트 용도로만 사용합니다.
