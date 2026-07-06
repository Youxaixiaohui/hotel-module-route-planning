# hotel/route_navigation_service.py
"""
旅游路线导航服务
负责将算法规划出的景点顺序转换为真实可通行的路线
通过调用地图导航API获取每段路线的真实道路数据
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import requests
from django.conf import settings

from .route_data_service import ScenicSpot, haversine_distance

logger = logging.getLogger(__name__)


@dataclass
class RouteSegment:
    """路线段数据类"""
    from_spot: ScenicSpot
    to_spot: ScenicSpot
    distance: float  # 距离 (公里)
    duration: int  # 预计时间 (分钟)
    polyline: List[Tuple[float, float]]  # 路线坐标点


class RouteNavigationService:
    """
    路线导航服务
    负责将景点顺序转换为真实可通行的路线
    """
    
    def __init__(self):
        self.baidu_ak = getattr(settings, 'BAIDU_MAP_AK', '')
        self.amap_ak = getattr(settings, 'AMAP_AK', '')
        self.current_map_type = 'baidu'  # 默认使用百度地图
        
    def split_route_into_segments(self, spots: List[ScenicSpot]) -> List[RouteSegment]:
        """
        将景点顺序拆分为多个路段
        
        :param spots: 景点列表 [A, B, C, D]
        :return: 路段列表 [(A→B), (B→C), (C→D)]
        """
        if len(spots) < 2:
            return []
        
        segments = []
        for i in range(len(spots) - 1):
            from_spot = spots[i]
            to_spot = spots[i + 1]
            
            # 计算预估距离和时间（用于显示）
            distance = self._calculate_distance(from_spot, to_spot)
            duration = self._calculate_travel_time(distance)
            
            segments.append(RouteSegment(
                from_spot=from_spot,
                to_spot=to_spot,
                distance=distance,
                duration=duration,
                polyline=[]
            ))
        
        return segments
    
    def get_real_route_data(self, segments: List[RouteSegment], map_type: str = 'baidu') -> List[RouteSegment]:
        """
        获取每段路线的真实道路数据
        
        :param segments: 路段列表
        :param map_type: 地图类型 ('baidu' 或 'amap')
        :return: 包含真实路线数据的路段列表
        """
        if not segments:
            return []
        
        self.current_map_type = map_type
        
        # 并行获取所有路段的路线数据
        real_segments = []
        for segment in segments:
            try:
                real_segment = self._get_single_segment_route(segment, map_type)
            except Exception:
                logger.exception("获取路段路线失败")
                real_segment = None

            # 空结果与异常都使用原始估算，保证输出和输入一一对应。
            real_segments.append(real_segment or segment)
        
        return real_segments
    
    def _get_single_segment_route(self, segment, map_type: str) -> Optional[RouteSegment]:
        """
        获取单个路段的真实路线数据
        
        :param segment: 路段（可以是RouteSegment对象或字典）
        :param map_type: 地图类型
        :return: 包含真实路线数据的路段
        """
        # 处理不同类型的segment对象
        if hasattr(segment, 'from_spot'):
            from_spot = segment.from_spot
            to_spot = segment.to_spot
        elif isinstance(segment, dict):
            from_spot = segment['from_spot']
            to_spot = segment['to_spot']
        else:
            raise ValueError(f"不支持的segment类型: {type(segment)}")
        
        if map_type == 'baidu':
            return self._get_baidu_route(from_spot, to_spot)
        elif map_type == 'amap':
            return self._get_amap_route(from_spot, to_spot)
        else:
            raise ValueError(f"不支持的地图类型: {map_type}")
    
    def _get_baidu_route(self, from_spot: ScenicSpot, to_spot: ScenicSpot) -> Optional[RouteSegment]:
        """
        获取百度地图路线数据
        
        :param from_spot: 起点景点
        :param to_spot: 终点景点
        :return: 路段数据
        """
        if not self.baidu_ak:
            logger.warning("未配置百度地图AK")
            return None
        
        url = "https://api.map.baidu.com/direction/v2/driving"
        params = {
            "origin": f"{from_spot.latitude},{from_spot.longitude}",
            "destination": f"{to_spot.latitude},{to_spot.longitude}",
            "ak": self.baidu_ak,
            "output": "json",
            "coord_type": "bd09ll",  # 使用百度坐标系
            "ret_coordtype": "bd09ll",
            "tactics": 11,  # 避免拥堵
            "region": "全国"  # 指定地区
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            # 添加详细的调试信息
            logger.info(f"百度地图API响应状态: {data.get('status')}")
            logger.info(f"百度地图API响应消息: {data.get('message', '无消息')}")
            
            if data.get('status') == 0:
                route = data['result']['routes'][0]
                distance = route['distance'] / 1000  # 转换为公里
                duration = route['duration'] / 60  # 转换为分钟
                
                # 提取路线坐标点
                polyline = []
                for step in route['steps']:
                    for point in step['path'].split(';'):
                        if point:
                            lng, lat = map(float, point.split(','))
                            polyline.append((lng, lat))
                
                logger.info(f"成功获取百度地图路线: 距离{distance}公里, 用时{duration}分钟, 坐标点{len(polyline)}个")
                
                return RouteSegment(
                    from_spot=from_spot,
                    to_spot=to_spot,
                    distance=distance,
                    duration=int(duration),
                    polyline=polyline
                )
            else:
                return None
                
        except Exception as e:
            return None
    
    def _get_amap_route(self, from_spot: ScenicSpot, to_spot: ScenicSpot) -> Optional[RouteSegment]:
        """
        获取高德地图路线数据
        
        :param from_spot: 起点景点
        :param to_spot: 终点景点
        :return: 路段数据
        """
        if not self.amap_ak:
            logger.warning("未配置高德地图AK")
            return None
        
        url = "https://restapi.amap.com/v3/direction/driving"
        params = {
            "origin": f"{from_spot.longitude},{from_spot.latitude}",
            "destination": f"{to_spot.longitude},{to_spot.latitude}",
            "key": self.amap_ak,
            "output": "json",
            "strategy": 10,  # 10: 躲避拥堵
            "extensions": "all"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            # 添加详细的调试信息
            logger.info(f"高德地图API响应状态: {data.get('status')}")
            logger.info(f"高德地图API响应消息: {data.get('info', '无消息')}")
            
            if data.get('status') == '1':
                route = data['route']['paths'][0]
                distance = float(route['distance']) / 1000
                duration = float(route['duration']) / 60
                
                # 提取路线坐标点
                polyline = []
                for step in route['steps']:
                    for point in step['polyline'].split(';'):
                        if point:
                            lng, lat = map(float, point.split(','))
                            polyline.append((lng, lat))
                
                logger.info(f"成功获取高德地图路线: 距离{distance}公里, 用时{duration}分钟, 坐标点{len(polyline)}个")
                
                return RouteSegment(
                    from_spot=from_spot,
                    to_spot=to_spot,
                    distance=distance,
                    duration=int(duration),
                    polyline=polyline
                )
            else:
                logger.error(f"高德地图API错误: {data.get('info', '未知错误')}")
                logger.error(f"API响应详情: {data}")
                return None
                
        except Exception as e:
            logger.error(f"高德地图路线获取失败: {e}")
            logger.error(f"请求参数: {params}")
            return None
    
    def _calculate_distance(self, from_spot: ScenicSpot, to_spot: ScenicSpot) -> float:
        """计算两点之间的距离（公里）"""
        return haversine_distance(
            from_spot.latitude, from_spot.longitude,
            to_spot.latitude, to_spot.longitude,
        )
    
    def _calculate_travel_time(self, distance: float) -> int:
        """根据距离计算预计行驶时间（分钟）"""
        # 假设平均速度 60km/h
        return int((distance / 60) * 60)


# 单例模式
_route_navigation_service_instance: Optional[RouteNavigationService] = None


def get_route_navigation_service() -> RouteNavigationService:
    """获取 RouteNavigationService 单例实例"""
    global _route_navigation_service_instance
    if _route_navigation_service_instance is None:
        _route_navigation_service_instance = RouteNavigationService()
    return _route_navigation_service_instance
