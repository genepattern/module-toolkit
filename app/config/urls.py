"""
URL configuration for the GenePattern Module Generator Web UI.
"""

from django.urls import path, include

urlpatterns = [
    path('', include('generator.urls')),
]

