CREATE TABLE "schema_migrations" ("version" varchar NOT NULL PRIMARY KEY);
CREATE TABLE "ar_internal_metadata" ("key" varchar NOT NULL PRIMARY KEY, "value" varchar, "created_at" datetime(6) NOT NULL, "updated_at" datetime(6) NOT NULL);
CREATE TABLE "lab_results" ("id" integer PRIMARY KEY AUTOINCREMENT NOT NULL, "sample_id" varchar NOT NULL, "assay" varchar NOT NULL, "analyte" varchar NOT NULL, "value" float NOT NULL, "unit" varchar NOT NULL, "revision" integer DEFAULT 1 NOT NULL, "created_at" datetime(6) NOT NULL, "updated_at" datetime(6) NOT NULL);
CREATE INDEX "index_lab_results_on_sample_id" ON "lab_results" ("sample_id") /*application='RailsLabResultsApi'*/;
CREATE TABLE "audit_events" ("id" integer PRIMARY KEY AUTOINCREMENT NOT NULL, "lab_result_id" integer NOT NULL, "action" varchar NOT NULL, "revision" integer NOT NULL, "details" json NOT NULL, "created_at" datetime(6) DEFAULT CURRENT_TIMESTAMP NOT NULL, CONSTRAINT "fk_rails_705327318b"
FOREIGN KEY ("lab_result_id")
  REFERENCES "lab_results" ("id")
);
CREATE INDEX "index_audit_events_on_lab_result_id" ON "audit_events" ("lab_result_id") /*application='RailsLabResultsApi'*/;
CREATE INDEX "index_audit_events_on_lab_result_id_and_id" ON "audit_events" ("lab_result_id", "id") /*application='RailsLabResultsApi'*/;
CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events
BEGIN
  SELECT RAISE(ABORT, 'audit_events is append-only');
END;
CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events
BEGIN
  SELECT RAISE(ABORT, 'audit_events is append-only');
END;
INSERT INTO "schema_migrations" (version) VALUES
('20261114120100'),
('20261114120000');

