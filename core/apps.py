import os
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # On Vercel, /var/task is read-only. Ensure /tmp/media exists so that
        # file uploads (IPD documents, ultrasound reports, etc.) don't crash
        # with [Errno 30] Read-only file system.
        from django.conf import settings
        media_root = str(getattr(settings, 'MEDIA_ROOT', ''))
        if media_root and not os.path.exists(media_root):
            try:
                os.makedirs(media_root, exist_ok=True)
            except OSError:
                pass
