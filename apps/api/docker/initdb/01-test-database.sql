-- Runs once, when the db volume is first created. Tests use this database
-- so they never touch the development data in epl_scout.
CREATE DATABASE epl_scout_test OWNER scout;
