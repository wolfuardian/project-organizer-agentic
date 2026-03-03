"""Shim — 轉發至新路徑，保持舊 import 不壞。"""
from domain.services.file_operations import *  # noqa: F401,F403
from domain.models import OperationRecord, MergeResult  # noqa: F401
