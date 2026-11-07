-- KBO 프로필·공식 시즌 기록·순위만 적재. 경기 CSV 없이 실행 가능 (psql 스크립트, Flyway 아님).
-- 먼저 python etl/crawl_to_tables.py 실행. data-pipeline 폴더에서:
--   PGPASSWORD=kbo psql -h localhost -p 5434 -U kbo -d kbo -f sql/load_kbo.sql
-- 경기 기록을 바꾸지 않으므로 MV 갱신은 필요 없다.
\set ON_ERROR_STOP on
BEGIN;
\ir includes/load_kbo.sql
COMMIT;
