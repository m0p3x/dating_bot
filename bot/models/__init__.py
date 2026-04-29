from bot.models.user import User
from bot.models.tag import Tag, UserTag, Photo
from bot.models.like import Like
from bot.models.viewed_report import Viewed, Report
from bot.models.admin import Admin
from bot.models.referral import Referral  # добавь

__all__ = ["User", "Photo", "Tag", "UserTag", "Like", "Viewed", "Report", "Admin", "Referral"]