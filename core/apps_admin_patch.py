from django.contrib.admin.sites import AdminSite


def patch_admin_site(site: AdminSite):
    """No-op placeholder.

    Left here so we can safely import/extend later if needed.
    """
    return site

