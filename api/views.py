from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
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
)
from .permissions import IsOwner, IsAdminOrReadOnly
from .filters import ProductFilter


# -----------------------------------------------------------------------------
# System & Authentication Views
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Category ViewSet
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Product ViewSet
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Cart ViewSet
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Address ViewSet
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Order ViewSet
# -----------------------------------------------------------------------------

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

        order.status = 'cancelled'
        order.save()
        return Response(
            {
                "success": True,
                "message": f"Order #{order.order_number} has been cancelled successfully.",
                "order": OrderSerializer(order).data,
            },
            status=status.HTTP_200_OK
        )


# -----------------------------------------------------------------------------
# Coupon ViewSet
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Favorite ViewSet
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# FAQ ViewSet
# -----------------------------------------------------------------------------

class FAQViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Frequently asked questions for Help & Support screen.
    """
    queryset = FAQ.objects.filter(is_active=True).order_by('order', 'id')
    serializer_class = FAQSerializer
    permission_classes = [permissions.AllowAny]
