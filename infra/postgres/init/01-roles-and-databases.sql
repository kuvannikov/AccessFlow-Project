\getenv owner_password ACCESSFLOW_OWNER_PASSWORD
\getenv app_password ACCESSFLOW_APP_PASSWORD
\getenv keycloak_password KEYCLOAK_DB_PASSWORD

CREATE ROLE accessflow_owner LOGIN PASSWORD :'owner_password';
CREATE ROLE accessflow_app LOGIN PASSWORD :'app_password';
CREATE ROLE keycloak LOGIN PASSWORD :'keycloak_password';

CREATE DATABASE accessflow OWNER accessflow_owner;
CREATE DATABASE keycloak OWNER keycloak;

REVOKE CONNECT ON DATABASE accessflow FROM PUBLIC;
REVOKE CONNECT ON DATABASE keycloak FROM PUBLIC;
GRANT CONNECT ON DATABASE accessflow TO accessflow_app;

\connect accessflow

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO accessflow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE accessflow_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO accessflow_app;
