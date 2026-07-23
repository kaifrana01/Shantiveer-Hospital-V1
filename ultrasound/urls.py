from django.urls import path
from . import views

app_name = 'ultrasound'

urlpatterns = [
    # Dashboard — completely separate from main HMS dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Billing
    path('bill/', views.ultrasound_investigation, name='ultrasound_investigation'),
    path('bills/', views.patient_list, name='patient_list'),
    path('bill/<int:pk>/', views.ultrasound_view_report, name='ultrasound_view_report'),

    # Expenses
    path('expenses/', views.expenses, name='expenses'),

    # Test master
    path('tests/', views.test_list, name='test_list'),
    path('tests/add/', views.test_add, name='test_add'),
    path('tests/<int:pk>/edit/', views.test_edit, name='test_edit'),
    path('tests/<int:pk>/toggle/', views.test_toggle, name='test_toggle'),

    # Legacy redirects from old URL names (keep backward compat)
    path('', views.patient_list, name='ultrasound_view_all'),
    path('report/<int:pk>/', views.ultrasound_view_report, name='ultrasound_view_report_legacy'),
]
