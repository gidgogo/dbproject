-- 기존 DB에 검토 수정본 뷰를 적용한다. 원본 테이블·수집 데이터는 보존한다.
-- psql -d kbo -v ON_ERROR_STOP=1 -f erd/ddl/09_upgrade_views.sql
-- 외부에서 추가한 종속 뷰가 있으면 CASCADE로 지우지 않고 전체 작업을 롤백한다.
\set ON_ERROR_STOP on
BEGIN;
\ir includes/rebuild_views.sql
COMMIT;
