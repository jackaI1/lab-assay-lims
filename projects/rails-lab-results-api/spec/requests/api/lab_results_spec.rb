require "rails_helper"

RSpec.describe "Api::LabResults", type: :request do
  let(:payload) do
    { lab_result: { sample_id: "S-200", assay: "ELISA", analyte: "IL-6", value: 12.0, unit: "ng/mL" } }
  end

  def json
    JSON.parse(response.body)
  end

  def create_result(overrides = {})
    post "/api/lab_results", params: payload.deep_merge(lab_result: overrides), as: :json
    expect(response).to have_http_status(:created)
    json
  end

  describe "POST /api/lab_results" do
    it "creates a valid result at revision 1" do
      post "/api/lab_results", params: payload, as: :json

      expect(response).to have_http_status(:created)
      expect(json).to include("sample_id" => "S-200", "value" => 12.0, "revision" => 1)
      expect(AuditEvent.where(action: "created").count).to eq(1)
    end

    it "rejects invalid input with 422 and per-field errors, and saves nothing" do
      post "/api/lab_results", params: { lab_result: payload[:lab_result].merge(value: -3, unit: "x") },
                               as: :json

      expect(response).to have_http_status(:unprocessable_content)
      expect(json["error"]).to eq("validation_failed")
      expect(json["details"].keys).to include("value", "unit")
      expect(LabResult.count).to eq(0)
      expect(AuditEvent.count).to eq(0)
    end

    it "refuses a body without the lab_result object and saves nothing" do
      post "/api/lab_results", params: { sample_id: "S-200" }, as: :json

      expect(response).to have_http_status(:unprocessable_content)
      expect(LabResult.count).to eq(0)
    end
  end

  describe "GET /api/lab_results" do
    it "lists results and filters by sample ID" do
      create_result(sample_id: "S-A")
      create_result(sample_id: "S-B")

      get "/api/lab_results", params: { sample_id: "S-B" }

      expect(response).to have_http_status(:ok)
      expect(json.map { |row| row["sample_id"] }).to eq(["S-B"])
    end
  end

  describe "GET /api/lab_results/:id" do
    it "returns the result" do
      id = create_result["id"]

      get "/api/lab_results/#{id}"

      expect(json).to include("id" => id, "revision" => 1)
    end

    it "returns 404 for an unknown result" do
      get "/api/lab_results/999999"

      expect(response).to have_http_status(:not_found)
      expect(json).to eq("error" => "not_found")
    end
  end

  describe "PATCH /api/lab_results/:id" do
    it "applies a correction made against the current revision" do
      id = create_result["id"]

      patch "/api/lab_results/#{id}", params: { revision: 1, lab_result: { value: 13.5 } }, as: :json

      expect(response).to have_http_status(:ok)
      expect(json).to include("value" => 13.5, "revision" => 2)
    end

    it "returns 409 with the current revision when the correction is based on an old revision" do
      id = create_result["id"]
      patch "/api/lab_results/#{id}", params: { revision: 1, lab_result: { value: 13.5 } }, as: :json

      patch "/api/lab_results/#{id}", params: { revision: 1, lab_result: { value: 99.0 } }, as: :json

      expect(response).to have_http_status(:conflict)
      expect(json).to eq("error" => "revision_conflict", "current_revision" => 2)
      expect(LabResult.find(id).value).to eq(13.5)
    end

    it "returns 422 when no revision is sent" do
      id = create_result["id"]

      patch "/api/lab_results/#{id}", params: { lab_result: { value: 13.5 } }, as: :json

      expect(response).to have_http_status(:unprocessable_content)
      expect(json["error"]).to eq("revision_required")
    end

    it "returns 422 for an invalid correction and does not bump the revision" do
      id = create_result["id"]

      patch "/api/lab_results/#{id}", params: { revision: 1, lab_result: { unit: "furlongs" } }, as: :json

      expect(response).to have_http_status(:unprocessable_content)
      expect(LabResult.find(id).revision).to eq(1)
    end
  end

  describe "GET /api/lab_results/:id/audit_events" do
    it "returns the history in the order it was written" do
      id = create_result["id"]
      patch "/api/lab_results/#{id}", params: { revision: 1, lab_result: { value: 13.5 } }, as: :json

      get "/api/lab_results/#{id}/audit_events"

      expect(response).to have_http_status(:ok)
      expect(json.map { |event| event["action"] }).to eq(%w[created corrected])
      expect(json.last["details"]).to eq("before" => { "value" => 12.0 }, "after" => { "value" => 13.5 })
    end
  end
end
