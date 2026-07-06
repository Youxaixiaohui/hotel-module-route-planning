# hotel/amap_service.py — 高德地图工具函数

from django.conf import settings

from .location_config import HOTEL_NAME, HOTEL_ADDRESS, HOTEL_GCJ02_LOCATION as HOTEL_LOCATION


def get_amap_key():
    """
    获取高德地图API Key（用于前端地图展示）
    优先从Django设置中读取，如果没有配置则返回空字符串
    """
    return getattr(settings, 'AMAP_AK', '')
