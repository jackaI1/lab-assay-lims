require "rails_helper"

RSpec.describe AuditEvent, type: :model do
  let!(:result) do
    LabResult.record!(sample_id: "S-100", assay: "ELISA", analyte: "TNF", value: 2.0, unit: "pg/mL")
  end
  let(:event) { result.audit_events.first }

  it "refuses to update a saved event in Rails" do
    expect { event.update!(action: "corrected") }.to raise_error(ActiveRecord::ReadOnlyRecord)
  end

  it "refuses to destroy a saved event in Rails" do
    expect { event.destroy! }.to raise_error(ActiveRecord::ReadOnlyRecord)
  end

  it "is also protected by the database when Rails is bypassed" do
    expect { AuditEvent.where(id: event.id).update_all(details: {}) }
      .to raise_error(ActiveRecord::StatementInvalid, /append-only/)
    expect { AuditEvent.where(id: event.id).delete_all }
      .to raise_error(ActiveRecord::StatementInvalid, /append-only/)
  end

  it "rejects an unknown action" do
    expect(AuditEvent.new(lab_result: result, action: "edited", revision: 1, details: { x: 1 }))
      .not_to be_valid
  end
end
