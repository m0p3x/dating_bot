import uuid
from typing import Optional

from yookassa import Configuration, Payment as YooPayment

from bot.config import settings

# Настройка ЮKassa
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


async def create_payment(amount: int, description: str, user_tg_id: int) -> Optional[str]:
    """
    Создаёт платёж через ЮKassa и возвращает ссылку на оплату.
    """
    try:
        payment_data = {
            "amount": {
                "value": f"{amount}.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": settings.YOOKASSA_RETURN_URL
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_tg_id": str(user_tg_id),
            }
        }

        payment = YooPayment.create(payment_data)

        return payment.confirmation.confirmation_url
    except Exception as e:
        print(f"Ошибка создания платежа: {e}")
        return None

async def get_payment_status(payment_id: str) -> dict:
    """Получает статус платежа по ID"""
    try:
        payment = YooPayment.find_one(payment_id)
        return {
            "paid": payment.paid,
            "status": payment.status,
            "amount": payment.amount.value if payment.amount else None,
        }
    except Exception as e:
        print(f"Ошибка проверки платежа: {e}")
        return {"paid": False, "status": "error"}
