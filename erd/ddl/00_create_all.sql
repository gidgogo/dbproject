-- =====================================================================
-- 전체 스키마를 한 번에 만든다 (레포 최상위 폴더에서 실행)
--   createdb kbo
--   psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/00_create_all.sql
-- 다시 만들 때는 erd/ddl/99_drop_all.sql 을 먼저 실행한다.
-- =====================================================================
\set ON_ERROR_STOP on
\i erd/ddl/01_domains.sql
\i erd/ddl/02_tables.sql
\i erd/ddl/03_indexes.sql
\i erd/ddl/04_triggers.sql
\i erd/ddl/05_views.sql
\i erd/ddl/06_reference_data.sql
