from django.shortcuts import render
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

import json

from bot.models import WhatsAppUser, Conversation, ConversationContext, Message
import requests
# Create your views here.

from django.http import HttpResponse

@csrf_exempt
def whatsapp_webhook(request):

    # VERIFY
    if request.method == "GET":
        if request.GET.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(request.GET.get("hub.challenge"))
        return HttpResponse("Invalid token", status=403)
    
    if request.method == "POST":
        print("message received")
        if not request.body:
            print("no body")

        data = json.loads(request.body)
        print(data)
        
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])

                for msg in messages:
                    phone = msg["from"]
                    text = msg.get("text", {}).get("body", "")

                    # 1. Create or get user
                    user, _ = WhatsAppUser.objects.get_or_create(
                        phone_number=phone
                    )

                    # 2. Create or get conversation
                    conversation, _ = Conversation.objects.get_or_create(
                        user=user,
                        is_open=True
                    )

                    # 3. Save inbound message
                    Message.objects.create(
                        conversation=conversation,
                        direction="in",
                        sender="user",
                        text=text,
                        whatsapp_message_id=msg.get("id")
                    )

                    # 4. Handle bot response
                    handle_bot(conversation, text)

        return HttpResponse("EVENT_RECEIVED", status=200)
    
def handle_bot(conversation, incoming_text):
    context, _ = ConversationContext.objects.get_or_create(
        conversation=conversation
    )

    # STOP bot if admin has taken over
    if context.last_bot_state == "ADMIN_HANDOVER":
        return

    state = context.last_bot_state or "START"

    # START state: greet user
    if state == "START":
        reply = (
            "Hi 👋 Welcome to HimaAus Education Consultancy!\n\n"
            "We help students from Nepal study abroad 🌍\n\n"
            "Which country are you interested in?"
        )
        context.last_bot_state = "ASK_COUNTRY"
        context.save()

        send_bot_message(conversation, reply)
        return

    # Continue normal flow
    continue_bot_flow(conversation, incoming_text, context)

def continue_bot_flow(conversation, text, context):
    text_lower = text.strip().lower()
    reply = None  # default: no reply

    YES_WORDS = {"yes", "y", "ok", "okay", "sure"}
    PROGRAMS = {"diploma", "bachelor", "master", "language"}
    INTAKES = {"jan", "january", "may", "sep", "september", "not sure"}
    COUNTRY = {"australia", "japan", "korea"}
    
    if context.last_bot_state == "ASK_COUNTRY":
        # Accept anything non-empty
        if text_lower in COUNTRY:
            context.interested_country = text.strip()
            reply = (
                "Great! 🎓 What level are you planning for?\n"
                "Diploma / Bachelor / Master / Language"
            )
            context.last_bot_state = "ASK_PROGRAM"
        else:
            reply = (
                "Sorry, we do not have that country"
            )
    elif context.last_bot_state == "ASK_PROGRAM":
        if text_lower in PROGRAMS:
            context.program_interest = text_lower
            reply = (
                "Nice choice 👍 Which intake are you planning for?\n"
                "Jan / May / Sep / Not sure"
            )
            context.last_bot_state = "ASK_INTAKE"
        else:
            reply = (
                "I didn’t quite get that 😊\n"
                "Please choose one: Diploma / Bachelor / Master / Language"
            )

    elif context.last_bot_state == "ASK_INTAKE":
        if text_lower in INTAKES:
            context.preferred_intake = text_lower
            reply = "Would you like to talk to our counselor for detailed guidance?"
            context.last_bot_state = "READY_FOR_ADMIN"
        else:
            reply = (
                "Just to confirm 😊\n"
                "Jan / May / Sep / Not sure"
            )

    elif context.last_bot_state == "READY_FOR_ADMIN":
        if text_lower in YES_WORDS:
            reply = "Thank you 🙏 Our counselor will message you shortly."
            context.last_bot_state = "ADMIN_HANDOVER"
        elif text_lower in {"no", "nah", "not now"}:
            reply = "No worries 😊 I’m here if you need anything else."
            context.last_bot_state = "START"
        else:
            # ❌ random text → no state change
            reply = "Please reply *YES* if you'd like to talk to a counselor."

    context.save()

    if reply:
        send_bot_message(conversation, reply)


def send_whatsapp_message(to, message):
    url = f"https://graph.facebook.com/v24.0/{settings.WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    print("Sending message to whatsapp", payload)
    r = requests.post(url, json=payload, headers=headers)
    if r.status_code != 200:
        print("WhatsApp send error:", r.text)
    return r.json()


def send_bot_message(conversation, text):
    send_whatsapp_message(conversation.user.phone_number, text)
    Message.objects.create(
        conversation=conversation,
        direction="out",
        sender="bot",
        text=text
    )



