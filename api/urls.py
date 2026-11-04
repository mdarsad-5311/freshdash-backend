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
    AdminLoginView,
    AdminMeView,
    AdminLogoutView,
    AdminCategoryViewSet,
    AdminProductViewSet,
    AdminOrderViewSet,
    AdminCustomerViewSet,
    AdminInventoryViewSet,
    AdminDashboardView,
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

# Dedicated Router for Admin Management Endpoints
admin_router = DefaultRouter()
admin_router.register(r'categories', AdminCategoryViewSet, basename='admin-category')
admin_router.register(r'products', AdminProductViewSet, basename='admin-product')
admin_router.register(r'orders', AdminOrderViewSet, basename='admin-order')
admin_router.register(r'customers', AdminCustomerViewSet, basename='admin-customer')
admin_router.register(r'inventory', AdminInventoryViewSet, basename='admin-inventory')

admin_urlpatterns = [
    # Admin Authentication
    path('auth/login/', AdminLoginView.as_view(), name='admin-auth-login'),
    path('auth/me/', AdminMeView.as_view(), name='admin-auth-me'),
    path('auth/logout/', AdminLogoutView.as_view(), name='admin-auth-logout'),
    path('auth/token/refresh/', CustomTokenRefreshView.as_view(), name='admin-token-refresh'),

    # Admin Dashboard Analytics
    path('dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),

    # Admin ViewSet Routes
    path('', include(admin_router.urls)),
]

urlpatterns = [
    # System & Health
    path('health/', health_check, name='health-check'),

    # Customer Authentication & Profile (JWT + Token compatibility)
    path('auth/signup/', SignupView.as_view(), name='auth-signup'),
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/token/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),
    path('auth/me/', ProfileView.as_view(), name='auth-me'),
    path('profile/', ProfileView.as_view(), name='profile-detail'),

    # Admin Management System (/api/v1/admin/...)
    path('admin/', include(admin_urlpatterns)),

    # OpenAPI Schema & Interactive Documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Customer Router ViewSets
    path('', include(router.urls)),
]
