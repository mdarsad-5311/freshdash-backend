from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from api.views import (
    SignupView,
    LoginView,
    LogoutView,
    CustomTokenRefreshView,
    ProfileView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    # Versioned API routes (recommended)
    path('api/v1/', include('api.urls')),

    # Direct top-level /api/auth/ aliases for convenience
    path('api/auth/signup/', SignupView.as_view(), name='top-auth-signup'),
    path('api/auth/login/', LoginView.as_view(), name='top-auth-login'),
    path('api/auth/logout/', LogoutView.as_view(), name='top-auth-logout'),
    path('api/auth/token/refresh/', CustomTokenRefreshView.as_view(), name='top-token-refresh'),
    path('api/auth/me/', ProfileView.as_view(), name='top-auth-me'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # Safe production media serving fallback for persistent storage
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
