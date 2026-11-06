from decimal import Decimal
import uuid
from django.db import models, transaction
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from drf_spectacular.utils import extend_schema_field
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

FREE_DELIVERY_THRESHOLD = Decimal('199.00')
STANDARD_DELIVERY_FEE = Decimal('20.00')


# User & Authentication

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['phone_number', 'order_updates', 'offers_notifications']


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']
        read_only_fields = ['id']


class SignupSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True)
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'phone_number']

    def validate_email(self, value):
        norm_email = value.strip().lower()
        if not norm_email:
            raise serializers.ValidationError("Email address is required.")
        if User.objects.filter(email__iexact=norm_email).exists():
            raise serializers.ValidationError("An account with this email address already exists.")
        return norm_email

    def validate_password(self, value):
        # Validate password strength against Django's configured AUTH_PASSWORD_VALIDATORS
        validate_password(value)
        return value

    def create(self, validated_data):
        phone_number = validated_data.pop('phone_number', '')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()

        if phone_number:
            user.profile.phone_number = phone_number
            user.profile.save()

        return user


# Backward compatibility alias
RegisterSerializer = SignupSerializer


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Username or email address")
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        login_input = attrs.get('username', '').strip()
        password = attrs.get('password')

        if not login_input or not password:
            raise serializers.ValidationError("Both username/email and password are required.")

        # Support email-based login while preserving username-based login
        auth_username = login_input
        if '@' in login_input:
            matched_user = User.objects.filter(email__iexact=login_input).first()
            if matched_user:
                auth_username = matched_user.username

        user = authenticate(username=auth_username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid username/email or password.")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        attrs['user'] = user
        attrs['tokens'] = {
            'access': access,
            'refresh': str(refresh),
        }
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="The refresh token to be blacklisted")

    def validate_refresh(self, value):
        token_str = value.strip()
        try:
            token = RefreshToken(token_str)
        except TokenError as e:
            raise serializers.ValidationError(f"Invalid or expired refresh token: {e}")
        self.context['token'] = token
        return token_str

    def save(self, **kwargs):
        token = self.context.get('token')
        if token:
            try:
                token.blacklist()
            except AttributeError:
                pass


class ProfileUpdateSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='profile.phone_number', required=False, allow_blank=True)
    order_updates = serializers.BooleanField(source='profile.order_updates', required=False)
    offers_notifications = serializers.BooleanField(source='profile.offers_notifications', required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'order_updates', 'offers_notifications']

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        profile = instance.profile
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()

        return instance


# Category & Product

class CategorySerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'photo', 'tint', 'image', 'is_active', 'products_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def get_products_count(self, obj) -> int:
        return obj.products.filter(is_available=True).count()


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'weight',
            'price',
            'original',
            'discount_percentage',
            'photo',
            'category',
            'category_name',
            'popular',
            'organic',
            'description',
            'stock',
            'image',
            'is_available',
            'is_low_stock',
            'is_out_of_stock',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        price = attrs.get('price', getattr(self.instance, 'price', None))
        original = attrs.get('original', getattr(self.instance, 'original', None))

        if price is not None and price < 0:
            raise serializers.ValidationError({'price': "Price cannot be negative."})
        if original is not None and original < 0:
            raise serializers.ValidationError({'original': "Original price cannot be negative."})
        if price is not None and original is not None and price > original:
            raise serializers.ValidationError({'price': "Discounted price cannot exceed original price."})

        return attrs


# Address

class AddressSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Address
        fields = ['id', 'user', 'name', 'line', 'area', 'is_default', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Address label cannot be empty.")
        return value.strip()

    def validate_line(self, value):
        if not value.strip():
            raise serializers.ValidationError("Address line cannot be empty.")
        return value.strip()

    def validate_area(self, value):
        if not value.strip():
            raise serializers.ValidationError("Locality/Area cannot be empty.")
        return value.strip()


# Cart

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_available=True),
        source='product',
        write_only=True,
    )
    key = serializers.CharField(read_only=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    unit_original = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_savings = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = [
            'id',
            'key',
            'product_id',
            'product',
            'quantity',
            'large',
            'unit_price',
            'unit_original',
            'total_price',
            'total_savings',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'key', 'created_at', 'updated_at']

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        product = validated_data['product']
        large = validated_data.get('large', False)
        quantity = validated_data.get('quantity', 1)

        # Upsert logic: if item exists for user with same pack size, increment quantity
        cart_item, created = CartItem.objects.get_or_create(
            user=user,
            product=product,
            large=large,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        return cart_item


class CartItemQuantityUpdateSerializer(serializers.Serializer):
    delta = serializers.IntegerField(required=False, default=0)
    quantity = serializers.IntegerField(required=False, min_value=0)

    def validate(self, attrs):
        if 'delta' not in attrs and 'quantity' not in attrs:
            raise serializers.ValidationError("Provide either 'delta' or 'quantity'.")
        return attrs


# Coupon & Offers

class CouponSerializer(serializers.ModelSerializer):
    discount_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = [
            'code',
            'description',
            'discount_rate',
            'discount_percentage',
            'max_discount',
            'min_order_value',
            'is_active',
        ]

    def get_discount_percentage(self, obj) -> int:
        return int(obj.discount_rate * 100)


class ApplyCouponSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=30)
    item_total = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.00'))

    def validate_code(self, value):
        code = value.strip().upper()
        try:
            coupon = Coupon.objects.get(code=code, is_active=True)
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive coupon code.")
        self.context['coupon'] = coupon
        return code


# Order

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product',
            'product_name',
            'weight',
            'quantity',
            'large',
            'unit_price',
            'total_price',
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    delivery_address = AddressSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'status',
            'payment_method',
            'payment_status',
            'delivery_address',
            'delivery_address_snapshot',
            'item_total',
            'delivery_fee',
            'discount_amount',
            'grand_total',
            'coupon_code',
            'items',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'order_number', 'status', 'payment_status', 'created_at', 'updated_at']


