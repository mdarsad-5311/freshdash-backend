from decimal import Decimal
from datetime import timedelta
from io import BytesIO
import time
from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

from api.models import (
    Category,
    Product,
    Address,
    CartItem,
    Coupon,
    Order,
    OrderItem,
    FavoriteProduct,
    FAQ,
)


class FreshDashAPITestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Users
        self.user = User.objects.create_user(
            username='alice',
            password='Password123!',
            email='alice@freshdash.local',
            first_name='Alice'
        )
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.user_refresh = RefreshToken.for_user(self.user)
        self.user_access = str(self.user_refresh.access_token)

        self.other_user = User.objects.create_user(
            username='bob',
            password='Password123!',
            email='bob@freshdash.local'
        )
        self.other_token, _ = Token.objects.get_or_create(user=self.other_user)
        self.other_refresh = RefreshToken.for_user(self.other_user)
        self.other_access = str(self.other_refresh.access_token)

        # Admin user
        self.admin_user = User.objects.create_superuser(
            username='admin_user',
            password='AdminPassword123!',
            email='admin@freshdash.local'
        )
        self.admin_token, _ = Token.objects.get_or_create(user=self.admin_user)
        self.admin_refresh = RefreshToken.for_user(self.admin_user)
        self.admin_access = str(self.admin_refresh.access_token)

        # Categories
        self.cat_veg = Category.objects.create(
            id='vegetables',
            name='Fresh vegetables',
            photo=0,
            tint='#EEF4E8'
        )
        self.cat_fruits = Category.objects.create(
            id='fruits',
            name='Fresh fruits',
            photo=5,
            tint='#FFF0E8'
        )
        self.cat_roots = Category.objects.create(
            id='roots',
            name='Root vegetables',
            photo=9,
            tint='#FFF0E3'
        )

        # Products
        self.product_tomato = Product.objects.create(
            id='tomato',
            name='Fresh red tomatoes',
            weight='500 g',
            price=Decimal('28.00'),
            original=Decimal('36.00'),
            photo=0,
            category=self.cat_veg,
            popular=True,
            organic=False,
            description='Firm, juicy tomatoes'
        )
        self.product_potato = Product.objects.create(
            id='potato',
            name='Farm fresh potatoes',
            weight='1 kg',
            price=Decimal('35.00'),
            original=Decimal('45.00'),
            photo=1,
            category=self.cat_roots,
            popular=True,
            organic=False,
            description='Smooth skin potatoes'
        )
        self.product_banana = Product.objects.create(
            id='banana',
            name='Banana Robusta',
            weight='6 pcs',
            price=Decimal('48.00'),
            original=Decimal('60.00'),
            photo=4,
            category=self.cat_fruits,
            popular=True,
            organic=True,
            description='Sweet bananas'
        )

        # Coupon
        self.coupon = Coupon.objects.create(
            code='FRESH20',
            description='20% off up to ₹50',
            discount_rate=Decimal('0.20'),
            max_discount=Decimal('50.00'),
            min_order_value=Decimal('0.00'),
            is_active=True
        )

        # FAQ
        self.faq = FAQ.objects.create(
            question='How fast is delivery?',
            answer='10-15 minutes.',
            order=1
        )

        # Address
        self.address = Address.objects.create(
            user=self.user,
            name='Home',
            line='24, 18th Main Road',
            area='HSR Layout, Bengaluru',
            is_default=True
        )

    # -------------------------------------------------------------------------
    # 1. System & Health Check Tests
    # -------------------------------------------------------------------------
    def test_health_check_endpoint(self):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')

    # -------------------------------------------------------------------------
    # 2. Phase 4 — User Authentication & Password Security Tests
    # -------------------------------------------------------------------------
    def test_user_signup_success(self):
        payload = {
            'username': 'newcustomer',
            'email': 'customer@freshdash.local',
            'password': 'StrongPassword123!',
            'first_name': 'New',
            'last_name': 'Customer',
            'phone_number': '9876543210'
        }
        response = self.client.post('/api/v1/auth/signup/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
        self.assertEqual(response.data['user']['username'], 'newcustomer')
        self.assertEqual(response.data['user']['email'], 'customer@freshdash.local')
        # Ensure password hash is NEVER exposed in response
        self.assertNotIn('password', response.data['user'])

    def test_user_signup_duplicate_email(self):
        payload = {
            'username': 'unique_user',
            'email': 'ALICE@FRESHDASH.LOCAL',  # Case-insensitive duplicate of existing user
            'password': 'StrongPassword123!',
        }
        response = self.client.post('/api/v1/auth/signup/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('email', response.data['errors'])

    def test_user_signup_invalid_email(self):
        payload = {
            'username': 'invalid_email_user',
            'email': 'not-a-valid-email',
            'password': 'StrongPassword123!',
        }
        response = self.client.post('/api/v1/auth/signup/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('email', response.data['errors'])

    def test_user_signup_weak_password(self):
        # Weak password (less than 8 characters, common, or too simple)
        payload = {
            'username': 'weak_pw_user',
            'email': 'weak@freshdash.local',
            'password': '123',  # Too short and numeric
        }
        response = self.client.post('/api/v1/auth/signup/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('password', response.data['errors'])

    def test_user_login_with_username(self):
        payload = {
            'username': 'alice',
            'password': 'Password123!'
        }
        response = self.client.post('/api/v1/auth/login/', payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
        self.assertEqual(response.data['user']['username'], 'alice')

    def test_user_login_with_email(self):
        # Phase 4 requirement: Support email-based login while preserving username-based login
        payload = {
            'username': 'ALICE@freshdash.local',  # email passed as login identifier
            'password': 'Password123!'
        }
        response = self.client.post('/api/v1/auth/login/', payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['user']['username'], 'alice')
        self.assertIn('tokens', response.data)

    def test_user_login_incorrect_password(self):
        payload = {
            'username': 'alice',
            'password': 'WrongPassword123!'
        }
        response = self.client.post('/api/v1/auth/login/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        # Secure error response without exposing whether user exists
        self.assertIn("Invalid", response.data['message'])

    def test_user_login_missing_credentials(self):
        payload = {'username': ''}
        response = self.client.post('/api/v1/auth/login/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])

    # -------------------------------------------------------------------------
    # 3. Phase 4 — JWT Security: Token Expiration, Rotation & Blacklisting
    # -------------------------------------------------------------------------
    def test_jwt_access_protected_endpoint(self):
        # Authenticate using Bearer JWT
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        response = self.client.get('/api/v1/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'alice')

    def test_jwt_invalid_access_token(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid.tampered.token')
        response = self.client.get('/api/v1/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])

    def test_jwt_token_refresh_rotation(self):
        payload = {'refresh': str(self.user_refresh)}
        response = self.client.post('/api/v1/auth/token/refresh/', payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        tokens = response.data['tokens']
        self.assertIn('access', tokens)
        self.assertIn('refresh', tokens)

        # Refresh token rotation verification: new refresh token is issued
        new_refresh = tokens['refresh']
        self.assertNotEqual(new_refresh, str(self.user_refresh))

        # Old refresh token is blacklisted and cannot be reused
        old_refresh_retry = self.client.post('/api/v1/auth/token/refresh/', {'refresh': str(self.user_refresh)})
        self.assertEqual(old_refresh_retry.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_invalid_refresh_token(self):
        payload = {'refresh': 'invalid-token-string'}
        response = self.client.post('/api/v1/auth/token/refresh/', payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_logout_and_blacklisting(self):
        # Generate fresh refresh token for logout test
        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        logout_res = self.client.post('/api/v1/auth/logout/', {'refresh': str(refresh)})
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)
        self.assertTrue(logout_res.data['success'])

        # Verify the blacklisted refresh token can no longer be used for refresh
        refresh_attempt = self.client.post('/api/v1/auth/token/refresh/', {'refresh': str(refresh)})
        self.assertEqual(refresh_attempt.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthorized_api_access(self):
        # Requesting private resources without credentials
        self.client.credentials()  # Clear auth headers
        res_cart = self.client.get('/api/v1/cart/')
        self.assertEqual(res_cart.status_code, status.HTTP_401_UNAUTHORIZED)

        res_addr = self.client.get('/api/v1/addresses/')
        self.assertEqual(res_addr.status_code, status.HTTP_401_UNAUTHORIZED)

        res_orders = self.client.get('/api/v1/orders/')
        self.assertEqual(res_orders.status_code, status.HTTP_401_UNAUTHORIZED)

    # -------------------------------------------------------------------------
    # 4. Phase 4 — Cross-User IDOR Prevention Tests
    # -------------------------------------------------------------------------
    def test_cross_user_idor_prevention(self):
        # Alice creates an address
        alice_addr = self.address  # id belonging to Alice

        # Bob logs in with JWT
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.other_access}')

        # 1. Bob attempts to GET Alice's address by ID -> 404
        get_res = self.client.get(f'/api/v1/addresses/{alice_addr.id}/')
        self.assertEqual(get_res.status_code, status.HTTP_404_NOT_FOUND)

        # 2. Bob attempts to PUT/PATCH Alice's address -> 404
        patch_res = self.client.patch(f'/api/v1/addresses/{alice_addr.id}/', {'name': 'Hacked'})
        self.assertEqual(patch_res.status_code, status.HTTP_404_NOT_FOUND)

        # 3. Bob attempts to DELETE Alice's address -> 404
        del_res = self.client.delete(f'/api/v1/addresses/{alice_addr.id}/')
        self.assertEqual(del_res.status_code, status.HTTP_404_NOT_FOUND)

        # 4. Bob attempts to place an order using Alice's address ID -> 400 Bad Request
        CartItem.objects.create(user=self.other_user, product=self.product_tomato, quantity=1)
        order_payload = {'delivery_address_id': alice_addr.id}
        order_res = self.client.post('/api/v1/orders/', order_payload)
        self.assertEqual(order_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("delivery_address_id", order_res.data['errors'])

    # -------------------------------------------------------------------------
    # 5. Phase 4 — Rate Limiting Tests
    # -------------------------------------------------------------------------
    def test_rate_limiting_on_login(self):
        cache.clear()
        payload = {'username': 'non_existent_user', 'password': 'bad_password'}
        responses = []
        for _ in range(7):
            responses.append(self.client.post('/api/v1/auth/login/', payload))

        # With 5/min rate limit, 6th or 7th request must be throttled with 429
        status_codes = [r.status_code for r in responses]
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, status_codes)

    # -------------------------------------------------------------------------
    # 6. Existing APIs & Functional Regression Tests
    # -------------------------------------------------------------------------
    def test_user_profile_get_and_update(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        response = self.client.get('/api/v1/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'alice')

        patch_payload = {
            'first_name': 'Alice Updated',
            'order_updates': False
        }
        patch_response = self.client.patch('/api/v1/profile/', patch_payload)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['user']['first_name'], 'Alice Updated')
        self.assertFalse(patch_response.data['user']['profile']['order_updates'])

    def test_categories_list(self):
        response = self.client.get('/api/v1/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(response.data['count'], 3)

    def test_products_list_pagination(self):
        response = self.client.get('/api/v1/products/?page_size=2')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(response.data['total_pages'], 2)

    def test_products_filtering_by_category(self):
        response = self.client.get('/api/v1/products/?category=fruits')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for prod in response.data['results']:
            self.assertEqual(prod['id'], 'banana')

    def test_products_filtering_by_organic(self):
        response = self.client.get('/api/v1/products/?organic=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for prod in response.data['results']:
            self.assertTrue(prod['organic'])

    def test_products_search(self):
        response = self.client.get('/api/v1/products/?search=tomato')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], 'tomato')

    def test_products_ordering(self):
        response = self.client.get('/api/v1/products/?ordering=-price')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prices = [float(p['price']) for p in response.data['results']]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_product_detail(self):
        response = self.client.get('/api/v1/products/tomato/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Fresh red tomatoes')
        self.assertEqual(response.data['discount_percentage'], 22)

    def test_product_pairs_well_with(self):
        response = self.client.get('/api/v1/products/tomato/pairs-well-with/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        for prod in response.data:
            self.assertNotEqual(prod['id'], 'tomato')

    def test_cart_operations_lifecycle(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')

        # Add tomato
        add_res = self.client.post('/api/v1/cart/', {'product_id': 'tomato', 'quantity': 2, 'large': False})
        self.assertEqual(add_res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(add_res.data['success'])
        self.assertEqual(add_res.data['summary']['total_items'], 2)

        # Partial update
        patch_res = self.client.patch('/api/v1/cart/tomato:regular/', {'delta': -1})
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['item']['quantity'], 1)

        # Delete by key
        del_res = self.client.delete('/api/v1/cart/tomato:regular/')
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)

        # Clear
        clear_res = self.client.post('/api/v1/cart/clear/')
        self.assertEqual(clear_res.status_code, status.HTTP_200_OK)
        self.assertEqual(clear_res.data['summary']['total_items'], 0)

    def test_apply_coupon_valid(self):
        payload = {'code': 'FRESH20', 'item_total': '200.00'}
        res = self.client.post('/api/v1/coupons/apply/', payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['valid'])
        self.assertEqual(Decimal(str(res.data['discount_amount'])), Decimal('40.00'))

    def test_order_placement_from_cart(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        self.client.post('/api/v1/cart/', {'product_id': 'tomato', 'quantity': 1})

        order_payload = {'delivery_address_id': self.address.id, 'coupon_code': 'FRESH20'}
        res = self.client.post('/api/v1/orders/', order_payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['success'])
        order_data = res.data['order']
        self.assertTrue(order_data['order_number'].startswith('FR'))

    def test_favorites_toggle_and_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        res = self.client.post('/api/v1/favorites/toggle/', {'product_id': 'tomato'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['is_favourite'])

        fav_list = self.client.get('/api/v1/favorites/')
        self.assertEqual(fav_list.status_code, status.HTTP_200_OK)
        self.assertEqual(fav_list.data['count'], 1)

    def test_faqs_list(self):
        res = self.client.get('/api/v1/faqs/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res.data['count'], 1)

    # -------------------------------------------------------------------------
    # 7. Phase 5.6: Integration & E2E Verification Tests
    # -------------------------------------------------------------------------
    def test_address_crud_and_set_default(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')

        # 1. Create new address
        create_res = self.client.post('/api/v1/addresses/', {
            'name': 'Work',
            'line': '8, 100 Feet Road',
            'area': 'Indiranagar, Bengaluru · 560038',
            'is_default': False,
        })
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        addr_id = create_res.data['id']
        self.assertEqual(create_res.data['name'], 'Work')

        # 2. Retrieve address
        get_res = self.client.get(f'/api/v1/addresses/{addr_id}/')
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data['line'], '8, 100 Feet Road')

        # 3. Partial update
        patch_res = self.client.patch(f'/api/v1/addresses/{addr_id}/', {
            'line': '12, 100 Feet Road, Suite 400',
        })
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['line'], '12, 100 Feet Road, Suite 400')

        # 4. Set as default
        default_res = self.client.post(f'/api/v1/addresses/{addr_id}/set-default/')
        self.assertEqual(default_res.status_code, status.HTTP_200_OK)
        self.assertTrue(default_res.data['address']['is_default'])

        # Verify old address is no longer default
        self.address.refresh_from_db()
        self.assertFalse(self.address.is_default)

        # 5. Delete address
        del_res = self.client.delete(f'/api/v1/addresses/{addr_id}/')
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)

        # Verify 404 after delete
        get_after_del = self.client.get(f'/api/v1/addresses/{addr_id}/')
        self.assertEqual(get_after_del.status_code, status.HTTP_404_NOT_FOUND)

    def test_order_creation_empty_cart_rejection(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        # Ensure cart is empty
        self.client.post('/api/v1/cart/clear/')

        res = self.client.post('/api/v1/orders/', {'delivery_address_id': self.address.id})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('basket is empty', str(res.data))

    def test_order_creation_invalid_address_rejection(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        self.client.post('/api/v1/cart/', {'product_id': 'tomato', 'quantity': 1})

        # Non-existent address ID (999999)
        res = self.client.post('/api/v1/orders/', {'delivery_address_id': 999999})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_delivery_fee_free_threshold(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')

        # 1. Under ₹199 -> ₹20 delivery fee
        # 1 tomato = ₹28 -> fee = 20 -> grand total = ₹48
        self.client.post('/api/v1/cart/', {'product_id': 'tomato', 'quantity': 1})
        order_res1 = self.client.post('/api/v1/orders/', {'delivery_address_id': self.address.id})
        self.assertEqual(order_res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(str(order_res1.data['order']['delivery_fee'])), Decimal('20.00'))

        # 2. Over ₹199 -> free delivery (fee = 0)
        # 8 bananas @ ₹48 = ₹384 -> fee = 0
        self.client.post('/api/v1/cart/', {'product_id': 'banana', 'quantity': 8})
        order_res2 = self.client.post('/api/v1/orders/', {'delivery_address_id': self.address.id})
        self.assertEqual(order_res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(str(order_res2.data['order']['delivery_fee'])), Decimal('0.00'))

    def test_cart_user_isolation(self):
        # Alice adds tomato to cart
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        self.client.post('/api/v1/cart/', {'product_id': 'tomato', 'quantity': 2})

        # Bob logs in and checks cart -> should be empty
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.other_access}')
        bob_cart = self.client.get('/api/v1/cart/')
        self.assertEqual(bob_cart.status_code, status.HTTP_200_OK)
        self.assertEqual(len(bob_cart.data['items']), 0)

        # Bob adds potato
        self.client.post('/api/v1/cart/', {'product_id': 'potato', 'quantity': 1})

        # Alice's cart is still tomato only
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        alice_cart = self.client.get('/api/v1/cart/')
        self.assertEqual(len(alice_cart.data['items']), 1)
        self.assertEqual(alice_cart.data['items'][0]['product']['id'], 'tomato')

    def test_user_profile_phone_and_notifications(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        patch_payload = {
            'first_name': 'Alice',
            'last_name': 'Green',
            'phone_number': '9876543210',
            'order_updates': True,
            'offers_notifications': True,
        }
        res = self.client.patch('/api/v1/auth/me/', patch_payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        user_data = res.data['user']
        self.assertEqual(user_data['first_name'], 'Alice')
        self.assertEqual(user_data['last_name'], 'Green')
        self.assertEqual(user_data['profile']['phone_number'], '9876543210')
        self.assertTrue(user_data['profile']['order_updates'])
        self.assertTrue(user_data['profile']['offers_notifications'])

    def test_order_history_and_detail_retrieval(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        self.client.post('/api/v1/cart/', {'product_id': 'tomato', 'quantity': 1})
        order_res = self.client.post('/api/v1/orders/', {'delivery_address_id': self.address.id})
        self.assertEqual(order_res.status_code, status.HTTP_201_CREATED)
        order_number = order_res.data['order']['order_number']

        # 1. Order history
        history_res = self.client.get('/api/v1/orders/')
        self.assertEqual(history_res.status_code, status.HTTP_200_OK)
        numbers = [o['order_number'] for o in history_res.data['results']]
        self.assertIn(order_number, numbers)

        # 2. Order detail by order number
        detail_res = self.client.get(f'/api/v1/orders/{order_number}/')
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_res.data['order_number'], order_number)
        self.assertEqual(len(detail_res.data['items']), 1)

    def test_category_products_action(self):
        res = self.client.get('/api/v1/categories/vegetables/products/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        prod_names = [p['id'] for p in res.data['results']]
        self.assertIn('tomato', prod_names)

    def test_product_bestsellers_and_seasonal_actions(self):
        # 1. Bestsellers action
        best_res = self.client.get('/api/v1/products/bestsellers/')
        self.assertEqual(best_res.status_code, status.HTTP_200_OK)
        best_ids = [p['id'] for p in best_res.data]
        self.assertIn('tomato', best_ids)

        # 2. Seasonal action (create a seasonal item first)
        Category.objects.get_or_create(id='seasonal', defaults={'name': 'Seasonal Special'})
        Product.objects.create(
            id='mango',
            name='Alphonso Mango',
            weight='1 kg',
            price=Decimal('120.00'),
            original=Decimal('150.00'),
            photo=3,
            category_id='seasonal',
            is_available=True,
        )
        season_res = self.client.get('/api/v1/products/seasonal/')
        self.assertEqual(season_res.status_code, status.HTTP_200_OK)
        season_ids = [p['id'] for p in season_res.data]
        self.assertIn('mango', season_ids)

    def test_product_admin_crud_permissions(self):
        # Regular user cannot create product
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        user_res = self.client.post('/api/v1/products/', {
            'id': 'spinach',
            'name': 'Fresh Palak',
            'weight': '250 g',
            'price': '20.00',
            'original': '25.00',
            'category': 'vegetables',
        })
        self.assertEqual(user_res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin user can create product
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        admin_res = self.client.post('/api/v1/products/', {
            'id': 'spinach',
            'name': 'Fresh Palak',
            'weight': '250 g',
            'price': '20.00',
            'original': '25.00',
            'category': 'vegetables',
            'is_available': True,
        })
        self.assertEqual(admin_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(admin_res.data['id'], 'spinach')

        # Admin user can update product
        patch_res = self.client.patch('/api/v1/products/spinach/', {'price': '18.00'})
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(patch_res.data['price'])), Decimal('18.00'))

        # Admin user can delete product
        del_res = self.client.delete('/api/v1/products/spinach/')
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)

    def test_product_validation_negative_and_excessive_price(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        # 1. Negative price
        neg_res = self.client.post('/api/v1/products/', {
            'id': 'coriander',
            'name': 'Fresh Coriander',
            'weight': '100 g',
            'price': '-10.00',
            'original': '20.00',
            'category': 'vegetables',
        })
        self.assertEqual(neg_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('price', str(neg_res.data))

        # 2. Discounted price > original price
        exc_res = self.client.post('/api/v1/products/', {
            'id': 'coriander',
            'name': 'Fresh Coriander',
            'weight': '100 g',
            'price': '50.00',
            'original': '20.00',
            'category': 'vegetables',
        })
        self.assertEqual(exc_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceed original price', str(exc_res.data))

    def test_cart_explicit_quantity_update_and_clear(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        # Add tomato
        self.client.post('/api/v1/cart/', {'product_id': 'tomato', 'quantity': 1})

        # Explicit quantity update to 5
        patch_res = self.client.patch('/api/v1/cart/tomato:regular/', {'quantity': 5})
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['item']['quantity'], 5)

        # Clear cart
        clear_res = self.client.post('/api/v1/cart/clear/')
        self.assertEqual(clear_res.status_code, status.HTTP_200_OK)
        self.assertEqual(clear_res.data['summary']['total_items'], 0)

    def test_cart_composite_key_and_double_pack(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        self.client.post('/api/v1/cart/clear/')

        # 1. Regular pack
        reg_res = self.client.post('/api/v1/cart/', {'product_id': 'tomato', 'quantity': 1, 'large': False})
        self.assertEqual(reg_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reg_res.data['item']['key'], 'tomato:regular')

        # 2. Large pack
        large_res = self.client.post('/api/v1/cart/', {'product_id': 'tomato', 'quantity': 1, 'large': True})
        self.assertEqual(large_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(large_res.data['item']['key'], 'tomato:large')

        # Verify bill summary has 2 items, total items = 2, large price = 2x regular
        # tomato price = 28.00, regular = 28, large = 56, total = 84
        cart_res = self.client.get('/api/v1/cart/')
        self.assertEqual(cart_res.status_code, status.HTTP_200_OK)
        self.assertEqual(cart_res.data['total_items'], 2)
        self.assertEqual(Decimal(str(cart_res.data['item_total'])), Decimal('84.00'))

    def test_address_invalid_input_validation(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')

        # Missing line
        res1 = self.client.post('/api/v1/addresses/', {
            'name': 'Home',
            'line': '   ',
            'area': 'Koramangala, Bengaluru',
        })
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('line', str(res1.data))

        # Missing area
        res2 = self.client.post('/api/v1/addresses/', {
            'name': 'Home',
            'line': 'Flat 101, Green Heights',
            'area': '',
        })
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('area', str(res2.data))

    def test_cross_user_order_idor_prevention(self):
        # Alice places an order
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        self.client.post('/api/v1/cart/', {'product_id': 'tomato', 'quantity': 1})
        alice_order = self.client.post('/api/v1/orders/', {'delivery_address_id': self.address.id})
        self.assertEqual(alice_order.status_code, status.HTTP_201_CREATED)
        order_number = alice_order.data['order']['order_number']

        # Bob logs in and attempts to access Alice's order
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.other_access}')
        bob_get = self.client.get(f'/api/v1/orders/{order_number}/')
        self.assertEqual(bob_get.status_code, status.HTTP_404_NOT_FOUND)

        # Bob's order history does not include Alice's order
        bob_history = self.client.get('/api/v1/orders/')
        self.assertEqual(bob_history.status_code, status.HTTP_200_OK)
        numbers = [o['order_number'] for o in bob_history.data['results']]
        self.assertNotIn(order_number, numbers)

    def test_coupon_validation_and_discount_caps(self):
        # 1. Non-existent coupon
        bad_res = self.client.post('/api/v1/coupons/apply/', {
            'code': 'INVALID999',
            'item_total': '250.00',
        })
        self.assertEqual(bad_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', str(bad_res.data))

        # 2. Inactive coupon
        Coupon.objects.create(
            code='EXPIRED50',
            description='Expired promo',
            discount_rate=Decimal('0.50'),
            max_discount=Decimal('100.00'),
            min_order_value=Decimal('0.00'),
            is_active=False,
        )
        inactive_res = self.client.post('/api/v1/coupons/apply/', {
            'code': 'EXPIRED50',
            'item_total': '200.00',
        })
        self.assertEqual(inactive_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('inactive', str(inactive_res.data).lower())

        # 3. Discount cap: FRESH20 gives 20% capped at ₹50.
        # On ₹1000 item total: 20% of 1000 = 200, but cap = ₹50
        cap_res = self.client.post('/api/v1/coupons/apply/', {
            'code': 'FRESH20',
            'item_total': '1000.00',
        })
        self.assertEqual(cap_res.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(cap_res.data['discount_amount'])), Decimal('50.00'))

    def test_favorite_validation_missing_and_invalid_product(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')

        # Missing product_id
        res1 = self.client.post('/api/v1/favorites/toggle/', {})
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(res1.data['success'])

        # Non-existent product_id
        res2 = self.client.post('/api/v1/favorites/toggle/', {'product_id': 'dragonfruit_not_found'})
        self.assertEqual(res2.status_code, status.HTTP_404_NOT_FOUND)

    def test_standardized_error_envelope_structure(self):
        # 1. 400 Bad Request
        res_400 = self.client.post('/api/v1/auth/signup/', {'username': 'test'})
        self.assertEqual(res_400.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('success', res_400.data)
        self.assertFalse(res_400.data['success'])
        self.assertEqual(res_400.data['status_code'], 400)
        self.assertIn('errors', res_400.data)

        # 2. 401 Unauthorized
        self.client.credentials()  # Clear credentials
        res_401 = self.client.get('/api/v1/auth/me/')
        self.assertEqual(res_401.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('success', res_401.data)
        self.assertFalse(res_401.data['success'])
        self.assertEqual(res_401.data['status_code'], 401)

        # 3. 404 Not Found
        res_404 = self.client.get('/api/v1/products/non-existent-product-id/')
        self.assertEqual(res_404.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('success', res_404.data)
        self.assertFalse(res_404.data['success'])
        self.assertEqual(res_404.data['status_code'], 404)

    def test_order_cancellation_and_status_restrictions(self):
        # Alice places an order
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        CartItem.objects.create(user=self.user, product=self.product_tomato, quantity=2)
        create_res = self.client.post('/api/v1/orders/', {'delivery_address_id': self.address.id})
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        order_number = create_res.data['order']['order_number']

        # 1. Cancel order successfully while placed
        cancel_res = self.client.post(f'/api/v1/orders/{order_number}/cancel/')
        self.assertEqual(cancel_res.status_code, status.HTTP_200_OK)
        self.assertTrue(cancel_res.data['success'])
        self.assertEqual(cancel_res.data['order']['status'], 'cancelled')

        # 2. Cannot cancel an already cancelled order -> 400 Bad Request
        dup_cancel_res = self.client.post(f'/api/v1/orders/{order_number}/cancel/')
        self.assertEqual(dup_cancel_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already cancelled", dup_cancel_res.data['message'])

        # 3. Cannot cancel delivered order -> 400 Bad Request
        order_obj = Order.objects.get(order_number=order_number)
        order_obj.status = 'delivered'
        order_obj.save()
        delivered_cancel_res = self.client.post(f'/api/v1/orders/{order_number}/cancel/')
        self.assertEqual(delivered_cancel_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be cancelled", delivered_cancel_res.data['message'])

        # 4. Bob cannot cancel Alice's order -> 404 Not Found (IDOR protection)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.other_access}')
        bob_cancel_res = self.client.post(f'/api/v1/orders/{order_number}/cancel/')
        self.assertEqual(bob_cancel_res.status_code, status.HTTP_404_NOT_FOUND)

    def test_coupon_apply_frontend_contract_fields(self):
        res = self.client.post('/api/v1/coupons/apply/', {
            'code': 'FRESH20',
            'item_total': '200.00',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['valid'])
        self.assertEqual(res.data['code'], 'FRESH20')
        # Check both backend and frontend contract keys
        self.assertIn('discount', res.data)
        self.assertIn('discount_amount', res.data)
        self.assertIn('grand_total', res.data)
        self.assertIn('final_total', res.data)
        self.assertEqual(Decimal(str(res.data['discount'])), Decimal('40.00'))
        self.assertEqual(Decimal(str(res.data['final_total'])), Decimal('160.00'))

    def test_auth_me_dual_structure(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        res = self.client.get('/api/v1/auth/me/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Root properties
        self.assertEqual(res.data['username'], 'alice')
        self.assertEqual(res.data['email'], 'alice@freshdash.local')
        # Nested 'user' object for frontend profile service
        self.assertIn('user', res.data)
        self.assertEqual(res.data['user']['username'], 'alice')
        self.assertIn('profile', res.data['user'])

    def test_token_refresh_dual_structure(self):
        payload = {'refresh': str(self.user_refresh)}
        res = self.client.post('/api/v1/auth/token/refresh/', payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        # Check nested tokens dict
        self.assertIn('tokens', res.data)
        self.assertIn('access', res.data['tokens'])
        # Check top-level access / refresh for standard Axios interceptors
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)


# -----------------------------------------------------------------------------
# Admin Management System Automated Tests
# -----------------------------------------------------------------------------

class AdminManagementSystemAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Regular Customer
        self.customer = User.objects.create_user(
            username='charlie',
            password='CustomerPassword123!',
            email='charlie@freshdash.local',
            first_name='Charlie',
            last_name='Customer'
        )
        self.customer_refresh = RefreshToken.for_user(self.customer)
        self.customer_access = str(self.customer_refresh.access_token)

        # Admin User (Superuser + role admin)
        self.admin = User.objects.create_superuser(
            username='admin_boss',
            password='AdminPassword123!',
            email='admin@freshdash.local',
            first_name='Admin',
            last_name='Boss'
        )
        if hasattr(self.admin, 'profile'):
            self.admin.profile.role = 'admin'
            self.admin.profile.save()
        self.admin_refresh = RefreshToken.for_user(self.admin)
        self.admin_access = str(self.admin_refresh.access_token)

        # Manager User (Staff + role manager)
        self.manager = User.objects.create_user(
            username='manager_mary',
            password='ManagerPassword123!',
            email='mary@freshdash.local',
            first_name='Mary',
            last_name='Manager',
            is_staff=True
        )
        if hasattr(self.manager, 'profile'):
            self.manager.profile.role = 'manager'
            self.manager.profile.save()
        self.manager_refresh = RefreshToken.for_user(self.manager)
        self.manager_access = str(self.manager_refresh.access_token)

        # Categories
        self.category_veg = Category.objects.create(
            id='vegetables',
            name='Vegetables',
            photo=0,
            tint='#EEF4E8'
        )
        self.category_empty = Category.objects.create(
            id='dairy',
            name='Dairy & Eggs',
            photo=2,
            tint='#FFF9E6'
        )

        # Products
        self.product_spinach = Product.objects.create(
            id='spinach',
            name='Fresh Organic Spinach',
            weight='250 g',
            price=Decimal('25.00'),
            original=Decimal('30.00'),
            stock=50,
            photo=3,
            category=self.category_veg,
            popular=True,
            organic=True,
            description='Leafy fresh spinach'
        )
        self.product_carrot = Product.objects.create(
            id='carrot',
            name='Sweet Carrots',
            weight='500 g',
            price=Decimal('40.00'),
            original=Decimal('50.00'),
            stock=8,  # low stock <= 10
            photo=4,
            category=self.category_veg,
            popular=False,
            organic=False,
            description='Crunchy orange carrots'
        )
        self.product_mango = Product.objects.create(
            id='mango',
            name='Alphonso Mangoes',
            weight='1 kg',
            price=Decimal('200.00'),
            original=Decimal('250.00'),
            stock=0,  # out of stock
            is_available=False,
            photo=5,
            category=self.category_veg,
            popular=True,
            organic=True,
            description='Sweet Alphonso mangoes'
        )

        # Customer Address
        self.address = Address.objects.create(
            user=self.customer,
            name='Home',
            line='123 Green Avenue',
            area='Downtown, Mumbai',
            is_default=True
        )

    # 1. Admin Authentication & RBAC Tests
    def test_admin_login_success(self):
        res = self.client.post('/api/v1/admin/auth/login/', {
            'username': 'admin_boss',
            'password': 'AdminPassword123!',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        self.assertIn('tokens', res.data)
        self.assertIn('access', res.data['tokens'])
        self.assertIn('refresh', res.data['tokens'])
        self.assertEqual(res.data['user']['username'], 'admin_boss')
        self.assertEqual(res.data['user']['role'], 'admin')

    def test_manager_login_success(self):
        res = self.client.post('/api/v1/admin/auth/login/', {
            'username': 'manager_mary',
            'password': 'ManagerPassword123!',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        self.assertEqual(res.data['user']['role'], 'manager')

    def test_customer_login_to_admin_denied_with_403(self):
        res = self.client.post('/api/v1/admin/auth/login/', {
            'username': 'charlie',
            'password': 'CustomerPassword123!',
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Access denied', str(res.data))

    def test_admin_login_invalid_password(self):
        res = self.client.post('/api/v1/admin/auth/login/', {
            'username': 'admin_boss',
            'password': 'WrongPassword!',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_me_profile(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.get('/api/v1/admin/auth/me/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['user']['username'], 'admin_boss')

    def test_unauthenticated_request_rejected(self):
        res = self.client.get('/api/v1/admin/products/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_token_forbidden_on_admin_endpoint(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.customer_access}')
        res = self.client.get('/api/v1/admin/products/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # 2. Product Management Tests
    def test_admin_list_products(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.get('/api/v1/admin/products/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items = res.data.get('results', res.data) if isinstance(res.data, dict) else res.data
        self.assertGreaterEqual(len(items), 3)

    def test_admin_create_product(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        payload = {
            'id': 'bell-pepper',
            'name': 'Green Bell Pepper',
            'weight': '500 g',
            'price': '45.00',
            'original': '60.00',
            'stock': 30,
            'category': 'vegetables',
            'popular': False,
            'organic': True,
            'description': 'Crisp organic bell peppers',
        }
        res = self.client.post('/api/v1/admin/products/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['id'], 'bell-pepper')
        self.assertEqual(res.data['stock'], 30)
        self.assertTrue(Product.objects.filter(id='bell-pepper').exists())

    def test_admin_create_product_auto_slug(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        payload = {
            'name': 'Fresh Broccoli Florets',
            'weight': '250 g',
            'price': '65.00',
            'original': '80.00',
            'stock': 20,
            'category': 'vegetables',
        }
        res = self.client.post('/api/v1/admin/products/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['id'].startswith('fresh-broccoli'))

    def test_admin_update_product(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.patch('/api/v1/admin/products/spinach/', {
            'price': '22.00',
            'stock': 45,
            'description': 'Updated crisp spinach description',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.spinach = Product.objects.get(id='spinach')
        self.assertEqual(self.spinach.price, Decimal('22.00'))
        self.assertEqual(self.spinach.stock, 45)

    def test_admin_toggle_product_status(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.post('/api/v1/admin/products/spinach/toggle-status/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data['is_available'])
        # Toggle back
        res2 = self.client.post('/api/v1/admin/products/spinach/toggle-status/')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertTrue(res2.data['is_available'])

    def test_admin_adjust_product_stock(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        # Set absolute
        res = self.client.post('/api/v1/admin/products/spinach/adjust-stock/', {'stock': 100})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['product']['stock'], 100)

        # Delta adjustment (+25)
        res2 = self.client.post('/api/v1/admin/products/spinach/adjust-stock/', {'adjustment': 25})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['product']['stock'], 125)

    def test_admin_delete_product(self):
        prod = Product.objects.create(
            id='temp-product',
            name='Temporary Fruit',
            weight='1 kg',
            price=Decimal('10.00'),
            original=Decimal('15.00'),
            category=self.category_veg
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.delete(f'/api/v1/admin/products/{prod.id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(id='temp-product').exists())

    # 3. Category Management Tests
    def test_admin_list_categories(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.get('/api/v1/admin/categories/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        categories = res.data.get('results', res.data) if isinstance(res.data, dict) else res.data
        self.assertGreaterEqual(len(categories), 2)
        veg_cat = next(c for c in categories if c['id'] == 'vegetables')
        self.assertGreaterEqual(veg_cat['products_count'], 1)

    def test_admin_create_category(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        payload = {
            'name': 'Exotic Fruits',
            'tint': '#FFE4E1',
            'photo': 7,
        }
        res = self.client.post('/api/v1/admin/categories/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['id'].startswith('exotic-fruits'))

    def test_admin_safe_category_deletion(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        # Deleting category with products fails with 400
        res = self.client.delete('/api/v1/admin/categories/vegetables/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot delete category', res.data['message'])

        # Deleting empty category succeeds
        res_empty = self.client.delete('/api/v1/admin/categories/dairy/')
        self.assertEqual(res_empty.status_code, status.HTTP_200_OK)
        self.assertFalse(Category.objects.filter(id='dairy').exists())

    def test_admin_toggle_category_status(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.post('/api/v1/admin/categories/vegetables/toggle-status/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data['is_active'])

    # 4. Order Management & Stock Restoration Tests
    def test_admin_list_orders_and_detail(self):
        # Create an order
        order = Order.objects.create(
            order_number='TESTORD101',
            user=self.customer,
            status='placed',
            item_total=Decimal('50.00'),
            delivery_fee=Decimal('20.00'),
            discount_amount=Decimal('0.00'),
            grand_total=Decimal('70.00'),
            payment_method='COD',
            payment_status='pending',
            delivery_address=self.address,
            delivery_address_snapshot={'name': 'Home', 'line': '123 Green Ave', 'area': 'Downtown'}
        )
        OrderItem.objects.create(
            order=order,
            product=self.product_spinach,
            product_name=self.product_spinach.name,
            weight=self.product_spinach.weight,
            quantity=2,
            unit_price=Decimal('25.00'),
            total_price=Decimal('50.00')
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res_list = self.client.get('/api/v1/admin/orders/')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        orders = res_list.data.get('results', res_list.data) if isinstance(res_list.data, dict) else res_list.data
        self.assertGreaterEqual(len(orders), 1)

        res_detail = self.client.get(f'/api/v1/admin/orders/{order.order_number}/')
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail.data['order_number'], 'TESTORD101')
        self.assertEqual(res_detail.data['customer']['username'], 'charlie')
        self.assertEqual(len(res_detail.data['items']), 1)

    def test_admin_update_order_status_and_payment(self):
        order = Order.objects.create(
            order_number='TESTORD102',
            user=self.customer,
            status='placed',
            item_total=Decimal('100.00'),
            grand_total=Decimal('100.00'),
            payment_method='UPI',
            payment_status='pending'
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.post(f'/api/v1/admin/orders/{order.order_number}/update-status/', {
            'status': 'processing',
            'payment_status': 'paid',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, 'processing')
        self.assertEqual(order.payment_status, 'paid')

    def test_admin_order_cancellation_restores_stock(self):
        # Product initial stock = 50
        initial_stock = self.product_spinach.stock
        order = Order.objects.create(
            order_number='TESTORD103',
            user=self.customer,
            status='placed',
            item_total=Decimal('75.00'),
            grand_total=Decimal('75.00')
        )
        OrderItem.objects.create(
            order=order,
            product=self.product_spinach,
            product_name=self.product_spinach.name,
            weight=self.product_spinach.weight,
            quantity=3,
            unit_price=Decimal('25.00'),
            total_price=Decimal('75.00')
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.post(f'/api/v1/admin/orders/{order.order_number}/update-status/', {
            'status': 'cancelled'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.product_spinach.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, initial_stock + 3)

    # 5. Customer Management Tests
    def test_admin_list_customers(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.get('/api/v1/admin/customers/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        customers = res.data.get('results', res.data) if isinstance(res.data, dict) else res.data
        charlie_entry = next((c for c in customers if c['username'] == 'charlie'), None)
        self.assertIsNotNone(charlie_entry)
        self.assertIn('orders_count', charlie_entry)
        self.assertIn('total_spent', charlie_entry)

    def test_admin_customer_detail(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.get(f'/api/v1/admin/customers/{self.customer.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['username'], 'charlie')
        self.assertEqual(len(res.data['addresses']), 1)

    def test_admin_toggle_customer_status(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.post(f'/api/v1/admin/customers/{self.customer.id}/toggle-status/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)

    def test_admin_change_customer_role(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.post(f'/api/v1/admin/customers/{self.customer.id}/change-role/', {
            'role': 'manager'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.profile.role, 'manager')
        self.assertTrue(self.customer.is_staff)

    # 6. Inventory & Stock Detection Tests
    def test_inventory_list_and_filters(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        # Low stock filter
        res_low = self.client.get('/api/v1/admin/inventory/?filter=low_stock')
        self.assertEqual(res_low.status_code, status.HTTP_200_OK)
        self.assertTrue(any(p['id'] == 'carrot' for p in res_low.data['inventory']))

        # Out of stock filter
        res_out = self.client.get('/api/v1/admin/inventory/?filter=out_of_stock')
        self.assertEqual(res_out.status_code, status.HTTP_200_OK)
        self.assertTrue(any(p['id'] == 'mango' for p in res_out.data['inventory']))

    def test_inventory_batch_adjust(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        payload = {
            'adjustments': [
                {'product_id': 'spinach', 'stock': 80},
                {'product_id': 'carrot', 'stock': 25},
            ]
        }
        res = self.client.post('/api/v1/admin/inventory/batch-adjust/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['updated_count'], 2)
        self.product_spinach.refresh_from_db()
        self.product_carrot.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, 80)
        self.assertEqual(self.product_carrot.stock, 25)

    # 7. Customer Order Placement Decrements Stock Atomically
    def test_customer_order_decrements_stock(self):
        initial_stock = self.product_spinach.stock
        # Add to cart
        CartItem.objects.create(
            user=self.customer,
            product=self.product_spinach,
            quantity=2,
            large=False
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.customer_access}')
        res = self.client.post('/api/v1/orders/', {
            'delivery_address_id': self.address.id
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.product_spinach.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, initial_stock - 2)

    def test_customer_order_insufficient_stock_fails(self):
        # Product carrot has stock = 8
        CartItem.objects.create(
            user=self.customer,
            product=self.product_carrot,
            quantity=10,  # exceeds available 8
            large=False
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.customer_access}')
        res = self.client.post('/api/v1/orders/', {
            'delivery_address_id': self.address.id
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient stock', str(res.data))

    # 8. Real-Time Admin Dashboard Analytics Tests
    def test_admin_dashboard_metrics(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.get('/api/v1/admin/dashboard/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        analytics = res.data['analytics']

        # Assert key live metrics exist and match real counts
        self.assertIn('total_products', analytics)
        self.assertIn('active_products', analytics)
        self.assertIn('total_categories', analytics)
        self.assertIn('total_customers', analytics)
        self.assertIn('total_orders', analytics)
        self.assertIn('today_orders_count', analytics)
        self.assertIn('today_revenue', analytics)
        self.assertIn('total_revenue', analytics)
        self.assertIn('orders_by_status', analytics)
        self.assertIn('recent_orders', analytics)
        self.assertIn('best_selling_products', analytics)
        self.assertIn('low_stock_products', analytics)
        self.assertIn('out_of_stock_products', analytics)
        self.assertEqual(analytics['total_categories'], Category.objects.count())
        self.assertEqual(analytics['total_products'], Product.objects.count())

