from aiohttp import web
import json
from bot.database import AsyncSessionFactory
from bot.services.premium_service import PremiumService

async def yookassa_webhook(request):
    try:
        data = await request.json()
        print(f"Webhook received: {data}")
        if data.get('event') == 'payment.succeeded':
            payment = data.get('object', {})
            metadata = payment.get('metadata', {})
            user_tg_id = metadata.get('user_tg_id')
            months = int(metadata.get('months', 1))
            if user_tg_id:
                async with AsyncSessionFactory() as session:
                    premium_svc = PremiumService(session)
                    await premium_svc.grant(int(user_tg_id), days=months * 30)
                    print(f"✅ Подписка активирована для {user_tg_id} на {months} мес")
        return web.Response(status=200)
    except Exception as e:
        print(f"Webhook error: {e}")
        return web.Response(status=500)

app = web.Application()
app.router.add_post('/webhook/yookassa', yookassa_webhook)

if __name__ == '__main__':
    web.run_app(app, host='127.0.0.1', port=8080)
