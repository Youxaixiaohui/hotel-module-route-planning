# hotel/location_config.py — 位置坐标集中配置
# BD-09：百度坐标系，供百度地图前端 JS SDK 和后端 API 使用
# GCJ-02：高德/国测局坐标系，供高德地图使用
# 两组坐标独立存储，因为它们之间存在 ~300m 偏移，不可混用

HOTEL_NAME = "示例"  # 可替换为实际名称
HOTEL_ADDRESS = "青海省西宁市城中区中心广场"

# 百度坐标系 (BD-09)
HOTEL_BD09_LAT = 36.6171
HOTEL_BD09_LNG = 101.7782

# 高德坐标系 (GCJ-02)
HOTEL_GCJ02_LAT = 36.6212
HOTEL_GCJ02_LNG = 101.7787
HOTEL_GCJ02_LOCATION = "101.7787,36.6212"  # 经度,纬度（供高德 API 使用）
