from django import template
from tasks.models import Developer

register = template.Library()


@register.simple_tag
def developer_name(request):
    return Developer.objects.get(user=request.user).get_name()