class OrderCreateSerializer(serializers.Serializer):
    delivery_address_id = serializers.IntegerField(required=False, allow_null=True)
    coupon_code = serializers.CharField(required=False, allow_blank=True, max_length=30)
    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_METHOD_CHOICES, default='COD', required=False)

    def validate_delivery_address_id(self, value):
        if value:
            user = self.context['request'].user
            if not Address.objects.filter(id=value, user=user).exists():
                raise serializers.ValidationError("Delivery address does not exist or does not belong to you.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        address_id = validated_data.get('delivery_address_id')
        coupon_code = validated_data.get('coupon_code', '').strip().upper()
        payment_method = validated_data.get('payment_method', 'COD')

        # Fetch user cart items
        cart_items = list(CartItem.objects.filter(user=user).select_related('product'))
        if not cart_items:
            raise serializers.ValidationError("Your basket is empty. Add products before placing an order.")

        # Check stock availability for all products in cart
        for item in cart_items:
            needed = item.quantity * 2 if item.large else item.quantity
            if not item.product.is_available or item.product.stock < needed:
                raise serializers.ValidationError(
                    f"Insufficient stock for '{item.product.name}'. Only {item.product.stock} available (requested {needed})."
                )

        # Deduct stock atomically
        for item in cart_items:
            needed = item.quantity * 2 if item.large else item.quantity
            item.product.stock -= needed
            if item.product.stock == 0:
                item.product.is_available = False
            item.product.save(update_fields=['stock', 'is_available'])

        # Resolve address
        address = None
        if address_id:
            address = Address.objects.filter(id=address_id, user=user).first()
        else:
            address = Address.objects.filter(user=user, is_default=True).first() or Address.objects.filter(user=user).first()

        address_snapshot = {}
        if address:
            address_snapshot = {
                'name': address.name,
                'line': address.line,
                'area': address.area,
            }

        # Calculate item totals
        item_total = sum(item.total_price for item in cart_items)
        delivery_fee = Decimal('0.00') if item_total >= FREE_DELIVERY_THRESHOLD else STANDARD_DELIVERY_FEE

        discount_amount = Decimal('0.00')
        valid_coupon_code = ''
        if coupon_code:
            coupon = Coupon.objects.filter(code=coupon_code, is_active=True).first()
            if coupon:
                discount_amount = coupon.calculate_discount(item_total)
                valid_coupon_code = coupon.code

        grand_total = max(Decimal('0.00'), item_total + delivery_fee - discount_amount)
        order_number = f"FR{uuid.uuid4().hex[:6].upper()}"

        order = Order.objects.create(
            order_number=order_number,
            user=user,
            status='placed',
            payment_method=payment_method,
            payment_status='pending',
            delivery_address=address,
            delivery_address_snapshot=address_snapshot,
            item_total=item_total,
            delivery_fee=delivery_fee,
            discount_amount=discount_amount,
            grand_total=grand_total,
            coupon_code=valid_coupon_code,
        )

        order_items = [
            OrderItem(
                order=order,
                product=item.product,
                product_name=item.product.name,
                weight='Double pack' if item.large else item.product.weight,
                quantity=item.quantity,
                large=item.large,
                unit_price=item.unit_price,
                total_price=item.total_price,
            )
            for item in cart_items
        ]
        OrderItem.objects.bulk_create(order_items)

        # Clear user cart after placing order
        CartItem.objects.filter(user=user).delete()

        return order


# Favorite & FAQ

class FavoriteProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = FavoriteProduct
        fields = ['id', 'product_id', 'product', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        user = self.context['request'].user
        product = validated_data['product']
        fav, _ = FavoriteProduct.objects.get_or_create(user=user, product=product)
        return fav


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ['id', 'question', 'answer', 'order']


# Admin Management System

class AdminLoginSerializer(serializers.Serializer):
    """
    Admin authentication with role verification.
    Only allows access to users with staff, superuser, or admin/manager role.
    """
    username = serializers.CharField(help_text="Username or email address")
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        login_input = attrs.get('username', '').strip()
        password = attrs.get('password')

        if not login_input or not password:
            raise serializers.ValidationError("Both username/email and password are required.")

        auth_username = login_input
        if '@' in login_input:
            matched = User.objects.filter(email__iexact=login_input).first()
            if matched:
                auth_username = matched.username

        user = authenticate(username=auth_username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid username/email or password.")
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled.")

        is_admin = user.is_superuser or user.is_staff or (
            hasattr(user, 'profile') and user.profile.role in ['admin', 'manager']
        )
        if not is_admin:
            raise serializers.ValidationError("Access denied. Administrator privileges required.")

        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        attrs['user'] = user
        attrs['tokens'] = {
            'access': access,
            'refresh': str(refresh),
        }
        return attrs


class AdminUserSerializer(serializers.ModelSerializer):
    """
    Serializer for admin user profile responses.
    """
    role = serializers.CharField(source='profile.role', default='admin', read_only=True)
    phone_number = serializers.CharField(source='profile.phone_number', default='', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_staff',
            'is_superuser',
            'is_active',
            'phone_number',
            'date_joined',
            'last_login',
        ]
        read_only_fields = fields


class AdminCategorySerializer(serializers.ModelSerializer):
    """
    Category CRUD for administrators, with safe slug generation, product counters,
    and explicit image removal support.
    """
    id = serializers.CharField(required=False, help_text="Slug ID (e.g. 'vegetables') or leave blank to auto-slugify")
    products_count = serializers.SerializerMethodField()
    remove_image = serializers.BooleanField(required=False, write_only=True, default=False)

    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'photo',
            'tint',
            'image',
            'remove_image',
            'is_active',
            'products_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_products_count(self, obj) -> int:
        return obj.products.count()

    def create(self, validated_data):
        validated_data.pop('remove_image', None)
        cat_id = validated_data.get('id')
        if not cat_id:
            base_slug = slugify(validated_data['name']) or 'cat'
            slug = base_slug
            counter = 1
            while Category.objects.filter(id=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            validated_data['id'] = slug
        return super().create(validated_data)

    def update(self, instance, validated_data):
        remove_image = validated_data.pop('remove_image', False)
        if remove_image and 'image' not in validated_data:
            if instance.image:
                instance.image.delete(save=False)
            instance.image = None
        return super().update(instance, validated_data)


class AdminProductSerializer(serializers.ModelSerializer):
    """
    Product CRUD for administrators with full pricing, stock, image upload and availability control.
    """
    id = serializers.CharField(required=False, help_text="Product slug id (e.g. 'fresh-apples') or leave blank to auto-slugify")
    category_name = serializers.CharField(source='category.name', read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'weight',
            'price',
            'original',
            'discount_percentage',
            'photo',
            'category',
            'category_name',
            'popular',
            'organic',
            'description',
            'stock',
            'image',
            'is_available',
            'is_low_stock',
            'is_out_of_stock',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock units cannot be negative.")
        return value

    def validate(self, attrs):
        price = attrs.get('price', getattr(self.instance, 'price', None))
        original = attrs.get('original', getattr(self.instance, 'original', None))

        if price is not None and price < 0:
            raise serializers.ValidationError({'price': "Price cannot be negative."})
        if original is not None and original < 0:
            raise serializers.ValidationError({'original': "Original price cannot be negative."})
        if price is not None and original is not None and price > original:
            raise serializers.ValidationError({'price': "Discounted price cannot exceed original price."})

        return attrs

    def create(self, validated_data):
        prod_id = validated_data.get('id')
        if not prod_id:
            base_slug = slugify(validated_data['name']) or 'item'
            slug = base_slug
            counter = 1
            while Product.objects.filter(id=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            validated_data['id'] = slug
        return super().create(validated_data)


class AdminOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product',
            'product_name',
            'weight',
            'quantity',
            'large',
            'unit_price',
            'total_price',
        ]


class AdminOrderListSerializer(serializers.ModelSerializer):
    """
    Compact order summary for admin listings with customer overview.
    """
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.CharField(source='user.email', read_only=True)
    customer_username = serializers.CharField(source='user.username', read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'status',
            'payment_method',
            'payment_status',
            'customer_username',
            'customer_name',
            'customer_email',
            'items_count',
            'item_total',
            'delivery_fee',
            'discount_amount',
            'grand_total',
            'coupon_code',
            'created_at',
            'updated_at',
        ]

    def get_customer_name(self, obj) -> str:
        name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return name or obj.user.username

    def get_items_count(self, obj) -> int:
        return obj.items.count()


class AdminOrderDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive order details for admin inspection.
    """
    customer = serializers.SerializerMethodField()
    items = AdminOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'status',
            'payment_method',
            'payment_status',
            'customer',
            'delivery_address',
            'delivery_address_snapshot',
            'items',
            'item_total',
            'delivery_fee',
            'discount_amount',
            'grand_total',
            'coupon_code',
            'created_at',
            'updated_at',
        ]

    def get_customer(self, obj) -> dict:
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'email': obj.user.email,
            'full_name': f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username,
            'phone_number': getattr(obj.user.profile, 'phone_number', '') if hasattr(obj.user, 'profile') else '',
        }


class AdminOrderStatusUpdateSerializer(serializers.Serializer):
    """
    Admin updating order status, payment status, and payment method.
    """
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES, required=False)
    payment_status = serializers.ChoiceField(choices=Order.PAYMENT_STATUS_CHOICES, required=False)
    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_METHOD_CHOICES, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field (status, payment_status, payment_method) is required.")
        return attrs


class AdminCustomerSerializer(serializers.ModelSerializer):
    """
    Registered customer listing with metrics for admin dashboard.
    """
    role = serializers.CharField(source='profile.role', default='customer', read_only=True)
    phone_number = serializers.CharField(source='profile.phone_number', default='', read_only=True)
    orders_count = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'role',
            'is_active',
            'is_staff',
            'orders_count',
            'total_spent',
            'date_joined',
            'last_login',
        ]

    def get_orders_count(self, obj) -> int:
        if hasattr(obj, 'annotated_orders_count'):
            return obj.annotated_orders_count
        return obj.orders.count()

    def get_total_spent(self, obj) -> Decimal:
        if hasattr(obj, 'annotated_total_spent'):
            return obj.annotated_total_spent
        spent = obj.orders.exclude(status='cancelled').aggregate(total=models.Sum('grand_total'))['total']
        return spent or Decimal('0.00')


class AdminCustomerDetailSerializer(AdminCustomerSerializer):
    """
    Detailed customer inspection with addresses and recent orders.
    """
    addresses = AddressSerializer(many=True, read_only=True)
    recent_orders = serializers.SerializerMethodField()

    class Meta(AdminCustomerSerializer.Meta):
        fields = AdminCustomerSerializer.Meta.fields + ['addresses', 'recent_orders']

    @extend_schema_field(AdminOrderListSerializer(many=True))
    def get_recent_orders(self, obj):
        orders = obj.orders.all()[:10]
        return AdminOrderListSerializer(orders, many=True).data


class AdminInventoryStockAdjustSerializer(serializers.Serializer):
    """
    Single product stock adjustment.
    """
    product_id = serializers.CharField()
    stock = serializers.IntegerField(min_value=0, required=False)
    adjustment = serializers.IntegerField(required=False, help_text="Delta to add or subtract (e.g. +10, -5)")

    def validate(self, attrs):
        if 'stock' not in attrs and 'adjustment' not in attrs:
            raise serializers.ValidationError("Either 'stock' or 'adjustment' must be provided.")
        prod_id = attrs.get('product_id')
        if not Product.objects.filter(id=prod_id).exists():
            raise serializers.ValidationError(f"Product with id '{prod_id}' does not exist.")
        return attrs


class AdminBatchStockAdjustSerializer(serializers.Serializer):
    """
    Batch stock adjustment payload.
    """
    adjustments = AdminInventoryStockAdjustSerializer(many=True, allow_empty=False)


