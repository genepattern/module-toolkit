"""
URL configuration for the generator app.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('generate/', views.generate_module, name='generate'),
    path('status/<str:module_dir>/', views.module_status, name='module_status'),
    path('console/<str:module_dir>/', views.console_log, name='console_log'),
    path('download/<str:module_dir>/<str:filename>/', views.download_file, name='download_file'),
    path('files/<str:module_dir>/', views.module_files, name='module_files'),
    path('debug/', views.debug_view, name='debug'),
]
