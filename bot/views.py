from django.shortcuts import render
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from twilio.rest import Client
import json

from bot.models import WhatsAppUser, Conversation, ConversationContext, Message
import requests
# Create your views here.

from django.http import HttpResponse

@csrf_exempt
def whatsapp_webhook(request):
    """
    Twilio WhatsApp webhook
    """
    if request.method != "POST":
        return HttpResponse("Invalid request", status=405)

    print("📩 WhatsApp message received (Twilio)")

    # Twilio sends form-encoded data
    phone = request.POST.get("From")      # whatsapp:+97798xxxxxxx
    text = request.POST.get("Body", "").strip()

    if not phone:
        return HttpResponse("No sender", status=400)

    # Normalize phone (optional)
    phone = phone.replace("whatsapp:", "")

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
        text=text
    )

    # 4. Handle bot logic
    handle_bot(conversation, text)

    # Twilio requires empty 200 response
    return HttpResponse("OK", status=200)

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
    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )

    msg = client.messages.create(
        from_=settings.TWILIO_WHATSAPP_NUMBER,
        to=f"whatsapp:{to}",
        body=message
    )

    print("✅ WhatsApp sent:", msg.sid)
    return msg.sid


def send_bot_message(conversation, text):
    send_whatsapp_message(conversation.user.phone_number, text)
    Message.objects.create(
        conversation=conversation,
        direction="out",
        sender="bot",
        text=text
    )



