# hotel/route_data_service.py
"""
旅游路线规划 - 数据准备层
负责景点数据查询、距离矩阵计算、景点评分计算
"""

import math
from dataclasses import dataclass
from typing import List, Optional

from django.conf import settings

from .location_config import (
    HOTEL_ADDRESS,
    HOTEL_BD09_LAT,
    HOTEL_BD09_LNG,
    HOTEL_NAME,
)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    使用 Haversine 公式计算两点之间的球面距离（公里）
    适用于地球上任意两点的粗略距离估算
    """
    R = 6371.0  # 地球半径（公里）
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


@dataclass
class ScenicSpot:
    """景点数据类"""
    id: str
    name: str
    latitude: float
    longitude: float
    rating: float  # 基础评分 (1-5)
    description: str = ""
    visit_duration: int = 60  # 建议游览时长 (分钟)
    popularity: float = 1.0  # 热度系数
    address: str = ""  # 地址信息


class RouteDataService:
    """
    数据准备层服务类
    提供距离计算、评分计算等功能
    """
    
    def __init__(self):
        self.baidu_map_ak = getattr(settings, 'BAIDU_MAP_AK', '')
        self.amap_ak = getattr(settings, 'AMAP_AK', '')
        self._distance_cache = {}  # 距离缓存
    
    def calculate_distance(self, spot1: ScenicSpot, spot2: ScenicSpot) -> float:
        """
        计算两个景点之间的距离 (公里)
        使用 Haversine 公式计算球面距离
        :return: 距离 (公里)
        """
        cache_key = f"{spot1.id}-{spot2.id}"
        if cache_key in self._distance_cache:
            return self._distance_cache[cache_key]
        
        distance = haversine_distance(
            spot1.latitude, spot1.longitude,
            spot2.latitude, spot2.longitude,
        )
        self._distance_cache[cache_key] = distance
        self._distance_cache[f"{spot2.id}-{spot1.id}"] = distance  # 对称缓存
        return distance
    
    def calculate_travel_time(self, distance: float, speed: float = 60) -> int:
        """
        估算行驶时间 (分钟)
        :param distance: 距离 (公里)
        :param speed: 平均速度 (公里/小时)，默认 60
        :return: 时间 (分钟)
        """
        return int((distance / speed) * 60)
    
    def build_distance_matrix(self, spots: List[ScenicSpot]) -> List[List[float]]:
        """
        构建距离矩阵
        :param spots: 景点列表
        :return: n×n 距离矩阵，matrix[i][j] 表示景点 i 到景点 j 的距离
        """
        n = len(spots)
        matrix = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i][j] = self.calculate_distance(spots[i], spots[j])
        
        return matrix
    
    def build_time_matrix(self, spots: List[ScenicSpot]) -> List[List[int]]:
        """
        构建时间矩阵
        :param spots: 景点列表
        :return: n×n 时间矩阵，matrix[i][j] 表示景点 i 到景点 j 的行驶时间 (分钟)
        """
        n = len(spots)
        matrix = [[0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(n):
                if i != j:
                    distance = self.calculate_distance(spots[i], spots[j])
                    matrix[i][j] = self.calculate_travel_time(distance)
        
        return matrix
    
    def calculate_spot_score(self, spot: ScenicSpot) -> float:
        """
        计算景点综合评分
        :param spot: 景点对象
        :return: 综合评分
        """
        # 基础评分 (0-5)
        base_score = spot.rating
        
        # 热度系数
        popularity_factor = spot.popularity
        
        # 综合评分 = 基础评分 × 热度
        final_score = base_score * popularity_factor
        
        return round(final_score, 2)
    
    def get_hotel_location(self) -> ScenicSpot:
        """获取默认位置 (作为路线起点/终点)"""
        return ScenicSpot(
            id="hotel",
            name=HOTEL_NAME,
            latitude=HOTEL_BD09_LAT,
            longitude=HOTEL_BD09_LNG,
            rating=0,
            address=HOTEL_ADDRESS,
        )
    
    def clear_cache(self):
        """清除距离缓存"""
        self._distance_cache.clear()


# 单例模式
_route_data_service_instance: Optional[RouteDataService] = None


def get_route_data_service() -> RouteDataService:
    """获取 RouteDataService 单例实例"""
    global _route_data_service_instance
    if _route_data_service_instance is None:
        _route_data_service_instance = RouteDataService()
    return _route_data_service_instance
