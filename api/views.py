from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Prefetch, Sum, Count, Q, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import viewsets, status, permissions, serializers
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from .models import (
    Category,
    Product,
    Address,
    CartItem,
    Coupon,
    Order,
    OrderItem,
    FavoriteProduct,
    FAQ,
    UserProfile,
    User,
)
from .serializers import (
    UserSerializer,
    SignupSerializer,
    RegisterSerializer,
    LoginSerializer,
    LogoutSerializer,
    ProfileUpdateSerializer,
    CategorySerializer,
    ProductSerializer,
    AddressSerializer,
    CartItemSerializer,
    CartItemQuantityUpdateSerializer,
    CouponSerializer,
    ApplyCouponSerializer,
    OrderSerializer,
    OrderCreateSerializer,
    FavoriteProductSerializer,
    FAQSerializer,
    FREE_DELIVERY_THRESHOLD,
    STANDARD_DELIVERY_FEE,
    AdminLoginSerializer,
    AdminUserSerializer,
    AdminCategorySerializer,
    AdminProductSerializer,
    AdminOrderItemSerializer,
    AdminOrderListSerializer,
    AdminOrderDetailSerializer,
    AdminOrderStatusUpdateSerializer,
    AdminCustomerSerializer,
    AdminCustomerDetailSerializer,
    AdminInventoryStockAdjustSerializer,
    AdminBatchStockAdjustSerializer,
)
from .permissions import IsOwner, IsAdminOrReadOnly, IsAdminRole
from .filters import ProductFilter


# System & Authentication

@extend_schema(
    responses={
        200: OpenApiResponse(
            description="System is operational",
            response={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "example": "healthy"},
                    "service": {"type": "string", "example": "FreshDash Backend API"},
                    "version": {"type": "string", "example": "1.0.0"},
                },
            },
        )
    }
)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """
    Health check endpoint returning system operational status.
    """
    return Response(
        {
            "status": "healthy",
            "service": "FreshDash Backend API",
            "version": "1.0.0",
        },
        status=status.HTTP_200_OK,
    )


class SignupView(APIView):
    """
    Register a new customer account with password strength validation
    and unique email enforcement. Returns JWT access & refresh tokens.
    """
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'signup'

    @extend_schema(request=SignupSerializer, responses={201: UserSerializer})
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        # Backward compatibility DRF static token
        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "success": True,
                "message": "User registered successfully.",
                "tokens": {
                    "access": access,
                    "refresh": str(refresh),
                },
                "token": token.key,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


# Backward compatibility alias
RegisterView = SignupView


