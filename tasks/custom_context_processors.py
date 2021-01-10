from tasks.models import Developer


def developer_or_supervisor(request):
    if not request.user.is_anonymous:
        developer = Developer.objects.filter(user=request.user)
        if developer:
            return {
                'is_developer': True
            }
        else:
            return {
                'is_developer': False
            }
    else:
        return {}
