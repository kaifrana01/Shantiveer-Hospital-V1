from django.urls import path
from . import views

app_name = 'lab'

urlpatterns = [
    path('', views.investigation, name='investigation'),

    # Patient discovery (auto-fill) helpers
    path('patient/lookup/', views.patient_lookup, name='patient_lookup'),

    path('view-all/', views.view_all, name='view_all'),
    path('report/<int:pk>/', views.view_report, name='view_report'),
    path('report/<int:pk>/print/', views.view_report_print, name='view_report_print'),
    path('patient-list/', views.patient_list, name='patient_list'),

    path('tests/', views.test_list, name='test_list'),

    path('tests/add/', views.test_add, name='test_add'),
    path('tests/<int:pk>/edit/', views.test_edit, name='test_edit'),
    path('tests/<int:pk>/toggle/', views.test_toggle, name='test_toggle'),
]


