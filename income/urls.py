from django.urls import path
from . import views
from . import export as export_views

app_name = 'income'

urlpatterns = [
    path('', views.daybook, name='daybook'),
    path('daybook/', views.daybook, name='daybook_alt'),
    path('daybook/export/<str:selected_date>/', export_views.resolve_export, name='daybook_export'),
]

