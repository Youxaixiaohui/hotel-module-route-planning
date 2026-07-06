# hotel/ant_colony.py
"""
旅游路线规划 - 蚁群算法核心模块
实现基于蚁群优化 (ACO) 的旅游路线规划算法
"""

import random
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from .route_data_service import ScenicSpot, RouteDataService


@dataclass
class ACOParams:
    """蚁群算法参数"""
    ant_count: int = 30  # 蚂蚁数量（减少以提高性能）
    iterations: int = 50  # 迭代次数（减少以提高性能）
    alpha: float = 1.0  # 信息素重要程度因子
    beta: float = 2.0  # 启发函数重要程度因子
    rho: float = 0.1  # 信息素挥发因子
    q0: float = 0.9  # 状态转移概率阈值 (确定性与随机选择的平衡)
    initial_pheromone: float = 1.0  # 初始信息素值


@dataclass
class RouteResult:
    """路线规划结果"""
    path: List[int]  # 景点索引序列
    total_distance: float  # 总距离 (公里)
    total_time: int  # 总时间 (分钟，包含游览时间)
    total_score: float  # 总评分
    spots: List[ScenicSpot]  # 对应的景点对象


class AntColonyOptimizer:
    """
    蚁群算法优化器
    用于求解旅游路线规划问题 (TSP 变种)
    """
    
    def __init__(self, params: Optional[ACOParams] = None):
        self.params = params or ACOParams()
        self.data_service = RouteDataService()
        
        # 算法状态
        self.pheromone_matrix: List[List[float]] = []
        self.distance_matrix: List[List[float]] = []
        self.time_matrix: List[List[int]] = []
        self.spot_scores: List[float] = []
        self.spots: List[ScenicSpot] = []
        
        # 最优解
        self.best_path: List[int] = []
        self.best_distance: float = float('inf')
    
    def initialize(self, spots: List[ScenicSpot]):
        """
        初始化算法
        :param spots: 待规划的景点列表
        """
        self.spots = spots
        n = len(spots)
        
        # 构建距离矩阵和时间矩阵
        self.distance_matrix = self.data_service.build_distance_matrix(spots)
        self.time_matrix = self.data_service.build_time_matrix(spots)
        
        # 计算景点评分
        self.spot_scores = [
            self.data_service.calculate_spot_score(spot)
            for spot in spots
        ]
        
        # 初始化信息素矩阵
        self.pheromone_matrix = [
            [self.params.initial_pheromone] * n for _ in range(n)
        ]
        
        # 重置最优解
        self.best_path = []
        self.best_distance = float('inf')
    
    def _heuristic_value(self, i: int, j: int) -> float:
        """
        计算启发式信息 η(i,j)
        综合考虑距离和景点评分
        """
        distance = self.distance_matrix[i][j]
        if distance == 0:
            return 0
        
        # 启发值 = 景点评分 / 距离
        # 评分越高、距离越近的景点越有吸引力
        score_factor = self.spot_scores[j]
        return score_factor / (distance + 0.1)  # 加 0.1 避免除零
    
    def _select_next_spot(self, current: int, visited: set, rng: random.Random) -> int:
        """
        选择下一个访问的景点
        使用伪随机比例规则 (Pseudo-Random Proportional Rule)
        """
        n = len(self.spots)
        unvisited = [j for j in range(n) if j not in visited]
        
        if not unvisited:
            return -1
        
        # q0 概率选择最优解，否则按概率分布选择
        if rng.random() < self.params.q0:
            # 确定性选择：选择 τ^α * η^β 最大的
            best_j = -1
            best_value = -1
            
            for j in unvisited:
                pheromone = self.pheromone_matrix[current][j]
                heuristic = self._heuristic_value(current, j)
                value = (pheromone ** self.params.alpha) * (heuristic ** self.params.beta)
                
                if value > best_value:
                    best_value = value
                    best_j = j
            
            return best_j
        else:
            # 随机选择：按概率分布
            probabilities = []
            for j in unvisited:
                pheromone = self.pheromone_matrix[current][j]
                heuristic = self._heuristic_value(current, j)
                prob = (pheromone ** self.params.alpha) * (heuristic ** self.params.beta)
                probabilities.append(prob)
            
            # 归一化
            total = sum(probabilities)
            if total == 0:
                return rng.choice(unvisited)
            
            probabilities = [p / total for p in probabilities]
            
            # 轮盘赌选择
            r = rng.random()
            cumulative = 0
            for idx, prob in enumerate(probabilities):
                cumulative += prob
                if r <= cumulative:
                    return unvisited[idx]
            
            return unvisited[-1]
    
    def _build_ant_path(self, rng: random.Random) -> List[int]:
        """构建一只蚂蚁的完整路径"""
        n = len(self.spots)
        
        # 随机选择起点
        start = rng.randint(0, n - 1)
        path = [start]
        visited = {start}
        
        current = start
        while len(visited) < n:
            next_spot = self._select_next_spot(current, visited, rng)
            if next_spot == -1:
                break
            path.append(next_spot)
            visited.add(next_spot)
            current = next_spot
        
        return path
    
    def _calculate_path_distance(self, path: List[int]) -> float:
        """计算路径总距离"""
        if len(path) < 2:
            return 0
        
        total = 0
        for i in range(len(path) - 1):
            total += self.distance_matrix[path[i]][path[i + 1]]
        
        # 返回起点 (形成闭环)
        total += self.distance_matrix[path[-1]][path[0]]
        return total
    
    def _calculate_path_score(self, path: List[int]) -> float:
        """计算路径总评分"""
        return sum(self.spot_scores[i] for i in path)
    
    def _update_pheromone(self, ant_paths: List[List[int]], 
                          ant_distances: List[float]):
        """更新信息素矩阵"""
        n = len(self.spots)
        
        # 信息素挥发
        for i in range(n):
            for j in range(n):
                self.pheromone_matrix[i][j] *= (1 - self.params.rho)
        
        # 信息素增强 (使用 Ant-Cycle 模型)
        for path, distance in zip(ant_paths, ant_distances):
            if distance == 0:
                continue
            
            # 路径质量 = 1 / 距离
            quality = 1.0 / distance
            
            for i in range(len(path) - 1):
                from_spot = path[i]
                to_spot = path[i + 1]
                self.pheromone_matrix[from_spot][to_spot] += quality
            
            # 返回起点的边
            self.pheromone_matrix[path[-1]][path[0]] += quality
        
        # 限制信息素范围，避免数值溢出
        for i in range(n):
            for j in range(n):
                self.pheromone_matrix[i][j] = max(0.1, min(100, self.pheromone_matrix[i][j]))
    
    def optimize(self, spots: List[ScenicSpot],
                max_total_time: Optional[int] = None) -> RouteResult:
        """
        执行蚁群优化算法
        :param spots: 待规划的景点列表
        :param max_total_time: 最大总时间限制（分钟），None表示无限制
        :return: 最优路线结果
        """
        # 初始化
        self.initialize(spots)
        
        rng = random.Random(42)  # 固定随机种子以保证可重复性
        
        for iteration in range(self.params.iterations):
            ant_paths = []
            ant_distances = []
            
            # 每只蚂蚁构建路径
            for _ in range(self.params.ant_count):
                path = self._build_ant_path_with_time_limit(rng, max_total_time)
                if not path:
                    continue
                distance = self._calculate_path_distance(path)
                ant_paths.append(path)
                ant_distances.append(distance)
                
                # 更新全局最优
                if distance < self.best_distance:
                    self.best_distance = distance
                    self.best_path = path.copy()
            
            # 更新信息素
            self._update_pheromone(ant_paths, ant_distances)
        
        # 构建最终结果
        if not self.best_path:
            # 如果没有找到有效路径，返回一个默认路径
            default_path = list(range(len(spots)))
            return self._build_result(default_path)
        
        return self._build_result(self.best_path)
    
    def _build_ant_path_with_time_limit(self, rng: random.Random,
                                      max_total_time: Optional[int] = None) -> List[int]:
        """构建一只蚂蚁的完整路径，考虑时间限制"""
        if max_total_time is None:
            return self._build_ant_path(rng)
        
        n = len(self.spots)
        if n == 0:
            return []
        
        # 随机选择起点
        start = rng.randint(0, n - 1)
        path = [start]
        visited = {start}
        current = start
        
        # 计算当前已用时间
        current_time = self.spots[start].visit_duration
        
        while len(visited) < n:
            next_spot = self._select_next_spot(current, visited, rng)
            if next_spot == -1:
                break
            
            # 计算到下一个景点的行驶时间
            travel_time = self.time_matrix[current][next_spot]
            visit_time = self.spots[next_spot].visit_duration
            total_new_time = current_time + travel_time + visit_time
            
            # 检查是否超出时间限制
            if total_new_time > max_total_time:
                break
            
            path.append(next_spot)
            visited.add(next_spot)
            current = next_spot
            current_time = total_new_time
        
        return path
    
    def _build_result(self, path: List[int]) -> RouteResult:
        """构建路线规划结果"""
        total_distance = self._calculate_path_distance(path)
        total_score = self._calculate_path_score(path)
        
        # 计算总时间 (行驶时间 + 游览时间)
        total_travel_time = 0
        for i in range(len(path) - 1):
            total_travel_time += self.time_matrix[path[i]][path[i + 1]]
        total_travel_time += self.time_matrix[path[-1]][path[0]]  # 返回
        
        total_visit_time = sum(self.spots[i].visit_duration for i in path)
        total_time = total_travel_time + total_visit_time
        
        result_spots = [self.spots[i] for i in path]
        
        return RouteResult(
            path=path,
            total_distance=round(total_distance, 2),
            total_time=total_time,
            total_score=round(total_score, 2),
            spots=result_spots
        )
    
    def optimize_with_fixed_endpoints(self, start: ScenicSpot,
                                      middle_spots: List[ScenicSpot],
                                      end: ScenicSpot,
                                      return_to_start: bool = False) -> RouteResult:
        """
        固定起点和终点的路线优化
        :param start: 起点
        :param middle_spots: 中间途经景点列表
        :param end: 终点
        :param return_to_start: 是否返回起点（形成闭环）
        :return: 最优路线结果
        """
        if not middle_spots:
            # 没有中间景点，直接返回起点->终点
            return RouteResult(
                path=[],
                total_distance=0,
                total_time=0,
                total_score=0,
                spots=[]
            )
        
        # 只对中间景点建立矩阵，但使用“起点 -> 中间点 -> 终点”作为评价目标。
        # 旧实现按中间景点闭环距离评价，可能得到对实际固定端点路线很差的顺序。
        self.initialize(middle_spots)
        
        rng = random.Random(42)
        
        for iteration in range(self.params.iterations):
            ant_paths = []
            ant_distances = []
            
            for _ in range(self.params.ant_count):
                # 构建路径（只包含中间景点）
                path = self._build_ant_path(rng)
                if not path:
                    continue
                    
                distance = self._calculate_fixed_endpoint_distance(
                    path, start, end, return_to_start
                )
                ant_paths.append(path)
                ant_distances.append(distance)
                
                if distance < self.best_distance:
                    self.best_distance = distance
                    self.best_path = path.copy()
            
            self._update_pheromone(ant_paths, ant_distances)
        
        # 如果没有找到有效路径，使用默认顺序
        if not self.best_path:
            self.best_path = list(range(len(middle_spots)))
        
        best_distance = self._calculate_fixed_endpoint_distance(
            self.best_path, start, end, return_to_start
        )
        return RouteResult(
            path=self.best_path,
            total_distance=round(best_distance, 2),
            total_time=0,
            total_score=0,
            spots=[middle_spots[i] for i in self.best_path]
        )

    def _calculate_fixed_endpoint_distance(
        self,
        path: List[int],
        start: ScenicSpot,
        end: ScenicSpot,
        return_to_start: bool = False,
    ) -> float:
        """计算固定起终点的开放路线距离。"""
        if not path:
            distance = self.data_service.calculate_distance(start, end)
        else:
            distance = self.data_service.calculate_distance(start, self.spots[path[0]])
            for i in range(len(path) - 1):
                distance += self.distance_matrix[path[i]][path[i + 1]]
            distance += self.data_service.calculate_distance(self.spots[path[-1]], end)

        if return_to_start:
            distance += self.data_service.calculate_distance(end, start)
        return distance


def create_aco_optimizer(params: Optional[ACOParams] = None) -> AntColonyOptimizer:
    """创建蚁群优化器实例"""
    return AntColonyOptimizer(params)
