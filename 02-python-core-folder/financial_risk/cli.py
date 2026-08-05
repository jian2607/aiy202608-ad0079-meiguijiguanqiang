"""命令行入口。"""

from __future__ import annotations

import argparse
import json

from .pipeline import FinancialRiskPipeline
from .review import ReviewWorkflow
from .sources.baostock import BaoStockError
from .quality import DataQualityError


def main() -> None:
    parser = argparse.ArgumentParser(description="模块化财务风险评估模型")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train = subparsers.add_parser("train", help="使用历史数据训练行业基准")
    train.add_argument("--input", required=True, help="历史财务CSV")
    train.add_argument("--model-dir", required=True, help="模型输出目录")
    train.add_argument("--config-dir", help="自定义配置目录")
    train.add_argument("--as-of-date", help="训练数据公告截止日期，格式YYYY-MM-DD")
    train.add_argument("--allow-errors", action="store_true", help="仅实验场景允许数据质量未达标")

    prepare = subparsers.add_parser("prepare", help="标准化、处理财报更正并检查数据质量")
    prepare.add_argument("--input", required=True, help="原始财务CSV")
    prepare.add_argument("--output", required=True, help="标准数据输出目录")
    prepare.add_argument("--config-dir", help="自定义配置目录")
    prepare.add_argument("--allow-errors", action="store_true", help="输出未达标数据，仅供修复参考")

    assess = subparsers.add_parser("assess", help="评估导入财务数据")
    assess.add_argument("--input", required=True, help="待评估财务CSV")
    assess.add_argument("--model-dir", required=True, help="行业基准模型目录")
    assess.add_argument("--output", required=True, help="评估输出目录")
    assess.add_argument("--config-dir", help="自定义配置目录")
    assess.add_argument("--enable-ai", action="store_true", help="使用deepseek-v4-flash生成受约束说明")
    assess.add_argument("--allow-errors", action="store_true", help="仅实验场景允许数据质量未达标")

    review = subparsers.add_parser("review-template", help="从评估结果生成人工复核模板")
    review.add_argument("--assessment", required=True, help="risk_assessments.json路径")
    review.add_argument("--output", required=True, help="复核CSV输出路径")

    calibrate = subparsers.add_parser("calibrate", help="汇总人工复核结果并生成校准建议")
    calibrate.add_argument("--reviews", required=True, help="已填写的复核CSV")
    calibrate.add_argument("--output", required=True, help="校准报告输出目录")

    promote = subparsers.add_parser("promote", help="更新模型版本发布状态")
    promote.add_argument("--model-dir", required=True, help="模型版本目录")
    promote.add_argument("--status", choices=["approved", "retired"], default="approved")
    promote.add_argument("--note", default="", help="审核说明")

    baostock_check = subparsers.add_parser("baostock-check", help="检查Baostock SDK与免费数据接口连通性")
    baostock_check.add_argument("--config-dir", help="自定义配置目录")

    baostock_collect = subparsers.add_parser("collect-baostock", help="采集季度财务指标并写入本地SQLite数据库")
    baostock_collect.add_argument("--start-year", type=int, required=True)
    baostock_collect.add_argument("--end-year", type=int, required=True)
    baostock_collect.add_argument("--output", required=True)
    baostock_collect.add_argument("--database", required=True)
    baostock_scope = baostock_collect.add_mutually_exclusive_group(required=True)
    baostock_scope.add_argument("--default-sample", action="store_true", help="使用内置十家公司样本池")
    baostock_scope.add_argument("--codes", help="逗号分隔Baostock代码，例如sh.600519,sz.000858")
    baostock_collect.add_argument("--config-dir", help="自定义配置目录")

    database_company = subparsers.add_parser("database-company", help="按公司、年份查询本地SQLite财务档案")
    database_company.add_argument("--database", required=True, help="SQLite本地数据库文件")
    database_company.add_argument("--ts-code", required=True, help="证券代码，例如600519.SH")

    args = parser.parse_args()
    try:
        if args.command in {"review-template", "calibrate"}:
            workflow = ReviewWorkflow()
            if args.command == "review-template":
                print(json.dumps({"status": "ok", "records": workflow.create_template(args.assessment, args.output), "output": args.output}, ensure_ascii=False))
            else:
                result = workflow.calibrate(args.reviews, args.output)
                print(json.dumps({"status": "ok", "reviewed": result["reviewed_count"], "output": args.output}, ensure_ascii=False))
            return

        pipeline = FinancialRiskPipeline(getattr(args, "config_dir", None))
        if args.command == "baostock-check":
            result = pipeline.baostock_health_check()
            print(json.dumps(result, ensure_ascii=False))
        elif args.command == "collect-baostock":
            codes = pipeline.configs.baostock["default_sample_pool"] if args.default_sample else args.codes.split(",")
            result = pipeline.collect_baostock(args.start_year, args.end_year, args.output, codes, args.database)
            print(json.dumps({"status": "ok", "output": args.output, "companies": result["company_count"], "financial_records": result["financial_record_count"], "database": result["database"]}, ensure_ascii=False))
        elif args.command == "database-company":
            reports = pipeline.database_company_reports(args.database, args.ts_code)
            print(json.dumps({"ts_code": args.ts_code, "report_count": len(reports), "reports": reports}, ensure_ascii=False))
        elif args.command == "prepare":
            result = pipeline.prepare(args.input, args.output, args.allow_errors)
            print(json.dumps({"status": "ok", "output": args.output, "records": result["manifest"]["record_count"], "quality": result["quality_summary"]}, ensure_ascii=False))
        elif args.command == "train":
            result = pipeline.train(args.input, args.model_dir, args.as_of_date, args.allow_errors)
            print(json.dumps({"status": "ok", "model_path": result["model_path"], "records": result["manifest"]["record_count"], "quality_issues": len(result["quality_issues"])}, ensure_ascii=False))
        elif args.command == "assess":
            result = pipeline.assess(args.input, args.model_dir, args.output, args.enable_ai, args.allow_errors)
            print(json.dumps({"status": "ok", "output": args.output, "records": result["manifest"]["record_count"], "quality_issues": len(result["quality_issues"])}, ensure_ascii=False))
        elif args.command == "promote":
            result = pipeline.registry.promote(args.model_dir, args.status, args.note)
            print(json.dumps({"status": "ok", "model_dir": args.model_dir, "release_status": result}, ensure_ascii=False))
    except (BaoStockError, DataQualityError, FileNotFoundError, ValueError) as error:
        print(json.dumps({"status": "error", "error_type": type(error).__name__, "message": str(error)}, ensure_ascii=False))
        raise SystemExit(2)
