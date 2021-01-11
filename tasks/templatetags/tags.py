from django import template
from tasks.models import Developer, Supervisor
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
def is_developer(request):
    developer = Developer.objects.filter(user=request.user)
    if developer:
        return True
    else:
        return False
