from django.urls import path
from . import views

app_name = 'prescription'

urlpatterns = [
    path('', views.list_view, name='list'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/print/', views.print_view, name='print'),
    path('dispense/<int:line_id>/', views.dispense_medicine, name='dispense'),
]
