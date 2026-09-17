import os

from pymongo import MongoClient


MONGODB_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGODB_URI)
db = client["ai_sales_assistant"]

leads_collection = db["leads"]
conversations_collection = db["conversations"]
messages_collection = db["messages"]
bookings_collection = db["bookings"]
bookings_collection.create_index(
    "idempotency_key",
    unique=True
)
google_tokens_collection = db["google_tokens"]

def create_lead(lead: dict):
    return leads_collection.insert_one(lead)


def get_lead(lead_id: str):
    return leads_collection.find_one({"lead_id": lead_id})


def update_lead(lead_id: str, updates: dict):
    return leads_collection.update_one(
        {"lead_id": lead_id},
        {"$set": updates},
    )


def create_conversation(conversation: dict):
    return conversations_collection.insert_one(conversation)


def get_conversation(conversation_id: str):
    return conversations_collection.find_one(
        {"conversation_id": conversation_id}
    )


def create_message(message: dict):
    return messages_collection.insert_one(message)


def get_messages(conversation_id: str):
    return list(
        messages_collection.find(
            {"conversation_id": conversation_id}
        ).sort("created_at", 1)
    )

def get_booking_by_idempotency_key(idempotency_key: str):
    return bookings_collection.find_one({
        "idempotency_key": idempotency_key

    })


def create_booking(booking: dict):
    return bookings_collection.insert_one(booking)


def get_booking_by_lead(lead_id: str):
    return bookings_collection.find_one({
        "lead_id": lead_id
    })