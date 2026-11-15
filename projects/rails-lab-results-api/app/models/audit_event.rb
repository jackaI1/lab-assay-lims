# One row of history for a lab result. Rows are written once and never changed.
class AuditEvent < ApplicationRecord
  ACTIONS = %w[created corrected].freeze

  belongs_to :lab_result

  validates :action, inclusion: { in: ACTIONS }
  validates :revision, numericality: { only_integer: true, greater_than: 0 }
  validates :details, presence: true

  # Rails refuses to save or destroy a persisted row. The database triggers in the
  # migration are the backstop for any other route.
  def readonly?
    persisted? || super
  end
end
