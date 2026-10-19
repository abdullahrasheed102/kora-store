-- Runs once, the first time the Postgres volume is created.
-- Tests get their own database so they can create and drop tables without touching dev data.
CREATE DATABASE kora_test OWNER kora;
