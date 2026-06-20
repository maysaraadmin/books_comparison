from django.urls import path
from . import views

app_name = 'compare'

urlpatterns = [
    path('', views.upload_and_compare, name='upload'),
]