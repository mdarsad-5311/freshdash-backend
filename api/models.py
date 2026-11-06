from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver


class Category(models.Model):
    """
    Produce category (e.g. vegetables, fruits, leafy, roots, exotic).
    """
    id = models.CharField(primary_key=True, max_length=50, help_text="Slug identifier like 'vegetables'")
    name = models.CharField(max_length=100)
    photo = models.PositiveIntegerField(default=0, help_text="Atlas photo index for frontend produce photo")
    tint = models.CharField(max_length=20, default="#EEF4E8", help_text="Hex code tint for mobile card background")
    image = models.ImageField(upload_to='categories/', null=True, blank=True, help_text="Uploaded category banner or icon")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Produce product item.
    """
    id = models.CharField(primary_key=True, max_length=50, help_text="Unique slug id like 'tomato', 'banana'")
    name = models.CharField(max_length=200)
    weight = models.CharField(max_length=50, help_text="Weight or pack descriptor, e.g. '500 g', '6 pcs'")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    original = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    photo = models.PositiveIntegerField(default=0, help_text="Atlas photo index")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    popular = models.BooleanField(default=False, help_text="Flag for everyday bestsellers")
    organic = models.BooleanField(default=False, help_text="Flag for certified organic produce")
    description = models.TextField(blank=True)
    stock = models.PositiveIntegerField(default=50, validators=[MinValueValidator(0)], help_text="Available inventory units")
    image = models.ImageField(upload_to='products/', null=True, blank=True, help_text="Uploaded product photo")
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.weight})"

    @property
    def discount_percentage(self) -> int:
        if self.original and self.original > self.price:
            return round(100 * (1 - float(self.price) / float(self.original)))
        return 0

    @property
    def is_low_stock(self) -> bool:
        return 0 < self.stock <= 10

    @property
    def is_out_of_stock(self) -> bool:
        return self.stock == 0


class Address(models.Model):
    """
    User delivery addresses (e.g. Home, Work).
    """
    ADDRESS_TYPE_CHOICES = [
        ('Home', 'Home'),
        ('Work', 'Work'),
        ('Other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    name = models.CharField(max_length=50, choices=ADDRESS_TYPE_CHOICES, default='Home')
    line = models.CharField(max_length=255, help_text="Street address line")
    area = models.CharField(max_length=255, help_text="Locality, City, Postal code")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.name}: {self.line}, {self.area}"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Ensure other addresses for this user are not marked default
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class CartItem(models.Model):
    """
    Item stored in user shopping basket.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    large = models.BooleanField(default=False, help_text="Double pack variant")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        constraints = [
            models.UniqueConstraint(fields=['user', 'product', 'large'], name='unique_user_product_pack')
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({'Double' if self.large else 'Regular'}) x{self.quantity}"

    @property
    def key(self) -> str:
        return f"{self.product_id}:{'large' if self.large else 'regular'}"

    @property
    def unit_price(self) -> Decimal:
        return self.product.price * Decimal('2.0') if self.large else self.product.price

    @property
    def unit_original(self) -> Decimal:
        return self.product.original * Decimal('2.0') if self.large else self.product.original

    @property
    def total_price(self) -> Decimal:
        return self.unit_price * Decimal(self.quantity)

    @property
    def total_savings(self) -> Decimal:
        return (self.unit_original - self.unit_price) * Decimal(self.quantity)


class Coupon(models.Model):
    """
    Promotional offers and discounts (e.g. FRESH20).
    """
    code = models.CharField(primary_key=True, max_length=30)
    description = models.CharField(max_length=255)
    discount_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.20'),
        help_text="Discount percentage in decimal form (0.20 for 20%)"
    )
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50.00'))
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"

    def __str__(self):
        return f"{self.code} ({int(self.discount_rate * 100)}% off, up to ₹{self.max_discount})"

    def calculate_discount(self, item_total: Decimal) -> Decimal:
        if not self.is_active or item_total < self.min_order_value:
            return Decimal('0.00')
        raw_discount = item_total * self.discount_rate
        return min(self.max_discount, raw_discount).quantize(Decimal('1.00'))


class Order(models.Model):
    """
    Customer orders placed via FreshDash.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('placed', 'Placed'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('COD', 'Cash on Delivery'),
        ('UPI', 'UPI Payment'),
        ('Card', 'Credit/Debit Card'),
        ('NetBanking', 'Net Banking'),
        ('Wallet', 'Digital Wallet'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    order_number = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='placed')
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='COD')
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default='pending')
    delivery_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    delivery_address_snapshot = models.JSONField(default=dict, blank=True)
    item_total = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=10, decimal_places=2)
    coupon_code = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.order_number} ({self.get_status_display()}) - ₹{self.grand_total}"


class OrderItem(models.Model):
    """
    Individual items line within an order.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items")
    product_name = models.CharField(max_length=200)
    weight = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField(default=1)
    large = models.BooleanField(default=False)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self):
        return f"{self.product_name} x{self.quantity} in Order #{self.order.order_number}"


class FavoriteProduct(models.Model):
    """
    User favorite products for quick repurchase and bookmarks.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorite_products")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Favorite Product"
        verbose_name_plural = "Favorite Products"
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='unique_user_favorite_product')
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} loves {self.product.name}"


class FAQ(models.Model):
    """
    Frequently Asked Questions displayed in Help & Support.
    """
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        ordering = ["order", "id"]

    def __str__(self):
        return self.question


class UserProfile(models.Model):
    """
    Mobile user settings and profile metadata.
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('customer', 'Customer'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    phone_number = models.CharField(max_length=20, blank=True)
    order_updates = models.BooleanField(default=True)
    offers_notifications = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"Profile of {self.user.username} ({self.role})"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        role = 'admin' if (instance.is_staff or instance.is_superuser) else 'customer'
        UserProfile.objects.create(user=instance, role=role)
    else:
        if hasattr(instance, 'profile'):
            if (instance.is_staff or instance.is_superuser) and instance.profile.role == 'customer':
                instance.profile.role = 'admin'
                instance.profile.save()
            else:
                instance.profile.save()
