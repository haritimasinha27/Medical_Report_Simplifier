from django.urls import path
from . import views

urlpatterns = [
    path('', views.ui, name='ui'),
    path('health', views.health, name='health'),
    path('process', views.process, name='process'),
]


