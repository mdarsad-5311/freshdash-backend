from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from api.models import (
    Category,
    Product,
    Address,
    Coupon,
    FAQ,
    UserProfile,
    CartItem,
)

CATEGORIES_DATA = [
    {'id': 'vegetables', 'name': 'Fresh vegetables', 'photo': 0, 'tint': '#EEF4E8'},
    {'id': 'fruits', 'name': 'Fresh fruits', 'photo': 5, 'tint': '#FFF0E8'},
    {'id': 'leafy', 'name': 'Leafy vegetables', 'photo': 8, 'tint': '#EAF3E5'},
    {'id': 'roots', 'name': 'Root vegetables', 'photo': 9, 'tint': '#FFF0E3'},
    {'id': 'exotic-vegetables', 'name': 'Exotic vegetables', 'photo': 3, 'tint': '#EBF0E5'},
    {'id': 'seasonal', 'name': 'Seasonal fruits', 'photo': 6, 'tint': '#FFF4D9'},
    {'id': 'organic', 'name': 'Organic produce', 'photo': 10, 'tint': '#EEF2E2'},
    {'id': 'herbs', 'name': 'Herbs and chillies', 'photo': 11, 'tint': '#F8F5DD'},
    {'id': 'exotic-fruits', 'name': 'Exotic fruits', 'photo': 7, 'tint': '#F0F3E5'},
]

PRODUCTS_DATA = [
    {
        'id': 'tomato',
        'name': 'Fresh red tomatoes',
        'weight': '500 g',
        'price': Decimal('28.00'),
        'original': Decimal('36.00'),
        'photo': 0,
        'category_id': 'vegetables',
        'popular': True,
        'organic': False,
        'description': 'Firm, juicy tomatoes with a bright, naturally tangy flavour. Perfect for everyday curries, salads and homemade sauces.',
    },
    {
        'id': 'potato',
        'name': 'Farm fresh potatoes',
        'weight': '1 kg',
        'price': Decimal('35.00'),
        'original': Decimal('45.00'),
        'photo': 1,
        'category_id': 'roots',
        'popular': True,
        'organic': False,
        'description': 'Versatile potatoes with smooth skin and a soft, fluffy texture when cooked. Your everyday kitchen essential.',
    },
    {
        'id': 'onion',
        'name': 'Red onions',
        'weight': '1 kg',
        'price': Decimal('42.00'),
        'original': Decimal('55.00'),
        'photo': 2,
        'category_id': 'roots',
        'popular': True,
        'organic': False,
        'description': 'Crisp red onions with a bold flavour, handpicked for your daily cooking.',
    },
    {
        'id': 'broccoli',
        'name': 'Fresh green broccoli',
        'weight': '1 pc · 250–350 g',
        'price': Decimal('65.00'),
        'original': Decimal('85.00'),
        'photo': 3,
        'category_id': 'exotic-vegetables',
        'popular': False,
        'organic': True,
        'description': 'Tender, vibrant florets that are lovely steamed, stir-fried or roasted with a little olive oil.',
    },
    {
        'id': 'banana',
        'name': 'Banana Robusta',
        'weight': '6 pcs',
        'price': Decimal('48.00'),
        'original': Decimal('60.00'),
        'photo': 4,
        'category_id': 'fruits',
        'popular': True,
        'organic': False,
        'description': 'Naturally sweet, creamy bananas. A delicious breakfast companion or an easy on-the-go snack.',
    },
    {
        'id': 'apple',
        'name': 'Royal Gala apples',
        'weight': '4 pcs · 500–600 g',
        'price': Decimal('149.00'),
        'original': Decimal('189.00'),
        'photo': 5,
        'category_id': 'fruits',
        'popular': True,
        'organic': False,
        'description': 'Crunchy, aromatic apples with a lovely balance of sweetness and freshness.',
    },
    {
        'id': 'mango',
        'name': 'Alphonso mangoes',
        'weight': '2 pcs · 500 g',
        'price': Decimal('199.00'),
        'original': Decimal('249.00'),
        'photo': 6,
        'category_id': 'seasonal',
        'popular': True,
        'organic': False,
        'description': 'Golden mangoes with fragrant, rich flesh. Enjoy chilled, in a smoothie or straight from the slice.',
    },
    {
        'id': 'avocado',
        'name': 'Premium Hass avocado',
        'weight': '1 pc',
        'price': Decimal('129.00'),
        'original': Decimal('159.00'),
        'photo': 7,
        'category_id': 'exotic-fruits',
        'popular': False,
        'organic': True,
        'description': 'Rich, buttery avocado with a creamy texture. Delicious on toast, in salads or as a fresh guacamole.',
    },
    {
        'id': 'spinach',
        'name': 'Fresh spinach (Palak)',
        'weight': '250 g',
        'price': Decimal('25.00'),
        'original': Decimal('35.00'),
        'photo': 8,
        'category_id': 'leafy',
        'popular': False,
        'organic': True,
        'description': 'Tender green leaves, carefully selected for freshness. Rinse thoroughly before cooking.',
    },
    {
        'id': 'carrot',
        'name': 'Crunchy orange carrots',
        'weight': '500 g',
        'price': Decimal('39.00'),
        'original': Decimal('50.00'),
        'photo': 9,
        'category_id': 'roots',
        'popular': False,
        'organic': True,
        'description': 'Sweet, crunchy carrots for colourful salads, soups and a wholesome snack.',
    },
    {
        'id': 'pepper',
        'name': 'Colourful bell peppers — assorted',
        'weight': '3 pcs · 400–500 g',
        'price': Decimal('89.00'),
        'original': Decimal('110.00'),
        'photo': 10,
        'category_id': 'exotic-vegetables',
        'popular': False,
        'organic': False,
        'description': 'A colourful mix of crisp bell peppers. Add a fresh crunch to stir-fries, wraps and roasted vegetables.',
    },
    {
        'id': 'lemon',
        'name': 'Fresh lemons',
        'weight': '4 pcs',
        'price': Decimal('29.00'),
        'original': Decimal('40.00'),
        'photo': 11,
        'category_id': 'herbs',
        'popular': False,
        'organic': False,
        'description': 'Bright, juicy lemons for a refreshing squeeze in drinks, dressings and everyday meals.',
    },
]

