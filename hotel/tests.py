import json
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings
from django.urls import reverse

from .ant_colony import AntColonyOptimizer
from .models import User
from .route_data_service import ScenicSpot


def spot(spot_id, latitude, longitude, duration=0):
    return ScenicSpot(
        id=spot_id,
        name=spot_id,
        latitude=latitude,
        longitude=longitude,
        rating=4,
        visit_duration=duration,
    )


class RoutePlanningApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='route-tester', phone='13800000000', password='test-password'
        )
        self.client.force_login(self.user)
        self.url = reverse('plan_custom_route')
        self.payload = {
            'start_point': {'name': '起点', 'latitude': 36.61, 'longitude': 101.77},
            'end_point': {'name': '终点', 'latitude': 36.70, 'longitude': 101.80},
            'spots': [],
            'map_type': 'baidu',
        }

    @patch('hotel.route_navigation_service.RouteNavigationService._get_single_segment_route', return_value=None)
    def test_response_contract_and_fallback_route(self, _route):
        response = self.client.post(
            self.url, data=json.dumps(self.payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['success'])
        data = body['data']
        self.assertEqual(data['total_distance'], data['summary']['total_distance'])
        self.assertEqual(data['total_time'], data['summary']['total_time'])
        self.assertIn('distance_num', data['segments'][0])
        self.assertIn('duration_num', data['segments'][0])

    def test_rejects_invalid_coordinates(self):
        self.payload['start_point']['latitude'] = 91
        response = self.client.post(
            self.url, data=json.dumps(self.payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_rejects_too_many_spots(self):
        self.payload['spots'] = [
            {'latitude': 36.6, 'longitude': 101.7} for _ in range(11)
        ]
        response = self.client.post(
            self.url, data=json.dumps(self.payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('最多支持', response.json()['error'])

    @patch('hotel.route_navigation_service.RouteNavigationService._get_single_segment_route', return_value=None)
    def test_time_budget_is_reported_without_dropping_stops(self, _route):
        self.payload['spots'] = [
            {
                'name': '景点', 'latitude': 36.65, 'longitude': 101.78,
                'visit_duration': 60,
            }
        ]
        self.payload['total_time'] = 0.5
        response = self.client.post(
            self.url, data=json.dumps(self.payload), content_type='application/json'
        )
        data = response.json()['data']
        self.assertEqual(len(data['spots']), 3)
        self.assertFalse(data['constraint_met'])


class FixedEndpointOptimizerTests(TestCase):
    def test_distance_includes_fixed_endpoints_not_middle_cycle(self):
        start = spot('start', 0, 0)
        middle = [spot('a', 0, 1), spot('b', 0, 2)]
        end = spot('end', 0, 3)
        optimizer = AntColonyOptimizer()
        optimizer.initialize(middle)

        forward = optimizer._calculate_fixed_endpoint_distance([0, 1], start, end)
        reverse = optimizer._calculate_fixed_endpoint_distance([1, 0], start, end)

        self.assertLess(forward, reverse)

    def test_time_limit_uses_minutes(self):
        optimizer = AntColonyOptimizer()
        optimizer.initialize([spot('a', 0, 0, 10), spot('b', 0, 1, 10)])
        result = optimizer.optimize(optimizer.spots, max_total_time=15)
        self.assertEqual(len(result.path), 1)


class ServiceLayerTests(TestCase):
    def test_get_hotel_location_returns_valid_spot(self):
        from .route_data_service import get_route_data_service

        svc = get_route_data_service()
        hotel = svc.get_hotel_location()

        self.assertEqual(hotel.id, 'hotel')
        self.assertEqual(hotel.name, '示例')
        self.assertAlmostEqual(hotel.latitude, 36.6171, places=3)
        self.assertAlmostEqual(hotel.longitude, 101.7782, places=3)

    def test_split_route_into_segments_basic(self):
        from .route_navigation_service import get_route_navigation_service

        a = spot('a', 36.61, 101.77)
        b = spot('b', 36.65, 101.80)
        c = spot('c', 36.70, 101.85)

        svc = get_route_navigation_service()
        segments = svc.split_route_into_segments([a, b, c])

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].from_spot.id, 'a')
        self.assertEqual(segments[0].to_spot.id, 'b')
        self.assertGreater(segments[0].distance, 0)
        self.assertGreater(segments[0].duration, 0)

    def test_split_route_into_segments_empty_and_single(self):
        from .route_navigation_service import get_route_navigation_service

        svc = get_route_navigation_service()
        self.assertEqual(svc.split_route_into_segments([]), [])
        self.assertEqual(svc.split_route_into_segments([spot('x', 0, 0)]), [])

    def test_get_real_route_data_empty_input(self):
        from .route_navigation_service import get_route_navigation_service

        svc = get_route_navigation_service()
        self.assertEqual(svc.get_real_route_data([]), [])

    @patch(
        'hotel.route_navigation_service.RouteNavigationService._get_single_segment_route',
        return_value=None,
    )
    def test_get_real_route_data_keeps_fallback_segment_on_empty_result(self, _route):
        from .route_navigation_service import get_route_navigation_service

        svc = get_route_navigation_service()
        original = svc.split_route_into_segments([
            spot('a', 36.61, 101.77), spot('b', 36.65, 101.80)
        ])

        self.assertEqual(svc.get_real_route_data(original), original)


@override_settings(BAIDU_MAP_SERVER_AK='test-ak')
class HotelRouteApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='hotel-route-tester', phone='13700000000', password='test-password'
        )
        self.client.force_login(self.user)
        self.url = reverse('hotel_route_api')

    @patch('hotel.views.requests.get')
    def test_address_without_location_returns_422(self, request_get):
        response_mock = request_get.return_value
        response_mock.raise_for_status.return_value = None
        response_mock.json.return_value = {'status': 0, 'result': {}}

        response = self.client.get(self.url, {'start': '不存在的地址'})

        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.json()['success'])

    @patch('hotel.views.requests.get', side_effect=requests.RequestException('timeout'))
    def test_geocoder_transport_failure_returns_502(self, _request_get):
        response = self.client.get(self.url, {'start': '西宁站'})

        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()['success'])

    @patch('hotel.views._baidu_direction_driving', return_value=None)
    @patch(
        'hotel.views._baidu_geocode',
        return_value=({'lng': 101.7, 'lat': 36.6}, None, None),
    )
    def test_direction_failure_returns_502(self, _geocode, _direction):
        response = self.client.get(self.url, {'start': '西宁站'})

        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()['success'])
