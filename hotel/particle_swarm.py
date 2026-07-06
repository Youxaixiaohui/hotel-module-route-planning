# hotel/particle_swarm.py
"""
旅游路线规划 - 粒子群优化模块
使用粒子群算法 (PSO) 优化蚁群算法的参数
优化参数：蚂蚁数量、α、β、ρ、q0
"""

import random
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from .ant_colony import AntColonyOptimizer, ACOParams, RouteResult
from .route_data_service import ScenicSpot


@dataclass
class Particle:
    """粒子类"""
    position: List[float]  # 参数位置 [ant_count, alpha, beta, rho, q0]
    velocity: List[float]  # 速度
    best_position: List[float]  # 个体最优位置
    best_fitness: float  # 个体最优适应度
    fitness: float  # 当前适应度


@dataclass
class PSOParams:
    """粒子群算法参数"""
    swarm_size: int = 15  # 粒子数量（减少以提高性能）
    max_iterations: int = 20  # 最大迭代次数（减少以提高性能）
    w: float = 0.7  # 惯性权重
    c1: float = 1.5  # 个体学习因子
    c2: float = 1.5  # 群体学习因子
    max_velocity: float = 0.3  # 最大速度


class ParticleSwarmOptimizer:
    """
    粒子群优化器
    用于优化蚁群算法的参数配置
    """
    
    # 参数搜索空间边界
    # [ant_count, alpha, beta, rho, q0]
    PARAM_BOUNDS = {
        'ant_count': (20, 100),      # 蚂蚁数量
        'alpha': (0.5, 3.0),         # 信息素因子
        'beta': (0.5, 5.0),          # 启发函数因子
        'rho': (0.05, 0.5),          # 挥发因子
        'q0': (0.5, 0.95)            # 确定性阈值
    }
    
    def __init__(self, params: Optional[PSOParams] = None):
        self.pso_params = params or PSOParams()
        self.particles: List[Particle] = []
        self.global_best_position: List[float] = []
        self.global_best_fitness: float = float('inf')
        
        # 记录优化历史
        self.history: List[float] = []
    
    def _normalize_position(self, position: List[float]) -> ACOParams:
        """将粒子位置转换为 ACO 参数"""
        ant_count = int(position[0])
        return ACOParams(
            ant_count=ant_count,
            alpha=position[1],
            beta=position[2],
            rho=position[3],
            q0=position[4]
        )
    
    def _random_position(self) -> List[float]:
        """生成随机参数位置"""
        return [
            random.uniform(self.PARAM_BOUNDS['ant_count'][0], self.PARAM_BOUNDS['ant_count'][1]),
            random.uniform(self.PARAM_BOUNDS['alpha'][0], self.PARAM_BOUNDS['alpha'][1]),
            random.uniform(self.PARAM_BOUNDS['beta'][0], self.PARAM_BOUNDS['beta'][1]),
            random.uniform(self.PARAM_BOUNDS['rho'][0], self.PARAM_BOUNDS['rho'][1]),
            random.uniform(self.PARAM_BOUNDS['q0'][0], self.PARAM_BOUNDS['q0'][1])
        ]
    
    def _random_velocity(self) -> List[float]:
        """生成随机速度"""
        bounds = [
            self.PARAM_BOUNDS['ant_count'][1] - self.PARAM_BOUNDS['ant_count'][0],
            self.PARAM_BOUNDS['alpha'][1] - self.PARAM_BOUNDS['alpha'][0],
            self.PARAM_BOUNDS['beta'][1] - self.PARAM_BOUNDS['beta'][0],
            self.PARAM_BOUNDS['rho'][1] - self.PARAM_BOUNDS['rho'][0],
            self.PARAM_BOUNDS['q0'][1] - self.PARAM_BOUNDS['q0'][0]
        ]
        return [
            random.uniform(-self.pso_params.max_velocity * b, self.pso_params.max_velocity * b)
            for b in bounds
        ]
    
    def _clamp_position(self, position: List[float]) -> List[float]:
        """将位置限制在边界内"""
        return [
            max(self.PARAM_BOUNDS['ant_count'][0], min(self.PARAM_BOUNDS['ant_count'][1], position[0])),
            max(self.PARAM_BOUNDS['alpha'][0], min(self.PARAM_BOUNDS['alpha'][1], position[1])),
            max(self.PARAM_BOUNDS['beta'][0], min(self.PARAM_BOUNDS['beta'][1], position[2])),
            max(self.PARAM_BOUNDS['rho'][0], min(self.PARAM_BOUNDS['rho'][1], position[3])),
            max(self.PARAM_BOUNDS['q0'][0], min(self.PARAM_BOUNDS['q0'][1], position[4]))
        ]
    
    def _clamp_velocity(self, velocity: List[float]) -> List[float]:
        """将速度限制在最大速度内"""
        bounds = [
            self.PARAM_BOUNDS['ant_count'][1] - self.PARAM_BOUNDS['ant_count'][0],
            self.PARAM_BOUNDS['alpha'][1] - self.PARAM_BOUNDS['alpha'][0],
            self.PARAM_BOUNDS['beta'][1] - self.PARAM_BOUNDS['beta'][0],
            self.PARAM_BOUNDS['rho'][1] - self.PARAM_BOUNDS['rho'][0],
            self.PARAM_BOUNDS['q0'][1] - self.PARAM_BOUNDS['q0'][0]
        ]
        return [
            max(-self.pso_params.max_velocity * b, min(self.pso_params.max_velocity * b, v))
            for v, b in zip(velocity, bounds)
        ]
    
    def _evaluate_fitness(self, position: List[float],
                          spots: List[ScenicSpot]) -> float:
        """
        评估粒子适应度
        使用蚁群算法求解，返回路径长度作为适应度 (越小越好)
        """
        aco_params = self._normalize_position(position)
        optimizer = AntColonyOptimizer(aco_params)
        
        # 减少迭代次数以加快评估速度
        optimizer.params.iterations = 50  # 评估时使用较少的迭代
        
        try:
            result = optimizer.optimize(spots)
            # 适应度 = 路径距离 (越小越好)
            # 同时考虑评分，距离短且评分高的路径更优
            fitness = result.total_distance / (result.total_score + 1)
            return fitness
        except Exception as e:
            # 如果出错，返回一个很大的适应度值
            return float('inf')
    
    def initialize(self):
        """初始化粒子群"""
        self.particles = []
        self.global_best_position = []
        self.global_best_fitness = float('inf')
        self.history = []
        
        for _ in range(self.pso_params.swarm_size):
            position = self._random_position()
            velocity = self._random_velocity()
            
            particle = Particle(
                position=position,
                velocity=velocity,
                best_position=position.copy(),
                best_fitness=float('inf'),
                fitness=float('inf')
            )
            self.particles.append(particle)
    
    def optimize(self, spots: List[ScenicSpot]) -> ACOParams:
        """
        执行粒子群优化
        :param spots: 景点列表
        :return: 最优的 ACO 参数
        """
        self.initialize()
        rng = random.Random(42)
        
        for iteration in range(self.pso_params.max_iterations):
            # 评估每个粒子的适应度
            for particle in self.particles:
                particle.fitness = self._evaluate_fitness(
                    particle.position, spots
                )
                
                # 更新个体最优
                if particle.fitness < particle.best_fitness:
                    particle.best_fitness = particle.fitness
                    particle.best_position = particle.position.copy()
                
                # 更新全局最优
                if particle.fitness < self.global_best_fitness:
                    self.global_best_fitness = particle.fitness
                    self.global_best_position = particle.position.copy()
            
            # 记录历史
            self.history.append(self.global_best_fitness)
            
            # 更新粒子速度和位置
            for particle in self.particles:
                for i in range(5):  # 5 个参数
                    r1 = rng.random()
                    r2 = rng.random()
                    
                    # 速度更新公式
                    cognitive = self.pso_params.c1 * r1 * (particle.best_position[i] - particle.position[i])
                    social = self.pso_params.c2 * r2 * (self.global_best_position[i] - particle.position[i])
                    
                    particle.velocity[i] = (
                        self.pso_params.w * particle.velocity[i] +
                        cognitive + social
                    )
                
                # 限制速度
                particle.velocity = self._clamp_velocity(particle.velocity)
                
                # 位置更新
                for i in range(5):
                    particle.position[i] += particle.velocity[i]
                
                # 限制位置
                particle.position = self._clamp_position(particle.position)
        
        # 返回最优参数
        return self._normalize_position(self.global_best_position)
    
    def get_optimized_params(self) -> ACOParams:
        """获取优化后的参数"""
        return self._normalize_position(self.global_best_position)


