from django.urls import path
from . import views

app_name = 'pharmacy'

urlpatterns = [
    path('', views.items, name='items'),
    path('purchase/', views.purchase, name='purchase'),
    path('sale/', views.sale, name='sale'),
    path('sale-purchase/', views.sale_purchase, name='sale_purchase'),
]
