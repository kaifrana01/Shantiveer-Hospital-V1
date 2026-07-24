from django.urls import path
from . import views

app_name = 'pharmacy'

urlpatterns = [
    path('', views.items, name='items'),
    path('items/<int:pk>/edit/', views.item_edit, name='item_edit'),
    path('items/<int:pk>/toggle/', views.item_toggle, name='item_toggle'),
    path('purchase/', views.purchase, name='purchase'),
    path('purchase/<int:pk>/delete/', views.purchase_delete, name='purchase_delete'),
    path('sale/', views.sale, name='sale'),
    path('sale/<int:pk>/delete/', views.sale_delete, name='sale_delete'),
    path('sale-purchase/', views.sale_purchase, name='sale_purchase'),
]
