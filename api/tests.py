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

    def test_product_stock_filters_and_unavailable_separation(self):
        """
        Regression test:
        1. out_of_stock: ONLY products where stock = 0
        2. low_stock: ONLY products where 0 < stock <= 10
        3. in_stock: ONLY products where stock > 10
        4. is_available: Separate availability filter
        5. Unavailable product with 50 units (like Kale) must NOT appear in out_of_stock
        """
        kale = Product.objects.create(
            id='test-kale',
            name='Organic Kale',
            weight='250 g',
            price=Decimal('20.00'),
            original=Decimal('25.00'),
            stock=50,
            is_available=False,
            category=self.category_veg
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')

        # Case 1: out_of_stock filter (Only stock == 0)
        res_out = self.client.get('/api/v1/admin/products/?stock_status=out_of_stock')
        self.assertEqual(res_out.status_code, status.HTTP_200_OK)
        items_out = res_out.data.get('results', res_out.data)
        out_ids = [p['id'] for p in items_out]
        self.assertIn('mango', out_ids)
        self.assertNotIn('test-kale', out_ids)
        self.assertNotIn('carrot', out_ids)
        self.assertNotIn('spinach', out_ids)

        # Case 2: low_stock filter (0 < stock <= 10)
        res_low = self.client.get('/api/v1/admin/products/?stock_status=low_stock')
        self.assertEqual(res_low.status_code, status.HTTP_200_OK)
        items_low = res_low.data.get('results', res_low.data)
        low_ids = [p['id'] for p in items_low]
        self.assertIn('carrot', low_ids)
        self.assertNotIn('mango', low_ids)
        self.assertNotIn('spinach', low_ids)
        self.assertNotIn('test-kale', low_ids)

        # Case 3: in_stock filter (stock > 10)
        res_in = self.client.get('/api/v1/admin/products/?stock_status=in_stock')
        self.assertEqual(res_in.status_code, status.HTTP_200_OK)
        items_in = res_in.data.get('results', res_in.data)
        in_ids = [p['id'] for p in items_in]
        self.assertIn('spinach', in_ids)
        self.assertIn('test-kale', in_ids)
        self.assertNotIn('mango', in_ids)
        self.assertNotIn('carrot', in_ids)

        # Case 4: Separate availability filter combined with in_stock
        res_in_hidden = self.client.get('/api/v1/admin/products/?stock_status=in_stock&is_available=false')
        self.assertEqual(res_in_hidden.status_code, status.HTTP_200_OK)
        items_in_hidden = res_in_hidden.data.get('results', res_in_hidden.data)
        in_hidden_ids = [p['id'] for p in items_in_hidden]
        self.assertIn('test-kale', in_hidden_ids)
        self.assertNotIn('spinach', in_hidden_ids)

        res_in_active = self.client.get('/api/v1/admin/products/?stock_status=in_stock&is_available=true')
        self.assertEqual(res_in_active.status_code, status.HTTP_200_OK)
        items_in_active = res_in_active.data.get('results', res_in_active.data)
        in_active_ids = [p['id'] for p in items_in_active]
        self.assertIn('spinach', in_active_ids)
        self.assertNotIn('test-kale', in_active_ids)

        # Case 5: Model property is_out_of_stock must be False for Kale
        self.assertFalse(kale.is_out_of_stock)
        self.assertFalse(kale.is_low_stock)

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

    def test_admin_category_search_and_filtering(self):
        """
        Verify:
        - Search by name & slug
        - Active / Inactive filtering
        - Combined search + status filtering
        """
        Category.objects.create(id='fruits', name='Seasonal Fruits', photo=2, tint='#FFF0E8', is_active=True)
        Category.objects.create(id='inactive-herbs', name='Rare Herbs', photo=3, tint='#F8F5DD', is_active=False)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')

        # 1. Search by name
        res_search_name = self.client.get('/api/v1/admin/categories/?search=Fruits')
        self.assertEqual(res_search_name.status_code, status.HTTP_200_OK)
        items = res_search_name.data.get('results', res_search_name.data)
        ids = [c['id'] for c in items]
        self.assertIn('fruits', ids)
        self.assertNotIn('vegetables', ids)
        self.assertNotIn('inactive-herbs', ids)

        # 2. Search by slug / id
        res_search_slug = self.client.get('/api/v1/admin/categories/?search=inactive-herbs')
        self.assertEqual(res_search_slug.status_code, status.HTTP_200_OK)
        items = res_search_slug.data.get('results', res_search_slug.data)
        ids = [c['id'] for c in items]
        self.assertEqual(ids, ['inactive-herbs'])

        # 3. Active filter (is_active=true)
        res_active = self.client.get('/api/v1/admin/categories/?is_active=true')
        self.assertEqual(res_active.status_code, status.HTTP_200_OK)
        items = res_active.data.get('results', res_active.data)
        ids = [c['id'] for c in items]
        self.assertIn('vegetables', ids)
        self.assertIn('fruits', ids)
        self.assertNotIn('inactive-herbs', ids)

        # 4. Inactive filter (is_active=false)
        res_inactive = self.client.get('/api/v1/admin/categories/?is_active=false')
        self.assertEqual(res_inactive.status_code, status.HTTP_200_OK)
        items = res_inactive.data.get('results', res_inactive.data)
        ids = [c['id'] for c in items]
        self.assertEqual(ids, ['inactive-herbs'])

        # 5. Combined search + status filter
        res_combined_match = self.client.get('/api/v1/admin/categories/?search=Herbs&is_active=false')
        self.assertEqual(res_combined_match.status_code, status.HTTP_200_OK)
        items = res_combined_match.data.get('results', res_combined_match.data)
        ids = [c['id'] for c in items]
        self.assertEqual(ids, ['inactive-herbs'])

        res_combined_nomatch = self.client.get('/api/v1/admin/categories/?search=Herbs&is_active=true')
        self.assertEqual(res_combined_nomatch.status_code, status.HTTP_200_OK)
        items = res_combined_nomatch.data.get('results', res_combined_nomatch.data)
        self.assertEqual(len(items), 0)

    def test_admin_category_image_removal_and_lifecycle(self):
        """
        Phase 2.1 Regression Tests:
        - (d) Add Category with image works
        - (b) PATCH without image or remove_image flag preserves existing image
        - (c) PATCH with new image replaces existing image
        - (a) PATCH with remove_image=true clears image
        - (e) remove_image flag does not interfere with other fields
        - PATCH with remove_image=false preserves image
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')

        def create_test_image(name='test.png'):
            buf = BytesIO()
            img = Image.new('RGB', (40, 40), color='green')
            img.save(buf, 'PNG')
            buf.seek(0)
            return SimpleUploadedFile(name, buf.read(), content_type='image/png')

        # 1. Add Category with image
        initial_image = create_test_image('initial_cat.png')
        create_payload = {
            'name': 'Bakery Goods',
            'tint': '#FFF5EE',
            'image': initial_image,
        }
        res_create = self.client.post('/api/v1/admin/categories/', create_payload, format='multipart')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(res_create.data['image'])
        cat_id = res_create.data['id']
        cat = Category.objects.get(id=cat_id)
        self.assertTrue(bool(cat.image))

        # 2. PATCH without image or remove flag -> preserves existing image
        res_preserve = self.client.patch(
            f'/api/v1/admin/categories/{cat_id}/',
            {'name': 'Artisan Bakery Goods'},
            format='multipart'
        )
        self.assertEqual(res_preserve.status_code, status.HTTP_200_OK)
        cat.refresh_from_db()
        self.assertTrue(bool(cat.image))
        self.assertIsNotNone(res_preserve.data['image'])
        self.assertEqual(res_preserve.data['name'], 'Artisan Bakery Goods')

        # 3. PATCH with new image -> replaces existing image
        replacement_image = create_test_image('replacement_cat.png')
        res_replace = self.client.patch(
            f'/api/v1/admin/categories/{cat_id}/',
            {'image': replacement_image},
            format='multipart'
        )
        self.assertEqual(res_replace.status_code, status.HTTP_200_OK)
        cat.refresh_from_db()
        self.assertTrue(bool(cat.image))
        self.assertIn('replacement_cat', cat.image.name)

        # 4. PATCH with remove_image='true' -> clears image, does not interfere with other fields
        res_remove = self.client.patch(
            f'/api/v1/admin/categories/{cat_id}/',
            {'remove_image': 'true', 'name': 'Bakery Standard', 'tint': '#E0EEEE'},
            format='multipart'
        )
        self.assertEqual(res_remove.status_code, status.HTTP_200_OK)
        cat.refresh_from_db()
        self.assertFalse(bool(cat.image))
        self.assertIsNone(res_remove.data['image'])
        self.assertEqual(res_remove.data['name'], 'Bakery Standard')
        self.assertEqual(res_remove.data['tint'], '#E0EEEE')

        # 5. PATCH with remove_image='false' preserves state
        readded_image = create_test_image('readded_cat.png')
        res_readd = self.client.patch(
            f'/api/v1/admin/categories/{cat_id}/',
            {'image': readded_image},
            format='multipart'
        )
        self.assertEqual(res_readd.status_code, status.HTTP_200_OK)
        cat.refresh_from_db()
        self.assertTrue(bool(cat.image))

        res_false_flag = self.client.patch(
            f'/api/v1/admin/categories/{cat_id}/',
            {'remove_image': 'false', 'name': 'Image Preserved Cat'},
            format='multipart'
        )
        self.assertEqual(res_false_flag.status_code, status.HTTP_200_OK)
        cat.refresh_from_db()
        self.assertTrue(bool(cat.image))
        self.assertIsNotNone(res_false_flag.data['image'])
        self.assertEqual(res_false_flag.data['name'], 'Image Preserved Cat')

        # Clean up
        if cat.image:
            cat.image.delete(save=False)
        cat.delete()

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

    def test_admin_orders_pagination(self):
        """
        Phase 3: Verify Admin Orders pagination:
        - Page 1 returns correct page_size and total_pages
        - Page 2 returns remaining items
        - Invalid page number returns HTTP 404
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        # Create 22 orders
        for i in range(22):
            Order.objects.create(
                order_number=f'PAGEORD{i:03d}',
                user=self.customer,
                status='placed',
                item_total=Decimal('50.00'),
                grand_total=Decimal('50.00'),
                payment_method='COD',
                payment_status='pending',
            )

        # Page 1
        res_p1 = self.client.get('/api/v1/admin/orders/?page=1')
        self.assertEqual(res_p1.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res_p1.data['count'], 22)
        self.assertGreaterEqual(res_p1.data['total_pages'], 2)
        self.assertEqual(res_p1.data['current_page'], 1)
        self.assertEqual(len(res_p1.data['results']), 20)

        # Page 2
        res_p2 = self.client.get('/api/v1/admin/orders/?page=2')
        self.assertEqual(res_p2.status_code, status.HTTP_200_OK)
        self.assertEqual(res_p2.data['current_page'], 2)
        self.assertGreaterEqual(len(res_p2.data['results']), 2)

        # Invalid page
        res_invalid = self.client.get('/api/v1/admin/orders/?page=9999')
        self.assertEqual(res_invalid.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_orders_search_and_filter(self):
        """
        Phase 3: Verify Admin Orders search and filtering:
        - Search by order_number
        - Search by username and email
        - Combined search + status filtering
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        special_order = Order.objects.create(
            order_number='SEARCH_SPECIAL_999',
            user=self.customer,
            status='placed',
            item_total=Decimal('90.00'),
            grand_total=Decimal('90.00'),
            payment_method='UPI',
            payment_status='pending',
        )

        # 1. Search by order number
        res_num = self.client.get('/api/v1/admin/orders/?search=SEARCH_SPECIAL')
        self.assertEqual(res_num.status_code, status.HTTP_200_OK)
        items = res_num.data.get('results', res_num.data)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['order_number'], 'SEARCH_SPECIAL_999')

        # 2. Search by customer username ('charlie')
        res_user = self.client.get('/api/v1/admin/orders/?search=charlie')
        self.assertEqual(res_user.status_code, status.HTTP_200_OK)
        items_user = res_user.data.get('results', res_user.data)
        self.assertTrue(all('charlie' in o['customer_username'] for o in items_user))

        # 3. Combined search + status filter
        res_comb = self.client.get('/api/v1/admin/orders/?search=SEARCH_SPECIAL&status=placed')
        self.assertEqual(res_comb.status_code, status.HTTP_200_OK)
        items_comb = res_comb.data.get('results', res_comb.data)
        self.assertEqual(len(items_comb), 1)

        res_comb_nomatch = self.client.get('/api/v1/admin/orders/?search=SEARCH_SPECIAL&status=delivered')
        self.assertEqual(res_comb_nomatch.status_code, status.HTTP_200_OK)
        items_nomatch = res_comb_nomatch.data.get('results', res_comb_nomatch.data)
        self.assertEqual(len(items_nomatch), 0)

    def test_admin_orders_dynamic_sorting(self):
        """
        Phase 3: Verify Admin Orders sorting:
        - Newest first (-created_at)
        - Oldest first (created_at)
        - Highest amount (-grand_total)
        - Lowest amount (grand_total)
        - Invalid ordering falls back to default
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        # Clear existing test orders to test strict sorting order
        Order.objects.all().delete()

        o1 = Order.objects.create(
            order_number='SORT_O1_LOW',
            user=self.customer,
            status='placed',
            item_total=Decimal('15.00'),
            grand_total=Decimal('15.00'),
            payment_method='COD'
        )
        o2 = Order.objects.create(
            order_number='SORT_O2_HIGH',
            user=self.customer,
            status='placed',
            item_total=Decimal('450.00'),
            grand_total=Decimal('450.00'),
            payment_method='UPI'
        )
        o3 = Order.objects.create(
            order_number='SORT_O3_MID',
            user=self.customer,
            status='placed',
            item_total=Decimal('120.00'),
            grand_total=Decimal('120.00'),
            payment_method='Card'
        )

        # 1. Amount: High to Low
        res_high = self.client.get('/api/v1/admin/orders/?ordering=-grand_total')
        self.assertEqual(res_high.status_code, status.HTTP_200_OK)
        items = res_high.data['results']
        totals = [float(x['grand_total']) for x in items]
        self.assertEqual(totals, [450.0, 120.0, 15.0])

        # 2. Amount: Low to High
        res_low = self.client.get('/api/v1/admin/orders/?ordering=grand_total')
        self.assertEqual(res_low.status_code, status.HTTP_200_OK)
        items_low = res_low.data['results']
        totals_low = [float(x['grand_total']) for x in items_low]
        self.assertEqual(totals_low, [15.0, 120.0, 450.0])

        # 3. Oldest first (created_at)
        res_oldest = self.client.get('/api/v1/admin/orders/?ordering=created_at')
        self.assertEqual(res_oldest.status_code, status.HTTP_200_OK)
        self.assertEqual(res_oldest.data['results'][0]['order_number'], 'SORT_O1_LOW')

        # 4. Newest first (-created_at)
        res_newest = self.client.get('/api/v1/admin/orders/?ordering=-created_at')
        self.assertEqual(res_newest.status_code, status.HTTP_200_OK)
        self.assertEqual(res_newest.data['results'][0]['order_number'], 'SORT_O3_MID')

        # 5. Invalid ordering parameter falls back to default newest first
        res_invalid = self.client.get('/api/v1/admin/orders/?ordering=malicious_sql_injection_attempt')
        self.assertEqual(res_invalid.status_code, status.HTTP_200_OK)
        self.assertEqual(res_invalid.data['results'][0]['order_number'], 'SORT_O3_MID')

    def test_admin_orders_status_transitions_and_inventory_safety(self):
        """
        Phase 3: Verify explicit status transition validation & inventory safety:
        - Valid transitions succeed
        - Delivered orders cannot transition to cancelled (HTTP 400)
        - Cancelled orders cannot transition to confirmed (HTTP 400)
        - Invalid status choice returns HTTP 400
        - Failed transition does not modify stock
        - Inventory is restored on valid cancellation and never restored twice
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        initial_stock = self.product_spinach.stock

        # Create order
        order = Order.objects.create(
            order_number='TRANS_TEST_01',
            user=self.customer,
            status='placed',
            item_total=Decimal('50.00'),
            grand_total=Decimal('50.00')
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

        # 1. Valid forward transitions: placed -> confirmed -> processing -> shipped -> delivered
        for st in ['confirmed', 'processing', 'shipped', 'delivered']:
            res = self.client.patch(f'/api/v1/admin/orders/{order.order_number}/', {'status': st})
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            order.refresh_from_db()
            self.assertEqual(order.status, st)

        # Spinach stock should NOT have changed during normal fulfillment
        self.product_spinach.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, initial_stock)

        # 2. Rule 1: Delivered order MUST NOT transition to cancelled
        res_cancel_delivered = self.client.patch(f'/api/v1/admin/orders/{order.order_number}/', {'status': 'cancelled'})
        self.assertEqual(res_cancel_delivered.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already been delivered', res_cancel_delivered.data['message'])

        # Stock remains untouched
        self.product_spinach.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, initial_stock)

        # 3. Rule: Invalid status choices rejected
        res_invalid_choice = self.client.patch(f'/api/v1/admin/orders/{order.order_number}/', {'status': 'nonexistent_state'})
        self.assertEqual(res_invalid_choice.status_code, status.HTTP_400_BAD_REQUEST)

        # 4. Create another placed order to test valid cancellation and inventory restoration
        order_to_cancel = Order.objects.create(
            order_number='TRANS_TEST_02',
            user=self.customer,
            status='placed',
            item_total=Decimal('25.00'),
            grand_total=Decimal('25.00')
        )
        OrderItem.objects.create(
            order=order_to_cancel,
            product=self.product_spinach,
            product_name=self.product_spinach.name,
            weight=self.product_spinach.weight,
            quantity=1,
            unit_price=Decimal('25.00'),
            total_price=Decimal('25.00')
        )

        res_cancel = self.client.patch(f'/api/v1/admin/orders/{order_to_cancel.order_number}/', {'status': 'cancelled'})
        self.assertEqual(res_cancel.status_code, status.HTTP_200_OK)
        order_to_cancel.refresh_from_db()
        self.assertEqual(order_to_cancel.status, 'cancelled')

        # Stock restored by +1
        self.product_spinach.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, initial_stock + 1)

        # 5. Rule 2: Cancelled order MUST NOT transition back to confirmed/placed
        res_reopen = self.client.patch(f'/api/v1/admin/orders/{order_to_cancel.order_number}/', {'status': 'confirmed'})
        self.assertEqual(res_reopen.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('is cancelled and cannot be reopened', res_reopen.data['message'])

        # Stock remains preserved (not deducted or restored incorrectly)
        self.product_spinach.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, initial_stock + 1)

    def test_admin_orders_payment_method_filtering(self):
        """
        Phase 3: Verify Payment Method filtering:
        - Valid payment methods return matching orders
        - Invalid payment method returns empty list
        - Combined payment method and status filter
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        Order.objects.all().delete()

        Order.objects.create(
            order_number='PM_COD_01',
            user=self.customer,
            status='placed',
            item_total=Decimal('50.00'),
            grand_total=Decimal('50.00'),
            payment_method='COD'
        )
        Order.objects.create(
            order_number='PM_UPI_01',
            user=self.customer,
            status='placed',
            item_total=Decimal('100.00'),
            grand_total=Decimal('100.00'),
            payment_method='UPI'
        )
        Order.objects.create(
            order_number='PM_CARD_01',
            user=self.customer,
            status='delivered',
            item_total=Decimal('150.00'),
            grand_total=Decimal('150.00'),
            payment_method='Card'
        )

        # 1. Filter COD
        res_cod = self.client.get('/api/v1/admin/orders/?payment_method=COD')
        self.assertEqual(res_cod.status_code, status.HTTP_200_OK)
        self.assertEqual(res_cod.data['count'], 1)
        self.assertEqual(res_cod.data['results'][0]['order_number'], 'PM_COD_01')

        # 2. Filter UPI
        res_upi = self.client.get('/api/v1/admin/orders/?payment_method=UPI')
        self.assertEqual(res_upi.status_code, status.HTTP_200_OK)
        self.assertEqual(res_upi.data['count'], 1)
        self.assertEqual(res_upi.data['results'][0]['order_number'], 'PM_UPI_01')

        # 3. Filter Invalid method -> empty results (HTTP 200)
        res_invalid_pm = self.client.get('/api/v1/admin/orders/?payment_method=crypto_bitcoin')
        self.assertEqual(res_invalid_pm.status_code, status.HTTP_200_OK)
        self.assertEqual(res_invalid_pm.data['count'], 0)
        self.assertEqual(len(res_invalid_pm.data['results']), 0)

        # 4. Combined payment_method + status
        res_comb = self.client.get('/api/v1/admin/orders/?payment_method=Card&status=delivered')
        self.assertEqual(res_comb.status_code, status.HTTP_200_OK)
        self.assertEqual(res_comb.data['count'], 1)
        self.assertEqual(res_comb.data['results'][0]['order_number'], 'PM_CARD_01')

        res_comb_nomatch = self.client.get('/api/v1/admin/orders/?payment_method=Card&status=placed')
        self.assertEqual(res_comb_nomatch.status_code, status.HTTP_200_OK)
        self.assertEqual(res_comb_nomatch.data['count'], 0)

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

    def test_admin_customers_pagination(self):
        """
        Phase 4: Customer list pagination:
        - Page 1 returns correct page_size (20) and total_pages
        - Page 2 returns remaining items
        - Invalid page number returns HTTP 404
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        # Create 22 additional customer users
        for i in range(22):
            User.objects.create_user(
                username=f'cust_page_{i:02d}',
                password='Password123!',
                email=f'cust_page_{i:02d}@freshdash.local'
            )

        # Page 1
        res_p1 = self.client.get('/api/v1/admin/customers/?page=1')
        self.assertEqual(res_p1.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res_p1.data['count'], 25)
        self.assertGreaterEqual(res_p1.data['total_pages'], 2)
        self.assertEqual(res_p1.data['current_page'], 1)
        self.assertEqual(len(res_p1.data['results']), 20)

        # Page 2
        res_p2 = self.client.get('/api/v1/admin/customers/?page=2')
        self.assertEqual(res_p2.status_code, status.HTTP_200_OK)
        self.assertEqual(res_p2.data['current_page'], 2)
        self.assertGreaterEqual(len(res_p2.data['results']), 5)

        # Invalid page
        res_invalid = self.client.get('/api/v1/admin/customers/?page=9999')
        self.assertEqual(res_invalid.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_customers_search(self):
        """
        Phase 4: Customer search across username, email, first_name, last_name, phone_number
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        target_user = User.objects.create_user(
            username='samuel_search_target',
            password='Password123!',
            email='samuel_unique@target.org',
            first_name='Samuel',
            last_name='Jackson'
        )
        if hasattr(target_user, 'profile'):
            target_user.profile.phone_number = '9876543210'
            target_user.profile.save()
        else:
            UserProfile.objects.create(user=target_user, phone_number='9876543210')

        # 1. Search by username
        res_uname = self.client.get('/api/v1/admin/customers/?search=samuel_search_target')
        self.assertEqual(res_uname.status_code, status.HTTP_200_OK)
        results = res_uname.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['username'], 'samuel_search_target')

        # 2. Search by email
        res_email = self.client.get('/api/v1/admin/customers/?search=samuel_unique@target.org')
        self.assertEqual(res_email.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_email.data['results']), 1)
        self.assertEqual(res_email.data['results'][0]['email'], 'samuel_unique@target.org')

        # 3. Search by first_name
        res_fname = self.client.get('/api/v1/admin/customers/?search=Samuel')
        self.assertEqual(res_fname.status_code, status.HTTP_200_OK)
        self.assertTrue(any(c['username'] == 'samuel_search_target' for c in res_fname.data['results']))

        # 4. Search by phone_number
        res_phone = self.client.get('/api/v1/admin/customers/?search=9876543210')
        self.assertEqual(res_phone.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_phone.data['results']), 1)
        self.assertEqual(res_phone.data['results'][0]['username'], 'samuel_search_target')

        # 5. Search non-existent
        res_none = self.client.get('/api/v1/admin/customers/?search=non_existent_zebra_xyz')
        self.assertEqual(res_none.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_none.data['results']), 0)

    def test_admin_customers_role_filtering(self):
        """
        Phase 4: Customer filtering by role (customer, admin, manager)
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')

        # 1. Consumer customers
        res_cust = self.client.get('/api/v1/admin/customers/?role=customer')
        self.assertEqual(res_cust.status_code, status.HTTP_200_OK)
        results_cust = res_cust.data['results']
        self.assertTrue(len(results_cust) > 0)
        self.assertTrue(all(c['role'] == 'customer' for c in results_cust))

        # 2. Admins
        res_admin = self.client.get('/api/v1/admin/customers/?role=admin')
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        results_admin = res_admin.data['results']
        self.assertTrue(len(results_admin) > 0)
        self.assertTrue(all(c['role'] == 'admin' for c in results_admin))

        # 3. Managers
        res_mgr = self.client.get('/api/v1/admin/customers/?role=manager')
        self.assertEqual(res_mgr.status_code, status.HTTP_200_OK)
        results_mgr = res_mgr.data['results']
        self.assertTrue(len(results_mgr) > 0)
        self.assertTrue(all(c['role'] == 'manager' for c in results_mgr))

    def test_admin_customers_active_filtering(self):
        """
        Phase 4: Customer filtering by is_active=true / false
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        inactive_user = User.objects.create_user(
            username='blocked_brian',
            password='Password123!',
            email='brian@blocked.local',
            is_active=False
        )

        # 1. Active filter (is_active=true)
        res_act = self.client.get('/api/v1/admin/customers/?is_active=true')
        self.assertEqual(res_act.status_code, status.HTTP_200_OK)
        self.assertTrue(all(c['is_active'] is True for c in res_act.data['results']))
        self.assertFalse(any(c['username'] == 'blocked_brian' for c in res_act.data['results']))

        # 2. Inactive filter (is_active=false)
        res_inact = self.client.get('/api/v1/admin/customers/?is_active=false')
        self.assertEqual(res_inact.status_code, status.HTTP_200_OK)
        self.assertTrue(all(c['is_active'] is False for c in res_inact.data['results']))
        self.assertTrue(any(c['username'] == 'blocked_brian' for c in res_inact.data['results']))

    def test_admin_customers_combined_search_and_filters(self):
        """
        Phase 4: Customer combined search + role + active status filtering
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        user = User.objects.create_user(
            username='combo_user_charlotte',
            password='Password123!',
            email='charlotte@combo.local',
            is_active=True
        )
        if hasattr(user, 'profile'):
            user.profile.role = 'customer'
            user.profile.save()

        # Match all three
        res_match = self.client.get('/api/v1/admin/customers/?search=combo_user&role=customer&is_active=true')
        self.assertEqual(res_match.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_match.data['results']), 1)
        self.assertEqual(res_match.data['results'][0]['username'], 'combo_user_charlotte')

        # Conflict on role -> 0 results
        res_nomatch = self.client.get('/api/v1/admin/customers/?search=combo_user&role=admin&is_active=true')
        self.assertEqual(res_nomatch.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_nomatch.data['results']), 0)

    def test_admin_customers_sorting_orders_count(self):
        """
        Phase 4: Dynamic sorting by orders_count (asc and desc)
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        u_high = User.objects.create_user(username='cust_high_orders', password='P1', email='h@orders.com')
        u_mid = User.objects.create_user(username='cust_mid_orders', password='P1', email='m@orders.com')
        u_zero = User.objects.create_user(username='cust_zero_orders', password='P1', email='z@orders.com')

        # High orders = 3
        for i in range(3):
            Order.objects.create(
                order_number=f'HIGH_ORD_{i}',
                user=u_high,
                status='placed',
                item_total=Decimal('10.00'),
                grand_total=Decimal('10.00')
            )
        # Mid orders = 1
        Order.objects.create(
            order_number='MID_ORD_1',
            user=u_mid,
            status='placed',
            item_total=Decimal('10.00'),
            grand_total=Decimal('10.00')
        )

        # 1. Descending: orders_count high to low
        res_desc = self.client.get('/api/v1/admin/customers/?search=cust_&ordering=-orders_count')
        self.assertEqual(res_desc.status_code, status.HTTP_200_OK)
        counts_desc = [c['orders_count'] for c in res_desc.data['results'] if c['username'] in ['cust_high_orders', 'cust_mid_orders', 'cust_zero_orders']]
        self.assertEqual(counts_desc, [3, 1, 0])

        # 2. Ascending: orders_count low to high
        res_asc = self.client.get('/api/v1/admin/customers/?search=cust_&ordering=orders_count')
        self.assertEqual(res_asc.status_code, status.HTTP_200_OK)
        counts_asc = [c['orders_count'] for c in res_asc.data['results'] if c['username'] in ['cust_high_orders', 'cust_mid_orders', 'cust_zero_orders']]
        self.assertEqual(counts_asc, [0, 1, 3])

    def test_admin_customers_sorting_total_spent(self):
        """
        Phase 4: Dynamic sorting by total_spent (asc and desc)
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        u_rich = User.objects.create_user(username='cust_rich_spender', password='P1', email='r@spent.com')
        u_mod = User.objects.create_user(username='cust_mod_spender', password='P1', email='m@spent.com')
        u_none = User.objects.create_user(username='cust_none_spender', password='P1', email='n@spent.com')

        Order.objects.create(
            order_number='RICH_ORD_1',
            user=u_rich,
            status='delivered',
            item_total=Decimal('500.00'),
            grand_total=Decimal('500.00')
        )
        Order.objects.create(
            order_number='MOD_ORD_1',
            user=u_mod,
            status='confirmed',
            item_total=Decimal('150.00'),
            grand_total=Decimal('150.00')
        )

        # 1. Descending total_spent
        res_desc = self.client.get('/api/v1/admin/customers/?search=cust_&ordering=-total_spent')
        self.assertEqual(res_desc.status_code, status.HTTP_200_OK)
        spents_desc = [float(c['total_spent']) for c in res_desc.data['results'] if c['username'] in ['cust_rich_spender', 'cust_mod_spender', 'cust_none_spender']]
        self.assertEqual(spents_desc, [500.0, 150.0, 0.0])

        # 2. Ascending total_spent
        res_asc = self.client.get('/api/v1/admin/customers/?search=cust_&ordering=total_spent')
        self.assertEqual(res_asc.status_code, status.HTTP_200_OK)
        spents_asc = [float(c['total_spent']) for c in res_asc.data['results'] if c['username'] in ['cust_rich_spender', 'cust_mod_spender', 'cust_none_spender']]
        self.assertEqual(spents_asc, [0.0, 150.0, 500.0])

    def test_admin_customers_zero_orders_and_business_rules_total_spent(self):
        """
        Phase 4: Verify business rules:
        - Customer without orders receives orders_count=0 and total_spent=0.00
        - Cancelled orders are excluded from total_spent but included in orders_count
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        u_mixed = User.objects.create_user(username='cust_mixed_orders', password='P1', email='mix@orders.com')

        # Placed order (50.00)
        Order.objects.create(
            order_number='MIX_ORD_VALID',
            user=u_mixed,
            status='placed',
            item_total=Decimal('50.00'),
            grand_total=Decimal('50.00')
        )
        # Cancelled order (100.00) -> should be excluded from total_spent
        Order.objects.create(
            order_number='MIX_ORD_CANCEL',
            user=u_mixed,
            status='cancelled',
            item_total=Decimal('100.00'),
            grand_total=Decimal('100.00')
        )

        res = self.client.get(f'/api/v1/admin/customers/{u_mixed.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['orders_count'], 2)  # 2 orders placed
        self.assertEqual(float(res.data['total_spent']), 50.0)  # Cancelled 100.00 strictly excluded

    def test_admin_customers_auth_and_rbac(self):
        """
        Phase 4: Authorization and RBAC:
        - Admin accesses successfully (200)
        - Consumer role receives HTTP 403 Forbidden
        - Unauthenticated request receives HTTP 401 Unauthorized
        """
        # 1. Unauthenticated -> 401
        self.client.credentials()  # Clear auth
        res_unauth = self.client.get('/api/v1/admin/customers/')
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Consumer token -> 403
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.customer_access}')
        res_forbidden = self.client.get('/api/v1/admin/customers/')
        self.assertEqual(res_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Admin token -> 200
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res_ok = self.client.get('/api/v1/admin/customers/')
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)

    def test_admin_customers_self_deactivation_protection(self):
        """
        Phase 4: Admin cannot deactivate their own administrative account
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.post(f'/api/v1/admin/customers/{self.admin.id}/toggle-status/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cannot deactivate your own', res.data['message'])
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

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

    # Phase 5: Inventory Management Regression Tests
    def test_inventory_batch_adjust_negative_stock_p0_bug_returns_400(self):
        """
        Phase 5 P0 Bug Fix: Negative stock adjustment in batch_adjust must return
        HTTP 400 Bad Request and not crash with an unhandled NameError (HTTP 500).
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        initial_stock = self.product_spinach.stock  # 50
        payload = {
            'adjustments': [
                {'product_id': 'spinach', 'adjustment': -100}  # 50 - 100 < 0
            ]
        }
        res = self.client.post('/api/v1/admin/inventory/batch-adjust/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.product_spinach.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, initial_stock)

    def test_inventory_batch_adjust_atomic_rollback(self):
        """
        Phase 5: If any product adjustment in a batch fails validation,
        all previous updates in the transaction must be rolled back atomically.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        spinach_initial = self.product_spinach.stock  # 50
        carrot_initial = self.product_carrot.stock    # 8

        payload = {
            'adjustments': [
                {'product_id': 'spinach', 'adjustment': 20},     # Valid: 50 -> 70
                {'product_id': 'carrot', 'adjustment': -50},     # Invalid: 8 - 50 = -42 < 0
            ]
        }
        res = self.client.post('/api/v1/admin/inventory/batch-adjust/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Confirm atomicity: spinach must NOT have been updated to 70
        self.product_spinach.refresh_from_db()
        self.product_carrot.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, spinach_initial)
        self.assertEqual(self.product_carrot.stock, carrot_initial)

    def test_inventory_single_stock_adjustment(self):
        """
        Phase 5: Single stock adjustment via POST /admin/inventory/adjust/
        Supports delta (+/-) and absolute units, rejecting invalid negative stock.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')

        # 1. Valid positive delta
        res = self.client.post('/api/v1/admin/inventory/adjust/', {'product_id': 'spinach', 'adjustment': 15})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.product_spinach.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, 65)

        # 2. Valid absolute stock
        res2 = self.client.post('/api/v1/admin/inventory/adjust/', {'product_id': 'carrot', 'stock': 45})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.product_carrot.refresh_from_db()
        self.assertEqual(self.product_carrot.stock, 45)

        # 3. Invalid delta dropping stock below 0
        res3 = self.client.post('/api/v1/admin/inventory/adjust/', {'product_id': 'spinach', 'adjustment': -100})
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)
        self.product_spinach.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, 65)

    def test_inventory_zero_stock_and_availability_sync(self):
        """
        Phase 5: Stock reaching 0 must automatically set is_available = False.
        Replenishing stock above 0 must automatically reactivate is_available = True.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        self.assertTrue(self.product_spinach.is_available)

        # Reduce to zero
        res = self.client.post('/api/v1/admin/inventory/adjust/', {'product_id': 'spinach', 'stock': 0})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.product_spinach.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, 0)
        self.assertFalse(self.product_spinach.is_available)

        # Replenish stock via delta
        res2 = self.client.post('/api/v1/admin/inventory/adjust/', {'product_id': 'spinach', 'adjustment': 25})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.product_spinach.refresh_from_db()
        self.assertEqual(self.product_spinach.stock, 25)
        self.assertTrue(self.product_spinach.is_available)

    def test_inventory_invalid_adjustment_payloads(self):
        """
        Phase 5: Validate missing fields, invalid types, empty batch, and non-existent products.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')

        # Missing product_id
        res1 = self.client.post('/api/v1/admin/inventory/adjust/', {'adjustment': 10})
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing both stock and adjustment
        res2 = self.client.post('/api/v1/admin/inventory/adjust/', {'product_id': 'spinach'})
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

        # Non-existent product
        res3 = self.client.post('/api/v1/admin/inventory/adjust/', {'product_id': 'non_existent_xyz', 'stock': 10})
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)

        # Negative absolute stock
        res4 = self.client.post('/api/v1/admin/inventory/adjust/', {'product_id': 'spinach', 'stock': -5})
        self.assertEqual(res4.status_code, status.HTTP_400_BAD_REQUEST)

        # Empty adjustments list
        res5 = self.client.post('/api/v1/admin/inventory/batch-adjust/', {'adjustments': []}, format='json')
        self.assertEqual(res5.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inventory_pagination_and_page_size(self):
        """
        Phase 5: Test server-side pagination with page and page_size parameters.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        # Create additional products to have 5 total
        Product.objects.create(id='banana', name='Banana', weight='1 kg', price=Decimal('40.00'), original=Decimal('45.00'), stock=30, photo=1, category=self.category_veg)
        Product.objects.create(id='apple', name='Royal Apple', weight='1 kg', price=Decimal('150.00'), original=Decimal('180.00'), stock=20, photo=2, category=self.category_veg)

        # Page 1 with page_size=2
        res1 = self.client.get('/api/v1/admin/inventory/?page=1&page_size=2')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data['count'], 5)
        self.assertEqual(res1.data['total_items'], 5)
        self.assertEqual(res1.data['total_pages'], 3)
        self.assertEqual(res1.data['current_page'], 1)
        self.assertEqual(res1.data['page_size'], 2)
        self.assertEqual(len(res1.data['inventory']), 2)

        # Page 2 with page_size=2
        res2 = self.client.get('/api/v1/admin/inventory/?page=2&page_size=2')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['current_page'], 2)
        self.assertEqual(len(res2.data['inventory']), 2)

        # Verify page 1 and page 2 items are distinct
        page1_ids = {p['id'] for p in res1.data['inventory']}
        page2_ids = {p['id'] for p in res2.data['inventory']}
        self.assertEqual(len(page1_ids.intersection(page2_ids)), 0)

    def test_inventory_invalid_page_numbers_safely_handled(self):
        """
        Phase 5: Negative, non-integer, and out-of-range page numbers must be handled safely
        without crashing (returns HTTP 200 with fallback page).
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')

        # Negative page
        res1 = self.client.get('/api/v1/admin/inventory/?page=-3')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data['current_page'], 1)

        # Non-integer page
        res2 = self.client.get('/api/v1/admin/inventory/?page=invalid_string')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['current_page'], 1)

        # Out of range page clamped to total_pages
        res3 = self.client.get('/api/v1/admin/inventory/?page=9999&page_size=2')
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertLessEqual(res3.data['current_page'], res3.data['total_pages'])

    def test_inventory_sorting_allowlist(self):
        """
        Phase 5: Ordering by stock, name, category (asc and desc) with deterministic tie-breaker.
        Arbitrary or unsupported ordering parameters must be safely ignored.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')

        # 1. Stock Ascending
        res_stock_asc = self.client.get('/api/v1/admin/inventory/?ordering=stock')
        self.assertEqual(res_stock_asc.status_code, status.HTTP_200_OK)
        stocks_asc = [p['stock'] for p in res_stock_asc.data['inventory']]
        self.assertEqual(stocks_asc, sorted(stocks_asc))

        # 2. Stock Descending
        res_stock_desc = self.client.get('/api/v1/admin/inventory/?ordering=-stock')
        self.assertEqual(res_stock_desc.status_code, status.HTTP_200_OK)
        stocks_desc = [p['stock'] for p in res_stock_desc.data['inventory']]
        self.assertEqual(stocks_desc, sorted(stocks_desc, reverse=True))

        # 3. Name Ascending
        res_name_asc = self.client.get('/api/v1/admin/inventory/?ordering=name')
        self.assertEqual(res_name_asc.status_code, status.HTTP_200_OK)
        names_asc = [p['name'] for p in res_name_asc.data['inventory']]
        self.assertEqual(names_asc, sorted(names_asc))

        # 4. Unsupported ordering safely falls back to default
        res_bad = self.client.get('/api/v1/admin/inventory/?ordering=unsupported_field_inject')
        self.assertEqual(res_bad.status_code, status.HTTP_200_OK)
        bad_stocks = [p['stock'] for p in res_bad.data['inventory']]
        self.assertEqual(bad_stocks, sorted(bad_stocks))

    def test_inventory_category_filtering(self):
        """
        Phase 5: Filter inventory by category ID.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        # Create product in dairy category
        Product.objects.create(
            id='milk_bottle',
            name='Farm Fresh Milk',
            weight='1 L',
            price=Decimal('60.00'),
            original=Decimal('65.00'),
            stock=15,
            photo=6,
            category=self.category_empty
        )

        # Filter by dairy
        res_dairy = self.client.get('/api/v1/admin/inventory/?category=dairy')
        self.assertEqual(res_dairy.status_code, status.HTTP_200_OK)
        self.assertEqual(res_dairy.data['count'], 1)
        self.assertEqual(res_dairy.data['inventory'][0]['id'], 'milk_bottle')

        # Filter by vegetables
        res_veg = self.client.get('/api/v1/admin/inventory/?category=vegetables')
        self.assertEqual(res_veg.status_code, status.HTTP_200_OK)
        self.assertTrue(all(p['category_id'] == 'vegetables' for p in res_veg.data['inventory']))

    def test_inventory_combined_filters(self):
        """
        Phase 5: Verify combined search, category, and status filters.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')

        # Search 'spin' + category 'vegetables' + filter 'in_stock'
        res = self.client.get('/api/v1/admin/inventory/?search=spin&category=vegetables&filter=in_stock')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(res.data['inventory'][0]['id'], 'spinach')

        # Search 'spin' + filter 'low_stock' -> 0 items (spinach has 50 stock)
        res_empty = self.client.get('/api/v1/admin/inventory/?search=spin&filter=low_stock')
        self.assertEqual(res_empty.status_code, status.HTTP_200_OK)
        self.assertEqual(res_empty.data['count'], 0)

    def test_inventory_rbac_protection(self):
        """
        Phase 5: Inventory endpoints require admin authentication (401 unauthenticated, 403 customer).
        """
        # 1. Unauthenticated list
        self.client.credentials()  # Clear credentials
        res1 = self.client.get('/api/v1/admin/inventory/')
        self.assertEqual(res1.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Customer list
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.customer_access}')
        res2 = self.client.get('/api/v1/admin/inventory/')
        self.assertEqual(res2.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Unauthenticated adjust
        self.client.credentials()
        res3 = self.client.post('/api/v1/admin/inventory/adjust/', {'product_id': 'spinach', 'stock': 20})
        self.assertEqual(res3.status_code, status.HTTP_401_UNAUTHORIZED)

        # 4. Customer adjust
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.customer_access}')
        res4 = self.client.post('/api/v1/admin/inventory/adjust/', {'product_id': 'spinach', 'stock': 20})
        self.assertEqual(res4.status_code, status.HTTP_403_FORBIDDEN)

        # 5. Customer batch-adjust
        res5 = self.client.post('/api/v1/admin/inventory/batch-adjust/', {'adjustments': [{'product_id': 'spinach', 'stock': 20}]}, format='json')
        self.assertEqual(res5.status_code, status.HTTP_403_FORBIDDEN)

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