FAQS_DATA = [
    {
        'question': 'How does FreshDash work?',
        'answer': 'Browse farm-fresh fruits, vegetables and greens. Add items to your basket and experience instant delivery in 10–15 minutes.',
        'order': 1,
    },
    {
        'question': 'Will checking out place a real order?',
        'answer': 'No, this is a local client demonstration showcasing quick-commerce UX, state management, and haptics.',
        'order': 2,
    },
    {
        'question': 'Can I change my delivery address?',
        'answer': 'Yes, switch between your saved Home and Work addresses from the address selector on the Home screen or in this section.',
        'order': 3,
    },
]


class Command(BaseCommand):
    help = "Seeds FreshDash database with initial categories, products, coupons, and demo user"

    def handle(self, *args, **options):
        self.stdout.write("Seeding FreshDash database...")

        # 1. Categories
        for cat in CATEGORIES_DATA:
            Category.objects.update_or_create(
                id=cat['id'],
                defaults={
                    'name': cat['name'],
                    'photo': cat['photo'],
                    'tint': cat['tint'],
                    'is_active': True,
                }
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(CATEGORIES_DATA)} categories"))

        # 2. Products
        for prod in PRODUCTS_DATA:
            Product.objects.update_or_create(
                id=prod['id'],
                defaults={
                    'name': prod['name'],
                    'weight': prod['weight'],
                    'price': prod['price'],
                    'original': prod['original'],
                    'photo': prod['photo'],
                    'category_id': prod['category_id'],
                    'popular': prod['popular'],
                    'organic': prod['organic'],
                    'description': prod['description'],
                    'is_available': True,
                }
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(PRODUCTS_DATA)} products"))

        # 3. Coupons
        Coupon.objects.update_or_create(
            code='FRESH20',
            defaults={
                'description': 'Get 20% off your basket, up to ₹50.',
                'discount_rate': Decimal('0.20'),
                'max_discount': Decimal('50.00'),
                'min_order_value': Decimal('0.00'),
                'is_active': True,
            }
        )
        self.stdout.write(self.style.SUCCESS("Seeded FRESH20 coupon"))

        # 4. FAQs
        for faq in FAQS_DATA:
            FAQ.objects.update_or_create(
                question=faq['question'],
                defaults={
                    'answer': faq['answer'],
                    'order': faq['order'],
                    'is_active': True,
                }
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(FAQS_DATA)} FAQs"))

        # 5. Demo user
        demo_user, created = User.objects.get_or_create(
            username='fresh_foodie',
            defaults={
                'email': 'foodie@freshdash.local',
                'first_name': 'Fresh',
                'last_name': 'Foodie',
            }
        )
        if created:
            demo_user.set_password('FreshFoodie123!')
            demo_user.save()
            self.stdout.write(self.style.SUCCESS("Created demo user: fresh_foodie"))
        else:
            self.stdout.write("Demo user fresh_foodie already exists")

        token, _ = Token.objects.get_or_create(user=demo_user)
        self.stdout.write(self.style.SUCCESS(f"Demo user token: {token.key}"))

        # 6. Saved Addresses for Demo user
        Address.objects.update_or_create(
            user=demo_user,
            name='Home',
            defaults={
                'line': '24, 18th Main Road, Sector 2',
                'area': 'HSR Layout, Bengaluru · 560102',
                'is_default': True,
            }
        )
        Address.objects.update_or_create(
            user=demo_user,
            name='Work',
            defaults={
                'line': '8, 100 Feet Road',
                'area': 'Indiranagar, Bengaluru · 560038',
                'is_default': False,
            }
        )
        self.stdout.write(self.style.SUCCESS("Seeded Home & Work addresses for demo user"))

        # 7. Initial Basket Items (matching frontend demo store)
        tomato = Product.objects.filter(id='tomato').first()
        banana = Product.objects.filter(id='banana').first()
        broccoli = Product.objects.filter(id='broccoli').first()

        if tomato:
            CartItem.objects.update_or_create(user=demo_user, product=tomato, large=False, defaults={'quantity': 1})
        if banana:
            CartItem.objects.update_or_create(user=demo_user, product=banana, large=False, defaults={'quantity': 1})
        if broccoli:
            CartItem.objects.update_or_create(user=demo_user, product=broccoli, large=False, defaults={'quantity': 1})

        self.stdout.write(self.style.SUCCESS("Seeded sample cart items for demo user"))
        self.stdout.write(self.style.SUCCESS("FreshDash seeding completed successfully!"))

