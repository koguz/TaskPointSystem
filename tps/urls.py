"""tps URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve
from django.conf import settings
import os

def _serve_sw(request):
    sw_path = os.path.join(settings.BASE_DIR, 'tasks', 'static', 'tasks')
    response = serve(request, 'sw.js', document_root=sw_path)
    response['Content-Type'] = 'application/javascript'
    return response

urlpatterns = [
    path('sw.js', _serve_sw, name='service_worker'),
    path('', include('tasks.urls')),
    path('admin/', admin.site.urls),
    #path('accounts/', include('django.contrib.auth.urls')),
]
