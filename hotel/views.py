# hotel/views.py — 路线规划模块视图
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
import json
import requests
import logging
import math

from .models import User
from .forms import RegisterForm, LoginForm
from .baidu_map_service import get_baidu_map_ak
from .amap_service import get_amap_key
from .route_data_service import ScenicSpot, get_route_data_service
from .route_navigation_service import get_route_navigation_service
from .particle_swarm import AdaptiveACOOptimizer

logger = logging.getLogger(__name__)

from .location_config import HOTEL_BD09_LNG as _HOTEL_LNG, HOTEL_BD09_LAT as _HOTEL_LAT

_MAX_ROUTE_SPOTS = 10
_MAX_REQUEST_BYTES = 100_000


def _api_error(message, status=400):
    return JsonResponse({'success': False, 'error': message}, status=status)


def _finite_number(value, field, minimum=None, maximum=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field}必须是数字')
    if not math.isfinite(number):
        raise ValueError(f'{field}必须是有限数字')
    if minimum is not None and number < minimum:
        raise ValueError(f'{field}不能小于{minimum}')
    if maximum is not None and number > maximum:
        raise ValueError(f'{field}不能大于{maximum}')
    return number


def _build_spot(raw, spot_id, default_name, default_duration=0):
    if not isinstance(raw, dict):
        raise ValueError(f'{default_name}数据格式错误')
    name = str(raw.get('name') or default_name).strip()[:200]
    address = str(raw.get('address') or '').strip()[:500]
    duration = _finite_number(
        raw.get('visit_duration', default_duration), '游览时长', 0, 24 * 60
    )
    return ScenicSpot(
        id=spot_id,
        name=name,
        latitude=_finite_number(raw.get('latitude'), '纬度', -90, 90),
        longitude=_finite_number(raw.get('longitude'), '经度', -180, 180),
        rating=_finite_number(raw.get('rating', 4.0), '评分', 0, 5),
        visit_duration=int(duration),
        description='',
        address=address,
    )

# ============================================================
# 认证视图
# ============================================================

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            password = form.cleaned_data['password']
            user.set_password(password)
            user.save()
            login(request, user)
            messages.success(request, '注册成功！')
            return redirect('route_planning')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('route_planning')
            else:
                form.add_error(None, '用户名或密码错误')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


# ============================================================
# 路线规划页面
# ============================================================

@login_required
def route_planning_view(request):
    """路线规划主页面"""
    context = {
        'baidu_map_ak': get_baidu_map_ak(),
        'amap_key': get_amap_key()
    }
    return render(request, 'route_planning.html', context)


# ============================================================
# 自定义路线规划 API
# ============================================================

