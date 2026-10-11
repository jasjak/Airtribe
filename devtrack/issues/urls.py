from django.urls import path
from . import views

urlpatterns = [
    path('reporters/', views.reporters_view, name='reporters'),
    path('reporters', views.reporters_view, name='reporters_no_slash'),
    path('issues/', views.issues_view, name='issues'),
    path('issues', views.issues_view, name='issues_no_slash'),
]