class LoginView(APIView):
    """
    Authenticate a user with username or email with rate limiting.
    Returns JWT access & refresh tokens.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer
    throttle_scope = 'login'

    @extend_schema(request=LoginSerializer, responses={200: OpenApiResponse(description="JWT tokens and user details")})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        tokens = serializer.validated_data['tokens']

        # Backward compatibility DRF static token
        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "success": True,
                "message": "Login successful.",
                "tokens": tokens,
                "token": token.key,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    Logout user by blacklisting their refresh token.
    Prevents token reuse and revokes active session.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=LogoutSerializer, responses={200: OpenApiResponse(description="Logged out and refresh token blacklisted")})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "success": True,
                "message": "Successfully logged out and refresh token blacklisted.",
            },
            status=status.HTTP_200_OK,
        )


class CustomTokenRefreshView(BaseTokenRefreshView):
    """
    Exchange a valid refresh token for a newly rotated refresh token and fresh access token.
    """
    @extend_schema(
        description="Exchange refresh token for a newly rotated refresh token and fresh access token."
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            data = dict(response.data)
            return Response(
                {
                    "success": True,
                    "message": "Token refreshed successfully.",
                    "tokens": data,
                    "access": data.get("access"),
                    "refresh": data.get("refresh"),
                },
                status=status.HTTP_200_OK,
            )
        return response


class ProfileView(APIView):
    """
    Retrieve and update profile settings (order_updates, notifications, phone).
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        user_data = UserSerializer(request.user).data
        return Response(
            {
                **user_data,
                "success": True,
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(request=ProfileUpdateSerializer, responses={200: UserSerializer})
    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "success": True,
                "message": "Profile updated successfully.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


# Category

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Categories listing and detail views with active produce products count.
    """
    queryset = Category.objects.filter(is_active=True).order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'

    @action(detail=True, methods=['get'], url_path='products')
    def products(self, request, id=None):
        category = self.get_object()
        products_qs = category.products.filter(is_available=True)
        page = self.paginate_queryset(products_qs)
        if page is not None:
            serializer = ProductSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ProductSerializer(products_qs, many=True)
        return Response(serializer.data)


# Product

class ProductViewSet(viewsets.ModelViewSet):
    """
    Complete CRUD for produce products.
    Supports filtering by category, popular, organic, offers, featured shelves,
    as well as full-text search and price ordering.
    """
    queryset = Product.objects.filter(is_available=True).select_related('category')
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'id'
    filterset_class = ProductFilter
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'name', 'created_at']
    ordering = ['name']

    @action(detail=True, methods=['get'], url_path='pairs-well-with')
    def pairs_well_with(self, request, id=None):
        """
        Returns complementary produce items for the product details screen.
        """
        current_product = self.get_object()
        complementary = (
            Product.objects.filter(is_available=True)
            .exclude(id=current_product.id)
            .order_by('?')[:5]
        )
        serializer = ProductSerializer(complementary, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='bestsellers')
    def bestsellers(self, request):
        """
        Returns everyday bestselling produce items.
        """
        bestsellers_qs = Product.objects.filter(is_available=True, popular=True)
        serializer = ProductSerializer(bestsellers_qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='seasonal')
    def seasonal(self, request):
        """
        Returns seasonal produce picks (e.g. Alphonso mangoes).
        """
        seasonal_qs = Product.objects.filter(is_available=True, category_id='seasonal')
        serializer = ProductSerializer(seasonal_qs, many=True)
        return Response(serializer.data)


# Cart

class CartViewSet(viewsets.ViewSet):
    """
    Manage user shopping basket: view basket with bill summary, add items,
    update quantities (+1 / -1), remove items, and clear basket.
    """
    queryset = CartItem.objects.none()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CartItemSerializer
    lookup_field = 'pk'

    def _get_cart_summary(self, user):
        cart_items = CartItem.objects.filter(user=user).select_related('product')
        items_data = CartItemSerializer(cart_items, many=True).data

        item_total = sum(item.total_price for item in cart_items)
        savings_total = sum(item.total_savings for item in cart_items)
        total_items = sum(item.quantity for item in cart_items)

        delivery_fee = Decimal('0.00') if item_total >= FREE_DELIVERY_THRESHOLD or total_items == 0 else STANDARD_DELIVERY_FEE
        grand_total = item_total + delivery_fee

        return {
            'items': items_data,
            'total_items': total_items,
            'item_total': item_total,
            'savings_total': savings_total,
            'free_delivery_threshold': FREE_DELIVERY_THRESHOLD,
            'delivery_fee': delivery_fee,
            'grand_total': grand_total,
        }

    @extend_schema(responses={200: OpenApiResponse(description="Basket summary and items")})
    def list(self, request):
        """
        Get all items in user's basket and calculated bill summary.
        """
        summary = self._get_cart_summary(request.user)
        return Response(summary, status=status.HTTP_200_OK)

    @extend_schema(request=CartItemSerializer, responses={201: CartItemSerializer})
    def create(self, request):
        """
        Add a product to user basket (with optional quantity and large pack).
        """
        serializer = CartItemSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        cart_item = serializer.save()

        summary = self._get_cart_summary(request.user)
        return Response(
            {
                "success": True,
                "message": f"Added {cart_item.product.name} to basket.",
                "item": CartItemSerializer(cart_item).data,
                "summary": summary,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=CartItemQuantityUpdateSerializer,
        parameters=[OpenApiParameter(name='pk', type=str, location=OpenApiParameter.PATH, description='Cart item ID or product key (e.g. tomato:regular)')]
    )
    def partial_update(self, request, pk=None):
        """
        Change item quantity by delta (+1 / -1) or set explicit quantity.
        Accepts numeric PK or composite key (e.g. 'tomato:regular').
        """
        user = request.user
        cart_item = None

        if pk.isdigit():
            cart_item = get_object_or_404(CartItem, id=int(pk), user=user)
        elif ':' in pk:
            product_id, size = pk.split(':', 1)
            is_large = size.lower() == 'large'
            cart_item = get_object_or_404(CartItem, user=user, product_id=product_id, large=is_large)
        else:
            cart_item = get_object_or_404(CartItem, user=user, product_id=pk)

        serializer = CartItemQuantityUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if 'quantity' in serializer.validated_data:
            new_quantity = serializer.validated_data['quantity']
        else:
            delta = serializer.validated_data.get('delta', 0)
            new_quantity = cart_item.quantity + delta

        if new_quantity <= 0:
            cart_item.delete()
            message = "Item removed from basket."
            item_data = None
        else:
            cart_item.quantity = new_quantity
            cart_item.save()
            message = "Basket quantity updated."
            item_data = CartItemSerializer(cart_item).data

        summary = self._get_cart_summary(user)
        return Response(
            {
                "success": True,
                "message": message,
                "item": item_data,
                "summary": summary,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={200: OpenApiResponse(description="Item removed from basket")},
        parameters=[OpenApiParameter(name='pk', type=str, location=OpenApiParameter.PATH, description='Cart item ID or product key (e.g. tomato:regular)')]
    )
    def destroy(self, request, pk=None):
        """
        Remove item completely from basket.
        Accepts numeric PK or composite key.
        """
        user = request.user
        if pk.isdigit():
            cart_item = get_object_or_404(CartItem, id=int(pk), user=user)
        elif ':' in pk:
            product_id, size = pk.split(':', 1)
            is_large = size.lower() == 'large'
            cart_item = get_object_or_404(CartItem, user=user, product_id=product_id, large=is_large)
        else:
            cart_item = get_object_or_404(CartItem, user=user, product_id=pk)

        cart_item.delete()
        summary = self._get_cart_summary(user)
        return Response(
            {
                "success": True,
                "message": "Item removed from basket.",
                "summary": summary,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses={200: OpenApiResponse(description="Basket emptied")})
    @action(detail=False, methods=['post'], url_path='clear')
    def clear(self, request):
        """
        Empties the basket.
        """
        CartItem.objects.filter(user=request.user).delete()
        summary = self._get_cart_summary(request.user)
        return Response(
            {
                "success": True,
                "message": "Basket cleared.",
                "summary": summary,
            },
            status=status.HTTP_200_OK,
        )


# Address

class AddressViewSet(viewsets.ModelViewSet):
    """
    User delivery addresses with ownership security and default address management.
    """
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    queryset = Address.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Address.objects.none()
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # If user has no addresses yet, make this first address default
        has_existing = Address.objects.filter(user=self.request.user).exists()
        is_default = not has_existing or serializer.validated_data.get('is_default', False)
        serializer.save(user=self.request.user, is_default=is_default)

    @action(detail=True, methods=['post'], url_path='set-default')
    def set_default(self, request, pk=None):
        address = self.get_object()
        address.is_default = True
        address.save()
        return Response(
            {
                "success": True,
                "message": f"{address.name} address set as default.",
                "address": AddressSerializer(address).data,
            },
            status=status.HTTP_200_OK,
        )


# Order

class OrderViewSet(viewsets.ModelViewSet):
    """
    Customer orders: place order from basket, view order history and detail.
    """
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    lookup_field = 'order_number'
    queryset = Order.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Order.objects.none()
        return Order.objects.filter(user=self.request.user).prefetch_related('items', 'items__product')

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def get_object(self):
        # Support lookup by order_number or numeric id
        lookup_val = self.kwargs.get(self.lookup_field)
        queryset = self.get_queryset()
        if lookup_val.isdigit():
            obj = get_object_or_404(queryset, id=int(lookup_val))
        else:
            obj = get_object_or_404(queryset, order_number=lookup_val)
        self.check_object_permissions(self.request, obj)
        return obj

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(
            {
                "success": True,
                "message": "Order placed successfully.",
                "order": OrderSerializer(order).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, order_number=None):
        """
        Cancel an order if it is in placed or confirmed status.
        """
        order = self.get_object()
        if order.status in ['out_for_delivery', 'delivered']:
            return Response(
                {
                    "success": False,
                    "message": f"Order #{order.order_number} cannot be cancelled because it is already {order.get_status_display().lower()}."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        if order.status == 'cancelled':
            return Response(
                {
                    "success": False,
                    "message": f"Order #{order.order_number} is already cancelled."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            order.status = 'cancelled'
            order.save(update_fields=['status', 'updated_at'])

            # Restore product inventory
            for item in order.items.select_related('product'):
                if item.product:
                    restored = item.quantity * 2 if item.large else item.quantity
                    item.product.stock += restored
                    if item.product.stock > 0 and not item.product.is_available:
                        item.product.is_available = True
                    item.product.save(update_fields=['stock', 'is_available'])

        return Response(
            {
                "success": True,
                "message": f"Order #{order.order_number} has been cancelled successfully.",
                "order": OrderSerializer(order).data,
            },
            status=status.HTTP_200_OK
        )


# Coupon

class CouponViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Offers and promo coupons with validation endpoint.
    """
    queryset = Coupon.objects.filter(is_active=True)
    serializer_class = CouponSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'code'

    @action(detail=False, methods=['post'], url_path='apply')
    def apply(self, request):
        """
        Validate promo code and calculate discount on specified item_total.
        """
        serializer = ApplyCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        coupon = serializer.context['coupon']
        item_total = serializer.validated_data['item_total']

        discount = coupon.calculate_discount(item_total)
        delivery_fee = Decimal('0.00') if item_total >= FREE_DELIVERY_THRESHOLD else STANDARD_DELIVERY_FEE
        final_total = max(Decimal('0.00'), item_total + delivery_fee - discount)

        return Response(
            {
                "valid": True,
                "code": coupon.code,
                "description": coupon.description,
                "discount_percentage": int(coupon.discount_rate * 100),
                "discount": discount,
                "discount_amount": discount,
                "item_total": item_total,
                "delivery_fee": delivery_fee,
                "grand_total": final_total,
                "final_total": final_total,
                "message": f"{int(coupon.discount_rate * 100)}% off applied, up to ₹{coupon.max_discount}.",
            },
            status=status.HTTP_200_OK,
        )


# Favorite

class FavoriteViewSet(viewsets.ModelViewSet):
    """
    User saved favorite products for rapid repurchase.
    """
    serializer_class = FavoriteProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    queryset = FavoriteProduct.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return FavoriteProduct.objects.none()
        return FavoriteProduct.objects.filter(user=self.request.user).select_related('product')

    @action(detail=False, methods=['post'], url_path='toggle')
    def toggle(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response(
                {"success": False, "message": "product_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        product = get_object_or_404(Product, id=product_id)
        existing = FavoriteProduct.objects.filter(user=request.user, product=product).first()

        if existing:
            existing.delete()
            is_favourite = False
            msg = f"Removed {product.name} from favourites."
        else:
            FavoriteProduct.objects.create(user=request.user, product=product)
            is_favourite = True
            msg = f"Saved {product.name} to favourites."

        return Response(
            {
                "success": True,
                "product_id": product.id,
                "is_favourite": is_favourite,
                "message": msg,
            },
            status=status.HTTP_200_OK,
        )


# FAQ

class FAQViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Frequently asked questions for Help & Support screen.
    """
    queryset = FAQ.objects.filter(is_active=True).order_by('order', 'id')
    serializer_class = FAQSerializer
    permission_classes = [permissions.AllowAny]


# Admin Management System

class AdminLoginView(APIView):
    """
    Dedicated admin login endpoint.
    Restricts access strictly to administrative roles (admin, manager, staff, superuser).
    Regular customer accounts are denied access with HTTP 403 Forbidden.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = AdminLoginSerializer
    throttle_scope = 'login'

    @extend_schema(request=AdminLoginSerializer, responses={200: OpenApiResponse(description="Admin JWT tokens and profile")})
    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        if not serializer.is_valid():
            # If role check failed, return 403 Forbidden
            for err_list in serializer.errors.values():
                if any("Access denied" in str(e) for e in err_list):
                    return Response(
                        {
                            "success": False,
                            "message": "Access denied. Administrator privileges required.",
                            "detail": "Access denied. Administrator privileges required.",
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        tokens = serializer.validated_data['tokens']
        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "success": True,
                "message": "Admin authentication successful.",
                "tokens": tokens,
                "token": token.key,
                "user": AdminUserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class AdminMeView(APIView):
    """
    Retrieve and update the authenticated administrator's profile.
    """
    permission_classes = [IsAdminRole]

    @extend_schema(responses={200: AdminUserSerializer})
    def get(self, request):
        return Response(
            {
                "success": True,
                "user": AdminUserSerializer(request.user).data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(request=AdminUserSerializer, responses={200: AdminUserSerializer})
    def patch(self, request):
        user = request.user
        for field in ['first_name', 'last_name', 'email']:
            if field in request.data:
                setattr(user, field, request.data[field])
        user.save()

        if hasattr(user, 'profile') and 'phone_number' in request.data:
            user.profile.phone_number = request.data['phone_number']
            user.profile.save()

        return Response(
            {
                "success": True,
                "message": "Admin profile updated successfully.",
                "user": AdminUserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class AdminLogoutView(APIView):
    """
    Revoke admin refresh token and log out.
    """
    permission_classes = [IsAdminRole]

    @extend_schema(request=LogoutSerializer, responses={200: OpenApiResponse(description="Logged out")})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "success": True,
                "message": "Admin logged out successfully.",
            },
            status=status.HTTP_200_OK,
        )


class AdminCategoryViewSet(viewsets.ModelViewSet):
    """
    Category Management for administrators:
    Full CRUD, safe deletion protection, image uploads, search, filtering, and active status toggle.
    """
    permission_classes = [IsAdminRole]
    queryset = Category.objects.all().order_by('name')
    serializer_class = AdminCategorySerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = Category.objects.all()

        # Active / Inactive status filter
        is_active = self.request.query_params.get('is_active')
        if is_active is not None and is_active != '':
            if is_active.lower() in ['true', '1']:
                qs = qs.filter(is_active=True)
            elif is_active.lower() in ['false', '0']:
                qs = qs.filter(is_active=False)

        # Search filter (name and slug ID)
        search = self.request.query_params.get('search')
        if search:
            search = search.strip()
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(id__icontains=search)
            )

        # Ordering
        ordering = self.request.query_params.get('ordering')
        if ordering in ['name', '-name', 'created_at', '-created_at']:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by('name')

        return qs

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        product_count = category.products.count()
        if product_count > 0:
            return Response(
                {
                    "success": False,
                    "message": f"Cannot delete category '{category.name}' because it contains {product_count} product(s). Please reassign or delete these products first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        category_name = category.name
        category.delete()
        return Response(
            {
                "success": True,
                "message": f"Category '{category_name}' deleted successfully.",
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='toggle-status')
    def toggle_status(self, request, pk=None):
        category = self.get_object()
        category.is_active = not category.is_active
        category.save(update_fields=['is_active', 'updated_at'])
        return Response(
            {
                "success": True,
                "is_active": category.is_active,
                "message": f"Category '{category.name}' is now {'active' if category.is_active else 'inactive'}.",
                "category": AdminCategorySerializer(category).data,
            },
            status=status.HTTP_200_OK,
        )


class AdminProductViewSet(viewsets.ModelViewSet):
    """
    Product Management for administrators:
    Full CRUD, stock tracking, image upload, availability toggle, and stock adjustment.
    """
    permission_classes = [IsAdminRole]
    queryset = Product.objects.select_related('category').all().order_by('-created_at')
    serializer_class = AdminProductSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = Product.objects.select_related('category').all()

        # Category filter
        cat = self.request.query_params.get('category')
        if cat:
            qs = qs.filter(category_id=cat)

        # Availability filter
        avail = self.request.query_params.get('is_available')
        if avail is not None:
            if avail.lower() in ['true', '1']:
                qs = qs.filter(is_available=True)
            elif avail.lower() in ['false', '0']:
                qs = qs.filter(is_available=False)

        # Stock status filter
        stock_status = self.request.query_params.get('stock_status')
        if stock_status == 'low_stock':
            qs = qs.filter(stock__gt=0, stock__lte=10)
        elif stock_status == 'out_of_stock':
            qs = qs.filter(stock=0)
        elif stock_status == 'in_stock':
            qs = qs.filter(stock__gt=10)

        # Search filter
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(id__icontains=search) |
                Q(category__name__icontains=search)
            )

        # Ordering
        ordering = self.request.query_params.get('ordering')
        if ordering in ['price', '-price', 'stock', '-stock', 'name', '-name', 'created_at', '-created_at']:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by('-created_at')

        return qs

    @action(detail=True, methods=['post'], url_path='toggle-status')
    def toggle_status(self, request, pk=None):
        product = self.get_object()
        product.is_available = not product.is_available
        product.save(update_fields=['is_available', 'updated_at'])
        return Response(
            {
                "success": True,
                "is_available": product.is_available,
                "message": f"Product '{product.name}' is now {'available' if product.is_available else 'unavailable'}.",
                "product": AdminProductSerializer(product).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='adjust-stock')
    def adjust_stock(self, request, pk=None):
        product = self.get_object()
        stock_val = request.data.get('stock')
        adjustment = request.data.get('adjustment')

        if stock_val is None and adjustment is None:
            return Response(
                {"success": False, "message": "Either 'stock' (absolute) or 'adjustment' (delta) is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            if stock_val is not None:
                try:
                    new_stock = int(stock_val)
                    if new_stock < 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    return Response({"success": False, "message": "'stock' must be a non-negative integer."}, status=status.HTTP_400_BAD_REQUEST)
                product.stock = new_stock
            elif adjustment is not None:
                try:
                    delta = int(adjustment)
                except (ValueError, TypeError):
                    return Response({"success": False, "message": "'adjustment' must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
                if product.stock + delta < 0:
                    return Response(
                        {"success": False, "message": f"Cannot reduce stock below 0. Current stock: {product.stock}."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                product.stock += delta

            if product.stock == 0:
                product.is_available = False
            elif product.stock > 0 and not product.is_available:
                product.is_available = True

            product.save(update_fields=['stock', 'is_available', 'updated_at'])

        return Response(
            {
                "success": True,
                "message": f"Stock for '{product.name}' updated to {product.stock}.",
                "product": AdminProductSerializer(product).data,
            },
            status=status.HTTP_200_OK,
        )


class AdminOrderViewSet(viewsets.ModelViewSet):
    """
    Order Management for administrators:
    List all customer orders, inspect details, update fulfillment and payment statuses,
    with automatic inventory synchronization upon cancellation.
    """
    permission_classes = [IsAdminRole]
    lookup_field = 'order_number'
    queryset = Order.objects.select_related('user', 'user__profile', 'delivery_address').prefetch_related('items', 'items__product').all()

    def get_serializer_class(self):
        if self.action == 'list':
            return AdminOrderListSerializer
        if self.action in ['update', 'partial_update']:
            return AdminOrderStatusUpdateSerializer
        return AdminOrderDetailSerializer

    def get_object(self):
        lookup_val = self.kwargs.get(self.lookup_field)
        qs = self.get_queryset()
        if lookup_val.isdigit():
            obj = get_object_or_404(qs, id=int(lookup_val))
        else:
            obj = get_object_or_404(qs, order_number=lookup_val)
        self.check_object_permissions(self.request, obj)
        return obj

    def get_queryset(self):
        qs = Order.objects.select_related('user', 'user__profile', 'delivery_address').prefetch_related('items', 'items__product').all()

        # Status filter
        order_status = self.request.query_params.get('status')
        if order_status:
            qs = qs.filter(status=order_status)

        # Payment status filter
        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            qs = qs.filter(payment_status=payment_status)

        # Payment method filter
        payment_method = self.request.query_params.get('payment_method')
        if payment_method:
            valid_methods = [c[0] for c in Order.PAYMENT_METHOD_CHOICES]
            if payment_method in valid_methods:
                qs = qs.filter(payment_method=payment_method)
            else:
                qs = qs.none()

        # Search filter (order number, customer name, email)
        search = self.request.query_params.get('search')
        if search:
            search = search.strip()
            qs = qs.filter(
                Q(order_number__icontains=search) |
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )

        # Date range filters
        date_from = self.request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = self.request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        # Dynamic Sorting
        ordering = self.request.query_params.get('ordering')
        ALLOWED_ORDERING = {
            '-created_at': ['-created_at', '-id'],
            'created_at': ['created_at', 'id'],
            '-grand_total': ['-grand_total', '-created_at', '-id'],
            'grand_total': ['grand_total', '-created_at', '-id'],
        }
        if ordering in ALLOWED_ORDERING:
            qs = qs.order_by(*ALLOWED_ORDERING[ordering])
        else:
            qs = qs.order_by('-created_at', '-id')

        return qs

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        order = self.get_object()
        serializer = AdminOrderStatusUpdateSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        ALLOWED_STATUS_TRANSITIONS = {
            'pending': {'placed', 'confirmed', 'processing', 'shipped', 'out_for_delivery', 'delivered', 'cancelled'},
            'placed': {'confirmed', 'processing', 'shipped', 'out_for_delivery', 'delivered', 'cancelled'},
            'confirmed': {'processing', 'shipped', 'out_for_delivery', 'delivered', 'cancelled'},
            'processing': {'shipped', 'out_for_delivery', 'delivered', 'cancelled'},
            'shipped': {'out_for_delivery', 'delivered', 'cancelled'},
            'out_for_delivery': {'delivered', 'cancelled'},
            'delivered': set(),
            'cancelled': set(),
        }

        with transaction.atomic():
            new_status = data.get('status')
            if new_status and new_status != order.status:
                old_status = order.status
                if old_status == 'delivered':
                    return Response(
                        {
                            "success": False,
                            "message": f"Order #{order.order_number} has already been delivered and cannot be transitioned to '{new_status}'.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if old_status == 'cancelled':
                    return Response(
                        {
                            "success": False,
                            "message": f"Order #{order.order_number} is cancelled and cannot be reopened or transitioned to '{new_status}'.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if new_status not in ALLOWED_STATUS_TRANSITIONS.get(old_status, set()):
                    return Response(
                        {
                            "success": False,
                            "message": f"Invalid status transition from '{old_status}' to '{new_status}'.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                order.status = new_status
                # Restore stock on cancellation
                if new_status == 'cancelled':
                    for item in order.items.select_related('product'):
                        if item.product:
                            restored = item.quantity * 2 if item.large else item.quantity
                            item.product.stock += restored
                            if item.product.stock > 0 and not item.product.is_available:
                                item.product.is_available = True
                            item.product.save(update_fields=['stock', 'is_available'])

            if 'payment_status' in data:
                order.payment_status = data['payment_status']
            if 'payment_method' in data:
                order.payment_method = data['payment_method']

            order.save()

        return Response(
            {
                "success": True,
                "message": f"Order #{order.order_number} updated successfully.",
                "order": AdminOrderDetailSerializer(order).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, order_number=None):
        return self.update(request, partial=True)


class AdminCustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Customer Management for administrators:
    Browse registered customers, view lifetime orders and total spend,
    inspect address books and order histories, and toggle active/blocked account status.
    """
    permission_classes = [IsAdminRole]
    queryset = User.objects.select_related('profile').prefetch_related('orders', 'addresses').all().order_by('-date_joined')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AdminCustomerDetailSerializer
        return AdminCustomerSerializer

    def get_queryset(self):
        qs = User.objects.select_related('profile').prefetch_related('orders', 'addresses').all()

        # Optimize customer query performance using SQL annotations
        qs = qs.annotate(
            annotated_orders_count=Count('orders', distinct=True),
            annotated_total_spent=Coalesce(
                Sum('orders__grand_total', filter=~Q(orders__status='cancelled')),
                Decimal('0.00'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        # Role filter
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(profile__role=role)

        # Active filter
        active = self.request.query_params.get('is_active')
        if active is not None:
            if active.lower() in ['true', '1']:
                qs = qs.filter(is_active=True)
            elif active.lower() in ['false', '0']:
                qs = qs.filter(is_active=False)

        # Search filter
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(profile__phone_number__icontains=search)
            )

        # Dynamic Sorting
        ordering = self.request.query_params.get('ordering')
        ORDERING_MAP = {
            'username': ['username', '-date_joined', 'id'],
            '-username': ['-username', '-date_joined', 'id'],
            'date_joined': ['date_joined', 'id'],
            '-date_joined': ['-date_joined', 'id'],
            'orders_count': ['annotated_orders_count', '-date_joined', 'id'],
            '-orders_count': ['-annotated_orders_count', '-date_joined', 'id'],
            'total_spent': ['annotated_total_spent', '-date_joined', 'id'],
            '-total_spent': ['-annotated_total_spent', '-date_joined', 'id'],
        }

        if ordering in ORDERING_MAP:
            return qs.order_by(*ORDERING_MAP[ordering])

        return qs.order_by('-date_joined', 'id')

    @action(detail=True, methods=['post'], url_path='toggle-status')
    def toggle_status(self, request, pk=None):
        customer = self.get_object()
        if customer == request.user:
            return Response(
                {"success": False, "message": "You cannot deactivate your own administrative account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer.is_active = not customer.is_active
        customer.save(update_fields=['is_active'])

        return Response(
            {
                "success": True,
                "is_active": customer.is_active,
                "message": f"Customer '{customer.username}' account has been {'activated' if customer.is_active else 'deactivated/blocked'}.",
                "customer": AdminCustomerSerializer(customer).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='change-role')
    def change_role(self, request, pk=None):
        customer = self.get_object()
        new_role = request.data.get('role')
        if new_role not in ['admin', 'manager', 'customer']:
            return Response(
                {"success": False, "message": "Role must be one of: 'admin', 'manager', 'customer'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not hasattr(customer, 'profile'):
            UserProfile.objects.create(user=customer)

        customer.profile.role = new_role
        customer.profile.save(update_fields=['role'])

        if new_role in ['admin', 'manager']:
            customer.is_staff = True
        else:
            customer.is_staff = False
        customer.save(update_fields=['is_staff'])

        return Response(
            {
                "success": True,
                "role": new_role,
                "message": f"User '{customer.username}' role changed to '{new_role}'.",
                "customer": AdminCustomerSerializer(customer).data,
            },
            status=status.HTTP_200_OK,
        )


class AdminInventoryViewSet(viewsets.ViewSet):
    """
    Inventory Management for administrators:
    Low-stock detection (threshold <= 10), out-of-stock monitoring, single and batch stock adjustments.
    Supports server-side pagination, allowlisted sorting, category and stock status filtering.
    """
    permission_classes = [IsAdminRole]
    serializer_class = AdminInventoryStockAdjustSerializer

    ORDERING_MAP = {
        'stock': ['stock', 'id'],
        '-stock': ['-stock', 'id'],
        'name': ['name', 'id'],
        '-name': ['-name', 'id'],
        'category': ['category__name', 'name', 'id'],
        '-category': ['-category__name', 'name', 'id'],
        'price': ['price', 'id'],
        '-price': ['-price', 'id'],
    }

    def list(self, request):
        qs = Product.objects.select_related('category').all()

        # Category filter
        category = request.query_params.get('category')
        if category:
            qs = qs.filter(category_id=category)

        # Stock status filter
        filter_type = request.query_params.get('filter')
        if filter_type == 'low_stock':
            qs = qs.filter(stock__gt=0, stock__lte=10)
        elif filter_type == 'out_of_stock':
            qs = qs.filter(stock=0)
        elif filter_type == 'in_stock':
            qs = qs.filter(stock__gt=10)

        # Search filter by produce name or ID
        search = request.query_params.get('search')
        if search and search.strip():
            search_term = search.strip()
            qs = qs.filter(Q(name__icontains=search_term) | Q(id__icontains=search_term))

        # Dynamic allowlisted ordering with deterministic tie-breaker
        ordering = request.query_params.get('ordering')
        if ordering in self.ORDERING_MAP:
            qs = qs.order_by(*self.ORDERING_MAP[ordering])
        else:
            qs = qs.order_by(*self.ORDERING_MAP['stock'])

        # Pagination: supports page and page_size safely
        page_size_param = request.query_params.get('page_size', 20)
        try:
            page_size = max(1, min(int(page_size_param), 100))
        except (ValueError, TypeError):
            page_size = 20

        paginator = Paginator(qs, page_size)
        total_count = paginator.count
        total_pages = paginator.num_pages or 1

        page_param = request.query_params.get('page', 1)
        try:
            page_number = int(page_param)
            if page_number < 1:
                page_number = 1
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, ValueError, TypeError):
            page_number = 1
            page_obj = paginator.page(1)
        except EmptyPage:
            # Safely clamp out-of-range page numbers
            page_number = max(1, total_pages)
            try:
                page_obj = paginator.page(page_number)
            except EmptyPage:
                page_obj = []

        items = [
            {
                "id": p.id,
                "name": p.name,
                "weight": p.weight,
                "category_id": p.category_id,
                "category_name": p.category.name if p.category else "",
                "price": str(p.price),
                "stock": p.stock,
                "is_available": p.is_available,
                "is_low_stock": p.is_low_stock,
                "is_out_of_stock": p.is_out_of_stock,
                "image": request.build_absolute_uri(p.image.url) if p.image else None,
            }
            for p in page_obj
        ]

        return Response(
            {
                "success": True,
                "count": total_count,
                "total_items": total_count,
                "total_pages": total_pages,
                "current_page": page_number,
                "page_size": page_size,
                "low_stock_count": Product.objects.filter(stock__gt=0, stock__lte=10).count(),
                "out_of_stock_count": Product.objects.filter(stock=0).count(),
                "inventory": items,
                "results": items,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['post'], url_path='adjust')
    def adjust(self, request):
        serializer = AdminInventoryStockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            # select_for_update() inside atomic transaction
            # On SQLite this operates under file-level database locks;
            # on PostgreSQL/MySQL it provides row-level locking.
            product = Product.objects.select_for_update().get(id=data['product_id'])
            if 'stock' in data:
                product.stock = data['stock']
            elif 'adjustment' in data:
                delta = data['adjustment']
                if product.stock + delta < 0:
                    return Response(
                        {"success": False, "message": f"Stock cannot drop below 0. Current stock: {product.stock}."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                product.stock += delta

            if product.stock == 0:
                product.is_available = False
            elif product.stock > 0 and not product.is_available:
                product.is_available = True

            product.save(update_fields=['stock', 'is_available', 'updated_at'])

        return Response(
            {
                "success": True,
                "message": f"Stock for '{product.name}' adjusted to {product.stock}.",
                "product": AdminProductSerializer(product).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['post'], url_path='batch-adjust')
    def batch_adjust(self, request):
        serializer = AdminBatchStockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        adjustments = serializer.validated_data['adjustments']

        updated_products = []
        with transaction.atomic():
            for item in adjustments:
                # select_for_update() inside atomic transaction
                # On SQLite this operates under file-level database locks;
                # on PostgreSQL/MySQL it provides row-level locking.
                prod = Product.objects.select_for_update().get(id=item['product_id'])
                if 'stock' in item:
                    prod.stock = item['stock']
                elif 'adjustment' in item:
                    delta = item['adjustment']
                    if prod.stock + delta < 0:
                        raise serializers.ValidationError(
                            f"Stock for '{prod.name}' cannot drop below 0 (current: {prod.stock}, adjustment: {delta})."
                        )
                    prod.stock += delta

                if prod.stock == 0:
                    prod.is_available = False
                elif prod.stock > 0 and not prod.is_available:
                    prod.is_available = True

                prod.save(update_fields=['stock', 'is_available', 'updated_at'])
                updated_products.append(prod)

        return Response(
            {
                "success": True,
                "message": f"Successfully updated stock for {len(updated_products)} product(s).",
                "updated_count": len(updated_products),
                "products": AdminProductSerializer(updated_products, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class AdminDashboardView(APIView):
    """
    Real-time Admin Dashboard Analytics:
    Total products, active products, categories, customers, orders, today's metrics,
    revenue, order breakdown by status, recent orders, bestsellers, and stock alerts.
    All statistics are calculated dynamically from live SQLite database records.
    """
    permission_classes = [IsAdminRole]

    @extend_schema(responses={200: OpenApiResponse(description="Real-time dashboard metrics")})
    def get(self, request):
        now = timezone.now()
        today = now.date()

        # Core entity counts
        total_products = Product.objects.count()
        active_products = Product.objects.filter(is_available=True).count()
        total_categories = Category.objects.count()
        total_customers = User.objects.filter(is_staff=False, is_superuser=False).count()
        total_orders = Order.objects.count()

        # Today's metrics
        today_orders = Order.objects.filter(created_at__date=today)
        today_orders_count = today_orders.count()
        today_revenue = (
            today_orders.exclude(status='cancelled')
            .aggregate(rev=Sum('grand_total'))['rev'] or Decimal('0.00')
        )

        # Lifetime revenue (excluding cancelled orders)
        total_revenue = (
            Order.objects.exclude(status='cancelled')
            .aggregate(rev=Sum('grand_total'))['rev'] or Decimal('0.00')
        )

        # Order breakdown by status
        orders_by_status = {
            s[0]: Order.objects.filter(status=s[0]).count()
            for s in Order.STATUS_CHOICES
        }

        # Order breakdown by payment status
        orders_by_payment_status = {
            s[0]: Order.objects.filter(payment_status=s[0]).count()
            for s in Order.PAYMENT_STATUS_CHOICES
        }

        # Stock alert counts
        low_stock_count = Product.objects.filter(stock__gt=0, stock__lte=10).count()
        out_of_stock_count = Product.objects.filter(stock=0).count()

        # Recent orders (last 5)
        recent_orders_qs = Order.objects.select_related('user').all().order_by('-created_at')[:5]
        recent_orders_data = AdminOrderListSerializer(recent_orders_qs, many=True).data

        # Top 5 best selling products (by non-cancelled order units sold)
        best_sellers_qs = (
            OrderItem.objects.exclude(order__status='cancelled')
            .values('product_id', 'product_name')
            .annotate(
                total_units_sold=Sum('quantity'),
                total_revenue=Sum('total_price'),
            )
            .order_by('-total_units_sold')[:5]
        )
        best_selling_products = list(best_sellers_qs)

        # Low stock products list (top 5 critical)
        low_stock_products_qs = Product.objects.filter(stock__gt=0, stock__lte=10).order_by('stock')[:5]
        low_stock_products = AdminProductSerializer(low_stock_products_qs, many=True).data

        # Out of stock products list (top 5)
        out_of_stock_products_qs = Product.objects.filter(stock=0).order_by('stock')[:5]
        out_of_stock_products = AdminProductSerializer(out_of_stock_products_qs, many=True).data

        return Response(
            {
                "success": True,
                "analytics": {
                    "total_products": total_products,
                    "active_products": active_products,
                    "total_categories": total_categories,
                    "total_customers": total_customers,
                    "total_orders": total_orders,
                    "today_orders_count": today_orders_count,
                    "today_revenue": str(today_revenue),
                    "total_revenue": str(total_revenue),
                    "orders_by_status": orders_by_status,
                    "orders_by_payment_status": orders_by_payment_status,
                    "low_stock_count": low_stock_count,
                    "out_of_stock_count": out_of_stock_count,
                    "recent_orders": recent_orders_data,
                    "best_selling_products": best_selling_products,
                    "low_stock_products": low_stock_products,
                    "out_of_stock_products": out_of_stock_products,
                },
            },
            status=status.HTTP_200_OK,
        )

