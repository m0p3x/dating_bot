from aiohttp import web
import json
import asyncpg

DATABASE_URL = "postgresql://postgres:ZXsaQW25ZXsaQW252525@localhost:5432/dating_bot"

async def yookassa_webhook(request):
    try:
        data = await request.json()
        print(f"Webhook received: {data}")
        
        if data.get('event') == 'payment.succeeded':
            metadata = data.get('object', {}).get('metadata', {})
            user_tg_id = metadata.get('user_tg_id')
            
            if user_tg_id:
                # Подключаемся к БД напрямую
                conn = await asyncpg.connect(DATABASE_URL)
                await conn.execute(
                    "UPDATE users SET has_premium = true, premium_until = NOW() + INTERVAL '30 days' WHERE tg_id = $1",
                    int(user_tg_id)
                )
                await conn.close()
                print(f"✅ Premium activated for user {user_tg_id}")
                
        return web.Response(status=200)
    except Exception as e:
        print(f"Webhook error: {e}")
        return web.Response(status=500)

app = web.Application()
app.router.add_post('/webhook/yookassa', yookassa_webhook)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=8080)
