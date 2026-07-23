from django.urls import path
from . import views

app_name = 'uhid'

urlpatterns = [
    path('', views.update, name='update'),
    path('uhid-update/', views.update, name='uhid_update'),
]
