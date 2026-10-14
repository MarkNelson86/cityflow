-- Optional pause: keep the data for a later session and prevent auto-resume.
USE ROLE ACCOUNTADMIN;
ALTER WAREHOUSE CITYFLOW_WH SUSPEND;
ALTER WAREHOUSE CITYFLOW_WH SET AUTO_RESUME = FALSE;
SHOW WAREHOUSES LIKE 'CITYFLOW_WH';

-- FINAL CLEANUP: only after saving evidence and deciding to end the cloud run.
-- Run each statement individually in Snowsight.
-- The databases are owned by CITYFLOW_ROLE.

-- USE ROLE CITYFLOW_ROLE;
-- DROP DATABASE CITYFLOW_FIXTURE;
-- DROP DATABASE CITYFLOW_REAL;

-- Switch to ACCOUNTADMIN before dropping the remaining objects and the role.
-- USE ROLE ACCOUNTADMIN;
-- DROP WAREHOUSE CITYFLOW_WH;
-- DROP RESOURCE MONITOR CITYFLOW_MONITOR;
-- DROP ROLE CITYFLOW_ROLE;

-- Run these after the drops to verify cleanup.
SHOW DATABASES LIKE 'CITYFLOW_%';
SHOW WAREHOUSES LIKE 'CITYFLOW_WH';
SHOW RESOURCE MONITORS LIKE 'CITYFLOW_MONITOR';
SHOW ROLES LIKE 'CITYFLOW_ROLE';
