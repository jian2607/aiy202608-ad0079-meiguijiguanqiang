"""可替换的数据源适配器。"""

from .baostock import BaoStockCollector, BaoStockError

__all__ = ["BaoStockCollector", "BaoStockError"]
