from django import template
from tasks.models import Developer, Supervisor, Notification
from django.utils.safestring import mark_safe
import json

register = template.Library()


@register.simple_tag
def developer_name(request):
    if Developer.objects.filter(user=request.user):
        return Developer.objects.get(user=request.user).get_name()
    elif Supervisor.objects.filter(user=request.user):
        return Supervisor.objects.get(user=request.user).get_name()

    return "No name"


@register.simple_tag
def developer_id(request):
    return Developer.objects.get(user=request.user).id


@register.filter(is_safe=True)
def safe_string(string_object):
    return mark_safe(json.dumps(string_object))


@register.simple_tag
def notification_count(request):
    count = Notification.objects.filter(user=request.user, is_seen=False).count()
    return count if count > 0 else ""


@register.filter
def get_item_at_index(target_list, index):
    try:
        return target_list[index]
    except IndexError:
        return None


# @register.simple_tag
# def is_developer(request):
#     developer = Developer.objects.filter(user=request.user)
#     if developer:
#         return True
#     else:
#         return False
