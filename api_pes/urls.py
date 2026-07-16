from django.urls import path
from . import views 


urlpatterns = [
    path('home/', views.home, name='home'),
    path('mpesa/initiate', views.initiate_stk_push, name='stkpush'),
    path('mpesa/callback', views.mpesa_callback, name='callback')
]