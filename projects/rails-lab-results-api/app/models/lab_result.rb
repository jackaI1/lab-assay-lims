# A validated lab result. Saved results are never overwritten: a correction must quote the
# revision it is based on, and each change adds one AuditEvent in the same transaction.
class LabResult < ApplicationRecord
  class RevisionConflict < StandardError
    attr_reader :current_revision

    def initialize(current_revision)
      @current_revision = current_revision
      super("the result is at revision #{current_revision}; reload it and correct that revision")
    end
  end

  ALLOWED_UNITS = %w[ng/mL ug/mL mg/L pg/mL mmol/L].freeze
  EDITABLE_FIELDS = %w[sample_id assay analyte value unit].freeze

  has_many :audit_events, -> { order(:id) }, dependent: :restrict_with_exception

  validates :sample_id, presence: true,
                        format: { with: /\A[A-Za-z0-9_-]{1,40}\z/,
                                  message: "may use letters, digits, '-' and '_' (up to 40 characters)" }
  validates :assay, :analyte, presence: true, length: { maximum: 60 }
  validates :unit, inclusion: { in: ALLOWED_UNITS }
  validates :value, numericality: { greater_than_or_equal_to: 0, less_than: 1_000_000 }
  validates :revision, numericality: { only_integer: true, greater_than: 0 }

  # Creates revision 1 and records a "created" event with the values as entered.
  def self.record!(attributes)
    transaction do
      result = create!(attributes.to_h.merge(revision: 1))
      result.audit_events.create!(action: "created", revision: 1,
                                  details: { after: result.saved_fields })
      result
    end
  end

  # Applies a correction only if expected_revision is still the current revision.
  # Unchanged values are a no-op: no new revision and no new audit event.
  def correct!(attributes, expected_revision:)
    transaction do
      lock!
      raise RevisionConflict.new(revision) unless revision == Integer(expected_revision)

      assign_attributes(attributes.to_h.stringify_keys.slice(*EDITABLE_FIELDS))
      diff = changes
      next self if diff.empty?

      details = { before: diff.transform_values(&:first), after: diff.transform_values(&:last) }
      self.revision += 1
      save!
      audit_events.create!(action: "corrected", revision: revision, details: details)
      self
    end
  end

  def saved_fields
    attributes.slice(*EDITABLE_FIELDS)
  end
end
