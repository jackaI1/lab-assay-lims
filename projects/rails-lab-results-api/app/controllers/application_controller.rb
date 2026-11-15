class ApplicationController < ActionController::API
  rescue_from ActiveRecord::RecordNotFound do
    render json: { error: "not_found" }, status: :not_found
  end

  private

  def render_validation_errors(record)
    render json: { error: "validation_failed", details: record.errors.as_json },
           status: :unprocessable_content
  end
end
