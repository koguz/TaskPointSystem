from tasks.models import Developer
from tasks.views import _avatar_url_set, _default_avatar_url


def navbar_avatar(request):
    default_avatar_url = _default_avatar_url()

    if not request.user.is_authenticated:
        return {"navbar_avatar_url": default_avatar_url}

    try:
        developer = Developer.objects.only("photoURL").get(user=request.user)
    except Developer.DoesNotExist:
        return {"navbar_avatar_url": default_avatar_url}

    avatar_url = developer.photoURL
    if avatar_url not in _avatar_url_set():
        avatar_url = default_avatar_url

    return {"navbar_avatar_url": avatar_url}
