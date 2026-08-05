"""自包含模型包的配置加载、版本追踪与交叉校验。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .preprocessing.normalizer import UNIT_MULTIPLIERS


DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent / "config"
SUPPORTED_AMOUNT_UNITS = set(UNIT_MULTIPLIERS)
CONFIG_FILES = {
    "metric_rules": "metric_rules.json",
    "weights": "weights.json",
    "synergy_rules": "synergy_rules.json",
    "field_mapping": "field_mapping.json",
    "ai": "ai_deepseek.json",
    "scoring_params": "scoring_params.json",
    "trend_rules": "trend_rules.json",
    "data_quality": "data_quality.json",
    "hard_rules": "hard_rules.json",
    "baostock": "baostock.json",
}


class ConfigError(ValueError):
    """配置缺失、结构不符或交叉引用不一致。"""


@dataclass(frozen=True)
class AppConfig:
    metric_rules: dict[str, Any]
    weights: dict[str, Any]
    synergy_rules: dict[str, Any]
    field_mapping: dict[str, Any]
    ai: dict[str, Any]
    scoring_params: dict[str, Any]
    trend_rules: dict[str, Any]
    data_quality: dict[str, Any]
    hard_rules: dict[str, Any]
    baostock: dict[str, Any]

    @property
    def metrics(self) -> dict[str, Any]:
        return self.metric_rules["metrics"]

    @property
    def field_map(self) -> dict[str, str]:
        return self.field_mapping["fields"]

    @property
    def metric_directions(self) -> dict[str, str]:
        return {name: rule["peer_direction"] for name, rule in self.metrics.items()}

    def versions(self) -> dict[str, str]:
        return {name: getattr(self, name).get("version", "unknown") for name in CONFIG_FILES}


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_configs(config_dir: str | Path | None = None) -> AppConfig:
    base = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    payloads: dict[str, dict[str, Any]] = {}
    for name, filename in CONFIG_FILES.items():
        path = base / filename
        if not path.exists():
            raise ConfigError(f"缺少配置文件: {path}")
        payloads[name] = load_json(path)
    config = AppConfig(**payloads)
    validate(config)
    return config


def validate(config: AppConfig) -> None:
    known = set(config.metrics)
    if not known:
        raise ConfigError("未定义评分指标")
    for name, rule in config.metrics.items():
        if rule.get("peer_direction") not in {"high", "low"}:
            raise ConfigError(f"指标 {name} 的 peer_direction 必须为 high 或 low")
        anchors = rule.get("anchors", [])
        if len(anchors) < 2:
            raise ConfigError(f"指标 {name} 至少需要两个锚点")
        if any(float(right[0]) <= float(left[0]) for left, right in zip(anchors, anchors[1:])):
            raise ConfigError(f"指标 {name} 的锚点必须按数值严格递增")
    groups = config.weights.get("groups", {})
    if not groups:
        raise ConfigError("未定义风险维度")
    if abs(sum(float(group["weight"]) for group in groups.values()) - 1.0) > 1e-6:
        raise ConfigError("维度权重之和必须为1")
    for group_name, group in groups.items():
        metrics = group.get("metrics", {})
        unknown = set(metrics) - known
        if unknown:
            raise ConfigError(f"维度 {group_name} 引用了未定义指标: {sorted(unknown)}")
        if abs(sum(float(weight) for weight in metrics.values()) - 1.0) > 1e-6:
            raise ConfigError(f"维度 {group_name} 的指标权重之和必须为1")
    for rule in config.synergy_rules.get("rules", []):
        unknown = {item["metric"] for item in rule.get("conditions", [])} - known
        if unknown:
            raise ConfigError(f"共振规则 {rule.get('id')} 引用了未定义指标: {sorted(unknown)}")
    quality = config.data_quality
    if not 0 < float(quality.get("minimum_core_completeness", 0)) <= 1:
        raise ConfigError("minimum_core_completeness 必须在(0, 1]内")
    if not set(quality.get("identifier_fields", [])) <= set(quality.get("required_fields", [])):
        raise ConfigError("数据质量标识字段必须同时属于必填字段")
    valid_operators = {"lt", "lte", "gt", "gte", "eq", "contains", "in"}
    for rule in config.hard_rules.get("rules", []):
        if not rule.get("id") or not rule.get("conditions"):
            raise ConfigError("硬性规则必须包含id和至少一个条件")
        for condition in rule["conditions"]:
            if condition.get("operator") not in valid_operators or not condition.get("field"):
                raise ConfigError(f"硬性规则 {rule['id']} 包含无效条件")
    if not config.baostock.get("allowed_quarters") or config.baostock.get("data_source") != "baostock":
        raise ConfigError("Baostock配置必须包含季度范围和数据源标识")
    _validate_baostock_coverage(config)


def _validate_baostock_coverage(config: AppConfig) -> None:
    """校验Baostock不可得指标的声明，并强制显式登记因此永久失效的维度。

    模型只有一个数据源，任何指标缺口都会直接、永久地改变可评分范围。
    这里要求配置显式承认缺口，避免某个维度长期静默返回insufficient_data。
    """
    baostock = config.baostock
    if baostock.get("amount_unit") not in SUPPORTED_AMOUNT_UNITS:
        raise ConfigError(f"Baostock配置的amount_unit必须为受支持单位: {sorted(SUPPORTED_AMOUNT_UNITS)}")
    unavailable = set(baostock.get("unavailable_metrics", []))
    unknown = unavailable - set(config.metrics)
    if unknown:
        raise ConfigError(f"Baostock配置的unavailable_metrics引用了未定义指标: {sorted(unknown)}")
    declared_unscorable = set(baostock.get("unscorable_groups", []))
    unknown_groups = declared_unscorable - set(config.weights["groups"])
    if unknown_groups:
        raise ConfigError(f"Baostock配置的unscorable_groups引用了未定义维度: {sorted(unknown_groups)}")
    reachable_total = 0.0
    for name, group in config.weights["groups"].items():
        reachable = sum(weight for metric, weight in group["metrics"].items() if metric not in unavailable)
        scorable = reachable >= float(group["minimum_coverage"])
        if not scorable and name not in declared_unscorable:
            raise ConfigError(
                f"维度 {name} 在Baostock数据源下最高可得指标权重为{reachable:.2f}，"
                f"低于minimum_coverage={group['minimum_coverage']}，将永久无法评分。"
                "请在baostock.json的unscorable_groups中显式登记，或调整权重配置。"
            )
        if scorable and name in declared_unscorable:
            raise ConfigError(f"维度 {name} 实际可评分，不应登记在unscorable_groups中")
        if scorable:
            reachable_total += float(group["weight"])
    minimum_total = float(config.scoring_params["aggregation"]["minimum_total_coverage"])
    if reachable_total < minimum_total:
        raise ConfigError(
            f"Baostock数据源下可评分维度权重合计仅{reachable_total:.2f}，"
            f"低于minimum_total_coverage={minimum_total}，总分将永远无法生成。"
        )
