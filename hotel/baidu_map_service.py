# hotel/baidu_map_service.py — 百度地图工具函数

from django.conf import settings

from .location_config import HOTEL_NAME, HOTEL_ADDRESS, HOTEL_BD09_LAT as HOTEL_LAT, HOTEL_BD09_LNG as HOTEL_LNG


def get_baidu_map_ak():
    """
    获取百度地图API Key（用于前端地图展示）
    优先从Django设置中读取，如果没有配置则返回空字符串
    """
    return getattr(settings, 'BAIDU_MAP_AK', '')
