# The audit table is append-only. Every saved change to a lab result adds one row here,
# and SQLite triggers reject any UPDATE or DELETE, even one made outside Rails.
class CreateAuditEvents < ActiveRecord::Migration[8.1]
  def up
    create_table :audit_events do |t|
      t.references :lab_result, null: false, foreign_key: true
      t.string :action, null: false
      t.integer :revision, null: false
      t.json :details, null: false
      t.datetime :created_at, null: false, default: -> { "CURRENT_TIMESTAMP" }
    end

    add_index :audit_events, %i[lab_result_id id]

    execute <<~SQL
      CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events
      BEGIN
        SELECT RAISE(ABORT, 'audit_events is append-only');
      END;
    SQL

    execute <<~SQL
      CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events
      BEGIN
        SELECT RAISE(ABORT, 'audit_events is append-only');
      END;
    SQL
  end

  def down
    execute "DROP TRIGGER IF EXISTS audit_events_no_delete"
    execute "DROP TRIGGER IF EXISTS audit_events_no_update"
    drop_table :audit_events
  end
end
