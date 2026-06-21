from django.urls import path
from . import views

app_name = 'compare'

urlpatterns = [
    path('', views.upload_and_compare, name='upload'),
    path('progress/<str:job_id>/', views.progress_page, name='progress_page'),
    path('api/progress/<str:job_id>/', views.get_progress, name='get_progress'),
    path('result/<str:job_id>/', views.result_page, name='result_page'),   # ← this was missing
]