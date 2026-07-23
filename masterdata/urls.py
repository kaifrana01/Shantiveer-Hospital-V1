from django.urls import path
from . import views

app_name = 'masterdata'

urlpatterns = [
    path('', views.interpretation, name='interpretation'),
    path('inves-interpretation/', views.interpretation, name='inves_interpretation'),
    path('doctors/add/', views.doctors, name='doctors'),
    path('doctors/', views.doctor_list, name='doctor_list'),
]
