Rails.application.routes.draw do
  get "up" => "rails/health#show", as: :rails_health_check

  namespace :api do
    resources :lab_results, only: %i[index show create update] do
      get :audit_events, on: :member
    end
  end
end
