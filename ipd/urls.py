from django.urls import path
from . import views

app_name = 'ipd'

urlpatterns = [
    path('', views.patient_list, name='patient_list'),
    path('admission/', views.admission, name='admission'),
    path('payment/', views.payment, name='payment'),
    path('payment/total/', views.payment_total, name='payment_total'),
    path('payment/<int:pk>/delete/', views.payment_delete, name='payment_delete'),
    path('bill/', views.bill, name='bill'),
    path('discharge/', views.discharge_list, name='discharge_list'),
    path('discharge/add/', views.discharge_add, name='discharge_add'),
    path('discharge/<int:pk>/print/', views.discharge_print, name='discharge_print'),
    path('medicine/', views.medicine, name='medicine'),
    path('medicine/<int:pk>/delete/', views.medicine_delete, name='medicine_delete'),
    path('delete/<int:pk>/', views.delete_patient, name='delete_patient'),
    path('admission/beds/', views.admission_beds, name='admission_beds'),
]
