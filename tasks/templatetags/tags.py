from django import template
from tasks.models import Developer
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


def developer_id(request):
    return Developer.objects.get(user=request.user).id

@register.filter(is_safe=True)
def safe_string(object):
    return mark_safe(json.dumps(object))
