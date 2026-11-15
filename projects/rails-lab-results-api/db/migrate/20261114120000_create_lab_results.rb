class CreateLabResults < ActiveRecord::Migration[8.1]
  def change
    create_table :lab_results do |t|
      t.string :sample_id, null: false
      t.string :assay, null: false
      t.string :analyte, null: false
      t.float :value, null: false
      t.string :unit, null: false
      t.integer :revision, null: false, default: 1
      t.timestamps
    end

    add_index :lab_results, :sample_id
  end
end
