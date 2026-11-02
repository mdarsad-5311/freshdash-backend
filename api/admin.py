from django.contrib import admin
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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'photo', 'tint', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('id', 'name')
    ordering = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'weight',
        'price',
        'original',
        'category',
        'popular',
        'organic',
        'is_available',
    )
    list_filter = ('category', 'popular', 'organic', 'is_available')
    search_fields = ('id', 'name', 'description')
    ordering = ('name',)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'line', 'area', 'is_default', 'created_at')
    list_filter = ('name', 'is_default')
    search_fields = ('user__username', 'line', 'area')


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'quantity', 'large', 'created_at')
    list_filter = ('large',)
    search_fields = ('user__username', 'product__name')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'discount_rate',
        'max_discount',
        'min_order_value',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active',)
    search_fields = ('code', 'description')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'weight', 'quantity', 'large', 'unit_price', 'total_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number',
        'user',
        'status',
        'grand_total',
        'item_total',
        'delivery_fee',
        'discount_amount',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('order_number', 'user__username')
    inlines = [OrderItemInline]


@admin.register(FavoriteProduct)
class FavoriteProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'created_at')
    search_fields = ('user__username', 'product__name')


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'order', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('question', 'answer')
    ordering = ('order',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'order_updates', 'offers_notifications', 'created_at')
    list_filter = ('order_updates', 'offers_notifications')
    search_fields = ('user__username', 'phone_number')
