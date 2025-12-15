from django.db import models
from django.utils import timezone
# Create your models here.


class WhatsAppUser(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.phone_number


class Conversation(models.Model):
    user = models.ForeignKey(
        WhatsAppUser,
        on_delete=models.CASCADE,
        related_name="conversations"
    )

    is_open = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    def close(self):
        self.is_open = False
        self.closed_at = timezone.now()
        self.save()

    def __str__(self):
        return f"Conversation with {self.user.phone_number}"

class ConversationContext(models.Model):
    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        related_name="context"
    )

    # Bot flow states:
    # START → ASK_COUNTRY → ASK_PROGRAM → ASK_INTAKE → READY_FOR_ADMIN → ADMIN_HANDOVER
    last_bot_state = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    interested_country = models.CharField(max_length=100, blank=True, null=True)
    program_interest = models.CharField(max_length=100, blank=True, null=True)
    preferred_intake = models.CharField(max_length=50, blank=True, null=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Context for {self.conversation.user.phone_number}"

class Message(models.Model):
    DIRECTION_CHOICES = (
        ("in", "Incoming"),
        ("out", "Outgoing"),
    )

    SENDER_CHOICES = (
        ("user", "User"),
        ("bot", "Bot"),
        ("admin", "Admin"),
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)

    text = models.TextField(blank=True, null=True)

    whatsapp_message_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} ({self.direction})"

