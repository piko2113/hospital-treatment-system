"""secondweb URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
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
from django.urls import path, re_path, include
from home import views as home_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('chat/', include('agent_chat.urls')),
    re_path(r'^$', home_views.home),
    re_path(r'^register$', home_views.register),
    re_path(r'^login$', home_views.login),
    re_path(r'^logout$', home_views.logout),
    re_path(r'^post$', home_views.post),
    re_path(r'^recognition$', home_views.recognition),
    re_path(r'^upload$', home_views.upload),
    path('article/<int:id>/', home_views.article),
    path('topic/<int:id>/', home_views.topic),
    path('comment/<int:id>/', home_views.comment),
    path('pseudo/<int:id>/', home_views.pseudo),

]
from django.conf import settings
from django.conf.urls.static import static
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
