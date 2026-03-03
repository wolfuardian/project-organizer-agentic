"""Shim — 轉發至新路徑，保持舊 import 不壞。"""
from domain.services.git_info import *  # noqa: F401,F403
from domain.models import GitInfo  # noqa: F401
