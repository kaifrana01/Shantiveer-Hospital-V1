from django import template
from core import rbac

register = template.Library()


@register.filter
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


@register.filter
def has_perm(user, perm_name):
    return user.has_perm(perm_name)


@register.filter
def get_item(d, key):
    """Look up a value in a dict by key from within a template."""
    try:
        return d.get(key)
    except AttributeError:
        return None


@register.filter
def can_view(user, module_key):
    """True if user has at least view access to module_key."""
    return rbac.has_access(user, module_key, level=rbac.VIEW)


@register.filter
def can_edit(user, module_key):
    """True if user has full (edit) access to module_key."""
    return rbac.has_access(user, module_key, level=rbac.FULL)
