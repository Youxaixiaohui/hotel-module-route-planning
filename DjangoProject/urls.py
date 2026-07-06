from django.urls import path, include
from django.shortcuts import redirect


def home_redirect_view(request):
    if request.user.is_authenticated:
        return redirect('route_planning')
    return redirect('login')


urlpatterns = [
    path('', include('hotel.urls')),
]
