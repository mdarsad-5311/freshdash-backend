from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from .views import (
    health_check,
    SignupView,
    RegisterView,
    LoginView,
    LogoutView,
    CustomTokenRefreshView,
    ProfileView,
    CategoryViewSet,
    ProductViewSet,
    CartViewSet,
    AddressViewSet,
    OrderViewSet,
    CouponViewSet,
    FavoriteViewSet,
    FAQViewSet,
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'addresses', AddressViewSet, basename='address')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'coupons', CouponViewSet, basename='coupon')
router.register(r'favorites', FavoriteViewSet, basename='favorite')
router.register(r'faqs', FAQViewSet, basename='faq')

urlpatterns = [
    # System & Health
    path('health/', health_check, name='health-check'),

    # Authentication & User Profile (JWT + Token compatibility)
    path('auth/signup/', SignupView.as_view(), name='auth-signup'),
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/token/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),
    path('auth/me/', ProfileView.as_view(), name='auth-me'),
    path('profile/', ProfileView.as_view(), name='profile-detail'),

    # OpenAPI Schema & Interactive Documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Router ViewSets
    path('', include(router.urls)),
]
