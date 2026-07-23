from django.urls import path
from . import api_views

app_name = 'api'

urlpatterns = [
    path('dashboard/', api_views.dashboard_stats, name='dashboard_stats'),
    path('dashboard/income-breakdown/', api_views.dashboard_income_breakdown, name='dashboard_income_breakdown'),
    path('patients/search/', api_views.patient_search, name='patient_search'),
    path('uhid/<str:uhid>/', api_views.uhid_lookup, name='uhid_lookup'),

    # Basic heuristic AI endpoints
    path('ai/triage/', api_views.ai_triage, name='ai_triage'),
    path('ai/prescription-summary/', api_views.ai_prescription_summary, name='ai_prescription_summary'),
    path('ai/inventory-reorder/', api_views.ai_inventory_reorder, name='ai_inventory_reorder'),
    path('ai/lab-recommend/', api_views.ai_lab_recommend, name='ai_lab_recommend'),
]

