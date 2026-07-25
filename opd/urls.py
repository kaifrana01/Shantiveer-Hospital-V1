from django.urls import path
from . import views

app_name = 'opd'

urlpatterns = [
    path('registration/', views.registration, name='registration'),
    path('opd_dashboard/', views.registration, name='dashboard'),
    path('patient-list/', views.patient_list, name='patient_list'),
    path('delete/<int:pk>/', views.delete_opd_visit, name='delete_opd_visit'),
]

