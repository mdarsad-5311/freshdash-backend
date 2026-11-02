from django.db.models import F, ExpressionWrapper, DecimalField
from django_filters import rest_framework as filters
from .models import Product

FEATURED_VEGETABLE_IDS = ['tomato', 'potato', 'onion', 'broccoli', 'carrot']
FEATURED_FRUIT_IDS = ['banana', 'apple', 'mango', 'avocado']
FRUIT_CATEGORY_IDS = ['fruits', 'seasonal', 'exotic-fruits']


class ProductFilter(filters.FilterSet):
    """
    Advanced filter for produce products supporting category tabs,
    organic filter, popular items, offers, and featured shelves.
    """
    category = filters.CharFilter(method='filter_by_category')
    popular = filters.BooleanFilter(field_name='popular')
    organic = filters.BooleanFilter(field_name='organic')
    offers = filters.BooleanFilter(method='filter_by_offers')
    featured = filters.CharFilter(method='filter_by_featured')
    min_price = filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = filters.NumberFilter(field_name='price', lookup_expr='lte')

    class Meta:
        model = Product
        fields = ['category', 'popular', 'organic', 'offers', 'featured', 'min_price', 'max_price']

    def filter_by_category(self, queryset, name, value):
        if not value or value == 'all':
            return queryset
        val_lower = value.lower()

        if val_lower == 'vegetables':
            # Vegetables tab in FreshDash frontend includes all except fruit categories
            return queryset.exclude(category_id__in=FRUIT_CATEGORY_IDS)
        elif val_lower == 'fruits':
            # Fruits tab includes fruits, seasonal, exotic-fruits
            return queryset.filter(category_id__in=FRUIT_CATEGORY_IDS)
        elif val_lower == 'organic':
            return queryset.filter(organic=True)
        else:
            return queryset.filter(category_id=value)

    def filter_by_offers(self, queryset, name, value):
        if value:
            # Matches frontend discount criteria: (original - price) / original >= 0.20
            # Which is equivalent to: price <= original * 0.80
            return queryset.filter(original__gt=0, price__lte=F('original') * 0.8)
        return queryset

    def filter_by_featured(self, queryset, name, value):
        val = value.lower()
        if val == 'vegetables':
            return queryset.filter(id__in=FEATURED_VEGETABLE_IDS)
        elif val == 'fruits':
            return queryset.filter(id__in=FEATURED_FRUIT_IDS)
        return queryset

