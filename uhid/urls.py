from django.urls import path
from . import views

app_name = 'uhid'

urlpatterns = [
    path('',                    views.update,          name='update'),
    path('uhid-update/',        views.update,          name='uhid_update'),
    path('register/',           views.register,        name='register'),
    path('edit/<str:uhid>/',    views.edit,            name='edit'),
    path('profile/<str:uhid>/', views.patient_profile, name='patient_profile'),
    path('api/search/',         views.patient_search_api, name='patient_search_api'),
]
