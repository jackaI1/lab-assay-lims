module Api
  class LabResultsController < ApplicationController
    def index
      results = LabResult.order(:id)
      results = results.where(sample_id: params[:sample_id]) if params[:sample_id].present?
      render json: results.map { |result| serialize(result) }
    end

    def show
      render json: serialize(LabResult.find(params[:id]))
    end

    def create
      result = LabResult.record!(result_params)
      render json: serialize(result), status: :created
    rescue ActiveRecord::RecordInvalid => e
      render_validation_errors(e.record)
    end

    def update
      result = LabResult.find(params[:id])
      expected = Integer(params[:revision], exception: false)
      if expected.nil?
        return render json: { error: "revision_required",
                              message: "send the revision you are correcting" },
                      status: :unprocessable_content
      end

      result.correct!(result_params, expected_revision: expected)
      render json: serialize(result)
    rescue LabResult::RevisionConflict => e
      render json: { error: "revision_conflict", current_revision: e.current_revision },
             status: :conflict
    rescue ActiveRecord::RecordInvalid => e
      render_validation_errors(e.record)
    end

    def audit_events
      result = LabResult.find(params[:id])
      render json: result.audit_events.map { |event| serialize_event(event) }
    end

    private

    def result_params
      params.expect(lab_result: %i[sample_id assay analyte value unit])
    end

    def serialize(result)
      result.saved_fields.merge("id" => result.id, "revision" => result.revision)
    end

    def serialize_event(event)
      { id: event.id, action: event.action, revision: event.revision,
        details: event.details, created_at: event.created_at }
    end
  end
end
