from django.urls import path

from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.expenses_page, name='page'),
    path('<int:pk>/delete/', views.expense_delete, name='delete'),
]

