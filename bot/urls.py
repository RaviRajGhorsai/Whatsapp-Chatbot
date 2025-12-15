from bot.views import whatsapp_webhook
from django.urls import path

urlpatterns = [
    path('webhook', whatsapp_webhook)
]