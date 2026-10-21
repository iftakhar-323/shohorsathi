-- One database per service. Add a line here when a new service is introduced.
-- (Runs only when the Postgres volume is first created; for an existing volume run the new lines by hand.)
CREATE DATABASE auth_db;
CREATE DATABASE catalog_db;
CREATE DATABASE order_db;
CREATE DATABASE provider_db;
CREATE DATABASE custom_request_db;
CREATE DATABASE media_db;