@login_required
def plan_custom_route(request):
    """
    基于用户选择的起点、终点和景点进行路线规划
    使用 ACO+PSO 算法优化访问顺序
    """
    if request.method != 'POST':
        return _api_error('仅支持 POST 请求', 405)

    try:
        if len(request.body) > _MAX_REQUEST_BYTES:
            return _api_error('请求数据过大', 413)
        data = json.loads(request.body)
        if not isinstance(data, dict):
            return _api_error('JSON 顶层必须是对象')
        data_service = get_route_data_service()

        start_point_data = data.get('start_point')
        end_point_data = data.get('end_point')
        spots_data = data.get('spots', [])
        total_time = data.get('total_time')
        map_type = data.get('map_type', 'baidu')
        return_to_start = data.get('return_to_start', False)

        if map_type not in {'baidu', 'amap'}:
            return _api_error('map_type 仅支持 baidu 或 amap')
        if not isinstance(return_to_start, bool):
            return _api_error('return_to_start 必须是布尔值')
        if not isinstance(spots_data, list):
            return _api_error('spots 必须是数组')
        if len(spots_data) > _MAX_ROUTE_SPOTS:
            return _api_error(f'途经点最多支持 {_MAX_ROUTE_SPOTS} 个')
        max_total_minutes = None
        if total_time is not None:
            max_total_minutes = int(
                _finite_number(total_time, '总时间', 0.5, 72) * 60
            )

        if not start_point_data or not end_point_data:
            return _api_error('请选择起点和终点')

        all_points = []

        start_spot = _build_spot(start_point_data, 'start', '起点')
        start_spot.rating = 5.0
        all_points.append(start_spot)

        for i, spot_data in enumerate(spots_data):
            spot = _build_spot(spot_data, f'spot_{i}', f'景点{i + 1}', 60)
            all_points.append(spot)

        end_spot = _build_spot(end_point_data, 'end', '终点')
        end_spot.rating = 5.0
        all_points.append(end_spot)

        if len(all_points) < 2:
            return _api_error('至少需要起点和终点')

        if len(all_points) > 3:
            adaptive_optimizer = AdaptiveACOOptimizer()
            middle_spots = all_points[1:-1]
            result, aco_params = adaptive_optimizer.optimize_with_fixed_endpoints(
                start_spot,
                middle_spots,
                end_spot,
                return_to_start=return_to_start,
                use_pso=True,
            )
            ordered_spots = [all_points[0]]
            for idx in result.path:
                ordered_spots.append(middle_spots[idx])
            ordered_spots.append(all_points[-1])
        else:
            ordered_spots = all_points
            aco_params = None

        if return_to_start and len(ordered_spots) > 1:
            ordered_spots.append(start_spot)

        navigation_service = get_route_navigation_service()
        route_segments = []
        total_distance = 0
        total_duration = 0

        for i in range(len(ordered_spots) - 1):
            from_spot = ordered_spots[i]
            to_spot = ordered_spots[i + 1]

            segment = {
                'from_spot': from_spot, 'to_spot': to_spot,
                'distance': 0, 'duration': 0, 'polyline': []
            }

            real_segment = None
            try:
                real_segment = navigation_service._get_single_segment_route(segment, map_type)
                if real_segment:
                    logger.info(f"成功获取{map_type}地图真实路线: {from_spot.name} -> {to_spot.name}")
                else:
                    if map_type == 'baidu':
                        real_segment = navigation_service._get_single_segment_route(segment, 'amap')
                        if real_segment:
                            logger.info(f"成功获取高德地图真实路线: {from_spot.name} -> {to_spot.name}")
            except Exception as e:
                if map_type == 'baidu':
                    try:
                        real_segment = navigation_service._get_single_segment_route(segment, 'amap')
                    except Exception:
                        pass

            if real_segment:
                segment = {
                    'from_spot': from_spot, 'to_spot': to_spot,
                    'distance': real_segment.distance,
                    'duration': real_segment.duration,
                    'polyline': real_segment.polyline
                }
                total_distance += real_segment.distance
                total_duration += real_segment.duration
            else:
                dist = data_service.calculate_distance(from_spot, to_spot)
                drive_time = (dist / 50) * 60
                segment = {
                    'from_spot': from_spot, 'to_spot': to_spot,
                    'distance': dist, 'duration': int(drive_time), 'polyline': []
                }
                total_distance += dist
                total_duration += int(drive_time)

            route_segments.append(segment)

        arrival_times = []
        current_time = 0
        for i, spot in enumerate(ordered_spots):
            if i == 0:
                arrival_times.append({
                    'spot_name': spot.name, 'arrival_time': 0,
                    'arrival_time_formatted': '0分钟', 'is_start': True
                })
            else:
                current_time += route_segments[i-1]['duration']
                if i > 1:
                    current_time += ordered_spots[i-1].visit_duration
                arrival_times.append({
                    'spot_name': spot.name, 'arrival_time': current_time,
                    'arrival_time_formatted': f'{int(current_time // 60)}小时{int(current_time % 60)}分钟',
                    'is_start': False, 'visit_duration': spot.visit_duration
                })

        total_visit_duration = sum(spot.visit_duration for spot in ordered_spots[1:-1])
        total_elapsed = total_duration + total_visit_duration
        hours = int(total_elapsed // 60)
        minutes = int(total_elapsed % 60)
        constraint_met = max_total_minutes is None or total_elapsed <= max_total_minutes

        spots_result = [{
            'name': spot.name, 'latitude': spot.latitude, 'longitude': spot.longitude,
            'address': spot.address,
            'visit_duration': spot.visit_duration if spot.visit_duration > 0 else None,
            'arrival_time': arrival_times[i]['arrival_time'],
            'arrival_time_formatted': arrival_times[i]['arrival_time_formatted']
        } for i, spot in enumerate(ordered_spots)]

        segments_result = [{
            'from': segment['from_spot'].name,
            'to': segment['to_spot'].name,
            'distance': round(segment['distance'], 2),
            'duration': segment['duration'],
            'distance_num': round(segment['distance'], 2),
            'duration_num': segment['duration'],
            'polyline': segment['polyline']
        } for segment in route_segments]

        return JsonResponse({
            'success': True,
            'data': {
                'spots': spots_result,
                'segments': segments_result,
                # 顶层统计字段用于当前前端和旧调用方；summary 是规范化结构。
                'total_distance': round(total_distance, 2),
                'total_time': total_elapsed,
                'total_duration': total_duration,
                'total_time_formatted': f'{hours}小时{minutes}分钟',
                'spot_count': len(ordered_spots),
                'map_type': map_type,
                'constraint_met': constraint_met,
                'summary': {
                    'total_distance': round(total_distance, 2),
                    'total_duration': total_duration,
                    'total_visit_duration': total_visit_duration,
                    'total_time': total_elapsed,
                    'total_time_formatted': f'{hours}小时{minutes}分钟',
                    'spot_count': len(ordered_spots),
                    'map_type': map_type,
                    'constraint_met': constraint_met,
                    'max_total_time': max_total_minutes,
                }
            }
        })

    except json.JSONDecodeError:
        return _api_error('无效的 JSON 数据')
    except ValueError as exc:
        return _api_error(str(exc))
    except Exception:
        logger.exception('自定义路线规划失败')
        return _api_error('路线规划失败，请稍后重试', 500)


# ============================================================
# 获取真实路线 API
# ============================================================

@login_required
def get_real_route(request):
    """获取真实路线数据 API — 用于前端绘制导航路线"""
    if request.method != 'POST':
        return _api_error('仅支持 POST 请求', 405)

    try:
        if len(request.body) > _MAX_REQUEST_BYTES:
            return _api_error('请求数据过大', 413)
        data = json.loads(request.body)
        if not isinstance(data, dict):
            return _api_error('JSON 顶层必须是对象')
        from_spot_data = data.get('from')
        to_spot_data = data.get('to')
        map_type = data.get('map_type', 'baidu')

        if not from_spot_data or not to_spot_data:
            return _api_error('缺少起点或终点数据')

        if map_type not in {'baidu', 'amap'}:
            return _api_error('map_type 仅支持 baidu 或 amap')
        from_spot = _build_spot(from_spot_data, 'temp_from', '起点')
        to_spot = _build_spot(to_spot_data, 'temp_to', '终点')

        navigation_service = get_route_navigation_service()
        segment = {
            'from_spot': from_spot, 'to_spot': to_spot,
            'distance': 0, 'duration': 0, 'polyline': []
        }
        real_segment = navigation_service._get_single_segment_route(segment, map_type)

        if real_segment:
            return JsonResponse({
                'success': True,
                'data': {
                    'from': from_spot_data, 'to': to_spot_data,
                    'distance': real_segment.distance,
                    'duration': real_segment.duration,
                    'distance_num': real_segment.distance,
                    'duration_num': real_segment.duration,
                    'polyline': real_segment.polyline
                }
            })
        else:
            data_service = get_route_data_service()
            dist = data_service.calculate_distance(from_spot, to_spot)
            drive_time = (dist / 50) * 60
            return JsonResponse({
                'success': True,
                'data': {
                    'from': from_spot_data, 'to': to_spot_data,
                    'distance': f'{dist:.1f}公里',
                    'duration': f'{int(drive_time)}分钟',
                    'distance_num': dist,
                    'duration_num': int(drive_time),
                    'polyline': []
                }
            })

    except json.JSONDecodeError:
        return _api_error('无效的 JSON 数据')
    except ValueError as exc:
        return _api_error(str(exc))
    except Exception:
        logger.exception('获取真实路线失败')
        return _api_error('获取路线失败，请稍后重试', 500)


# ============================================================
# 驾车路线代理 API
# ============================================================

def _baidu_geocode(address: str, ak: str):
    """百度 Geocoding API — 文字地址转经纬度"""
    try:
        resp = requests.get(
            'https://api.map.baidu.com/geocoding/v3/',
            params={'address': address, 'output': 'json', 'ak': ak},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get('status')
        if status != 0:
            error = f'百度 API 返回错误（status={status}，msg={data.get("message", "")}）'
            return None, error, 502

        loc = data.get('result', {}).get('location')
        if not loc or 'lng' not in loc or 'lat' not in loc:
            return None, '未找到该地址对应的位置', 422
        return {'lng': loc['lng'], 'lat': loc['lat']}, None, None
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning('百度 Geocoding API 调用失败: %s', exc)
        return None, '地图服务暂时不可用', 502


def _baidu_direction_driving(origin_lng, origin_lat, dest_lng, dest_lat, tactics, ak):
    """百度 Direction API v2（驾车）"""
    try:
        resp = requests.get(
            'https://api.map.baidu.com/direction/v2/driving',
            params={
                'origin': f'{origin_lat},{origin_lng}',
                'destination': f'{dest_lat},{dest_lng}',
                'tactics': tactics, 'output': 'json', 'ak': ak,
            },
            timeout=12,
        )
        data = resp.json()
        if data.get('status') != 0:
            logger.warning('百度 Direction API 返回错误: status=%s msg=%s',
                           data.get('status'), data.get('message', ''))
            return None

        routes = data.get('result', {}).get('routes', [])
        if not routes:
            return None

        route = routes[0]
        total_distance = route.get('distance', 0)
        total_duration = route.get('duration', 0)

        points = []
        for step in route.get('steps', []):
            path = step.get('path', '')
            for pair in path.split(';'):
                pair = pair.strip()
                if not pair:
                    continue
                try:
                    lng_s, lat_s = pair.split(',')
                    points.append({'lng': float(lng_s), 'lat': float(lat_s)})
                except ValueError:
                    continue

        return {
            'points': points,
            'distance': total_distance,
            'duration': total_duration,
        }
    except Exception as e:
        logger.warning('百度 Direction API 调用失败: %s', e)
    return None


@login_required
def hotel_route_api(request):
    """
    驾车路线后端代理接口。
    GET 参数：
      start   - 出发地名称（必填）
      policy  - 路线策略（可选，默认 0）0=时间优先 1=距离最短 2=不走高速
    """
    start = request.GET.get('start', '').strip()
    policy_key = request.GET.get('policy', '0').strip()

    if not start:
        return _api_error('请提供出发地', 400)

    ak = getattr(settings, 'BAIDU_MAP_SERVER_AK', '') or getattr(settings, 'BAIDU_MAP_AK', '')
    if not ak:
        return _api_error('地图服务端 AK 未配置，请联系管理员', 500)

    try:
        tactics = int(policy_key)
    except (ValueError, TypeError):
        return _api_error('policy 必须是 0、1 或 2')
    if tactics not in {0, 1, 2}:
        return _api_error('policy 必须是 0、1 或 2')

    origin, geo_err, geo_status = _baidu_geocode(start, ak)
    if not origin:
        return _api_error(f'地理编码失败：{geo_err}', geo_status)

    route = _baidu_direction_driving(
        origin_lng=origin['lng'], origin_lat=origin['lat'],
        dest_lng=_HOTEL_LNG, dest_lat=_HOTEL_LAT,
        tactics=tactics, ak=ak,
    )
    if not route:
        return _api_error('百度地图未找到驾车路线，请检查起点地址或稍后重试', 502)

    dist_m = route['distance']
    dur_s = route['duration']
    if dist_m >= 1000:
        distance_text = f'{dist_m / 1000:.1f} 公里'
    else:
        distance_text = f'{dist_m} 米'

    dur_min = dur_s // 60
    if dur_min >= 60:
        hrs = dur_min // 60
        mins = dur_min % 60
        duration_text = f'{hrs} 小时 {mins} 分钟' if mins else f'{hrs} 小时'
    else:
        duration_text = f'{dur_min} 分钟'

    return JsonResponse({
        'success': True,
        'points': route['points'],
        'distance': dist_m,
        'duration': dur_s,
        'origin': origin,
        'distance_text': distance_text,
        'duration_text': duration_text,
    })
