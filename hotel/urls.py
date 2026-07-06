# hotel/urls.py — 路线规划模块路由
from django.urls import path
from . import views

urlpatterns = [
    path('', views.route_planning_view, name='home'),

    # 认证
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # 路线规划
    path('route-planning/', views.route_planning_view, name='route_planning'),
    path('api/plan-custom-route/', views.plan_custom_route, name='plan_custom_route'),
    path('api/get-real-route/', views.get_real_route, name='get_real_route'),
    path('api/hotel-route/', views.hotel_route_api, name='hotel_route_api'),
]
