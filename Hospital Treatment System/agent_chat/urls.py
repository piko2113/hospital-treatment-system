from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.chat_page, name='chat_page'),
    path('api/', views.api_chat, name='api_chat'),
    path('api/ct/', views.api_ct_image, name='api_ct_image'),
    path('api/kb-status/', views.check_kb, name='check_kb'),
    path('api/history/', views.api_history, name='api_history'),
    path('api/multimodal/', views.api_multimodal, name='api_multimodal'),
]