class AdaptiveACOOptimizer:
    """
    自适应蚁群优化器
    结合 PSO 参数优化和 ACO 路线规划
    """
    
    def __init__(self):
        self.pso = ParticleSwarmOptimizer()
        self.best_aco_params: Optional[ACOParams] = None
    
    def optimize_middle_spots(self, middle_spots: List[ScenicSpot],
                               use_pso: bool = True) -> Tuple[RouteResult, ACOParams]:
        """
        使用ACO+PSO优化中间景点顺序
        :param middle_spots: 中间途经景点列表
        :param use_pso: 是否使用 PSO 优化参数
        :return: (路线结果，使用的 ACO 参数)
        """
        if use_pso and len(middle_spots) >= 3:
            # 使用 PSO 优化参数
            self.best_aco_params = self.pso.optimize(middle_spots)
        else:
            # 使用默认参数
            self.best_aco_params = ACOParams()
        
        # 使用优化后的参数执行 ACO
        optimizer = AntColonyOptimizer(self.best_aco_params)
        # 恢复完整迭代次数
        optimizer.params.iterations = 100
        
        # 执行标准优化
        result = optimizer.optimize(middle_spots)
        
        return result, self.best_aco_params

    def optimize_with_fixed_endpoints(
        self,
        start: ScenicSpot,
        middle_spots: List[ScenicSpot],
        end: ScenicSpot,
        return_to_start: bool = False,
        use_pso: bool = True,
    ) -> Tuple[RouteResult, ACOParams]:
        """优化固定起终点之间的途经点顺序。"""
        if use_pso and len(middle_spots) >= 3:
            self.best_aco_params = self.pso.optimize(middle_spots)
        else:
            self.best_aco_params = ACOParams()

        optimizer = AntColonyOptimizer(self.best_aco_params)
        optimizer.params.iterations = 100
        result = optimizer.optimize_with_fixed_endpoints(
            start, middle_spots, end, return_to_start
        )
        return result, self.best_aco_params


def create_pso_optimizer(params: Optional[PSOParams] = None) -> ParticleSwarmOptimizer:
    """创建 PSO 优化器实例"""
    return ParticleSwarmOptimizer(params)


def create_adaptive_optimizer() -> AdaptiveACOOptimizer:
    """创建自适应优化器实例"""
    return AdaptiveACOOptimizer()
