-- KBO 프로필·공식 시즌 기록·순위만 적재. 경기 CSV 없이 실행 가능.
-- 먼저 python etl/crawl_to_tables.py 실행. 레포 루트에서 이 파일 실행.
\set ON_ERROR_STOP on
BEGIN;
\ir includes/load_kbo.sql
COMMIT;
