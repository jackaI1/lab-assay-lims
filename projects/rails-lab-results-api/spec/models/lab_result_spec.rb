require "rails_helper"

RSpec.describe LabResult, type: :model do
  let(:valid_attributes) do
    { sample_id: "S-001", assay: "ELISA", analyte: "IL-6", value: 7.5, unit: "ng/mL" }
  end

  describe "validations" do
    it "accepts a complete result" do
      expect(LabResult.new(valid_attributes)).to be_valid
    end

    it "rejects a missing sample ID" do
      result = LabResult.new(valid_attributes.merge(sample_id: ""))
      expect(result).not_to be_valid
      expect(result.errors[:sample_id]).to be_present
    end

    it "rejects a sample ID with spaces or punctuation" do
      expect(LabResult.new(valid_attributes.merge(sample_id: "S 001;drop"))).not_to be_valid
    end

    it "rejects a negative value" do
      expect(LabResult.new(valid_attributes.merge(value: -0.1))).not_to be_valid
    end

    it "rejects a value that is not a number" do
      expect(LabResult.new(valid_attributes.merge(value: "seven"))).not_to be_valid
    end

    it "rejects an infinite value" do
      expect(LabResult.new(valid_attributes.merge(value: Float::INFINITY))).not_to be_valid
    end

    it "rejects a unit that is not on the allowed list" do
      result = LabResult.new(valid_attributes.merge(unit: "furlongs"))
      expect(result).not_to be_valid
      expect(result.errors[:unit]).to be_present
    end
  end

  describe ".record!" do
    it "saves revision 1 and one created audit event with the entered values" do
      result = LabResult.record!(valid_attributes)

      expect(result.revision).to eq(1)
      expect(result.audit_events.count).to eq(1)
      event = result.audit_events.first
      expect(event.action).to eq("created")
      expect(event.revision).to eq(1)
      expect(event.details["after"]).to include("sample_id" => "S-001", "value" => 7.5)
    end

    it "saves nothing when the input is invalid" do
      expect { LabResult.record!(valid_attributes.merge(unit: "bad")) }
        .to raise_error(ActiveRecord::RecordInvalid)
      expect(LabResult.count).to eq(0)
      expect(AuditEvent.count).to eq(0)
    end
  end

  describe "#correct!" do
    let!(:result) { LabResult.record!(valid_attributes) }

    it "increments the revision and records only the fields that changed" do
      result.correct!({ value: 8.0 }, expected_revision: 1)

      expect(result.reload.revision).to eq(2)
      expect(result.value).to eq(8.0)
      latest = result.audit_events.last
      expect(latest.action).to eq("corrected")
      expect(latest.revision).to eq(2)
      expect(latest.details).to eq("before" => { "value" => 7.5 }, "after" => { "value" => 8.0 })
    end

    it "keeps the earlier audit events in order" do
      result.correct!({ value: 8.0 }, expected_revision: 1)
      result.correct!({ value: 8.5 }, expected_revision: 2)

      expect(result.audit_events.map(&:action)).to eq(%w[created corrected corrected])
      expect(result.audit_events.map(&:revision)).to eq([1, 2, 3])
    end

    it "rejects a stale revision and leaves the result and history unchanged" do
      result.correct!({ value: 8.0 }, expected_revision: 1)

      expect { result.correct!({ value: 9.0 }, expected_revision: 1) }
        .to raise_error(LabResult::RevisionConflict) { |error| expect(error.current_revision).to eq(2) }

      result.reload
      expect(result.value).to eq(8.0)
      expect(result.revision).to eq(2)
      expect(result.audit_events.count).to eq(2)
    end

    it "rolls back a correction that fails validation" do
      expect { result.correct!({ unit: "furlongs" }, expected_revision: 1) }
        .to raise_error(ActiveRecord::RecordInvalid)

      result.reload
      expect(result.unit).to eq("ng/mL")
      expect(result.revision).to eq(1)
      expect(result.audit_events.count).to eq(1)
    end

    it "does nothing when the values are unchanged" do
      result.correct!({ value: 7.5 }, expected_revision: 1)

      expect(result.reload.revision).to eq(1)
      expect(result.audit_events.count).to eq(1)
    end
  end
end
