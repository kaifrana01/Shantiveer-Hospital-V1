from django.urls import path
from . import views

app_name = 'masterdata'

urlpatterns = [
    path('', views.interpretation, name='interpretation'),
    path('inves-interpretation/', views.interpretation, name='inves_interpretation'),
    path('interpretation/<int:pk>/edit/', views.interpretation_edit, name='interpretation_edit'),
    path('interpretation/<int:pk>/delete/', views.interpretation_delete, name='interpretation_delete'),
    
    path('doctors/add/', views.doctors, name='doctors'),
    path('doctors/', views.doctor_list, name='doctor_list'),
    path('doctors/<int:pk>/edit/', views.doctor_edit, name='doctor_edit'),
    path('doctors/<int:pk>/toggle/', views.doctor_toggle, name='doctor_toggle'),
]
