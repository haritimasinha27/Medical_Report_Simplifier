from django.urls import path
from . import views

urlpatterns = [
    path('', views.ui, name='ui'),
    path('health', views.health, name='health'),
    path('extract', views.extract, name='extract'),
    path('normalize', views.normalize, name='normalize'),
    path('process', views.process, name='process'),
]


