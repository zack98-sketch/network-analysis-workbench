"""Manual / Dictionary entry (操作手册字典库).

These entries are the *background dictionary* used by analysts to correlate
config/log parsing results with authoritative documentation. They MUST NOT be
mixed into the material data flows. They function as a knowledge base:

  category (required):
    - "command_reference"   -> CLI 命令参考
    - "protocol_reference"  -> 协议/端口标准说明
    - "config_pattern"      -> 配置段落结构/约定参考 (配对配置文件解析)
    - "log_pattern"         -> 日志字段/事件结构说明 (配对日志解析)
    - "compliance_baseline" -> 等保/合规基线要求 (配合风险引擎)
    - "troubleshooting"     -> 常见排障手册
    - "vendor_notes"        -> 厂商注意事项 (HW/H3C/Cisco…)

  mapping_target (optional) -> 配对目标
    - "config_parser"  配置解析依据
    - "log_parser"     日志解析依据
    - "both"           两者皆可
    - None             仅字典学习条目

  trigger_keywords -> 字符串数组。当用户在 ConfigView / LogView 对某条
  raw_line 或某个 key 发起「查字典」请求时，按 trigger_keywords 命中
  返回相应 Manual 条目，作为「解析依据配对」结果展示。
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, JSON, Index
from sqlalchemy.sql import func
import enum

from app.database import Base


class ManualCategory(str, enum.Enum):
    COMMAND_REF = "command_reference"
    PROTOCOL_REF = "protocol_reference"
    CONFIG_PATTERN = "config_pattern"
    LOG_PATTERN = "log_pattern"
    COMPLIANCE_BASELINE = "compliance_baseline"
    TROUBLESHOOTING = "troubleshooting"
    VENDOR_NOTES = "vendor_notes"


class MappingTarget(str, enum.Enum):
    CONFIG_PARSER = "config_parser"
    LOG_PARSER = "log_parser"
    BOTH = "both"


class Manual(Base):
    __tablename__ = "manuals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(512), nullable=False, index=True)
    category = Column(Enum(ManualCategory), default=ManualCategory.CONFIG_PATTERN, index=True)
    vendor = Column(String(128), nullable=True, index=True)          # e.g. Huawei, H3C, Cisco
    device_family = Column(String(128), nullable=True, index=True)   # e.g. AR, CE, NE, S
    os_version = Column(String(128), nullable=True)                  # e.g. VRP V8R10
    mapping_target = Column(Enum(MappingTarget), nullable=True, index=True)
    trigger_keywords = Column(JSON, nullable=True)                   # List[str]
    signature_patterns = Column(JSON, nullable=True)                 # List[str] (regex-ish, 可选)
    summary = Column(String(1024), nullable=True)                    # 一两句简介
    content_md = Column(Text, nullable=False)                        # 内容，Markdown
    references = Column(JSON, nullable=True)                         # List[str] 外链/来源
    standard_ref = Column(String(255), nullable=True)                # 对应合规标准
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


Index("ix_manuals_cat_vendor", Manual.category, Manual.vendor)
Index("ix_manuals_mapping_category", Manual.mapping_target, Manual.category)
