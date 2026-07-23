from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.views.generic import RedirectView
from django.contrib import admin

import core.admin_site
from core.admin_api import admin_stats, admin_logs, admin_users, admin_tests

urlpatterns = [
    path('admin/', admin.site.urls),
    # Admin dashboard JSON widgets
    path('admin/hms-stats/', admin_stats, name='admin_hms_stats'),
    path('admin/hms-logs/',  admin_logs,  name='admin_hms_logs'),
    path('admin/hms-users/', admin_users, name='admin_hms_users'),
    path('admin/hms-tests/', admin_tests, name='admin_hms_tests'),
    path('', RedirectView.as_view(pattern_name='accounts:login', permanent=False)),
    path('', include('accounts.urls')),
    path('', include('core.urls')),
    path('opd/', include('opd.urls')),
    path('ipd/', include('ipd.urls')),
    path('lab/', include('lab.urls')),
    path('ultrasound/', include('ultrasound.urls')),
    path('pharmacy/', include('pharmacy.urls')),
    path('prescription/', include('prescription.urls')),
    path('uhid/', include('uhid.urls')),
    path('master/', include('masterdata.urls')),
    path('income/', include('income.urls')),
    path('expenses/', include('expenses.urls')),
    path('history/', include('history.urls')),
    path('api/', include('core.api_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = 'ShantiVeer HMS Admin'
