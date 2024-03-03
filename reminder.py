import requests
import pymongo
import datetime
import credential_manager as cm


def send_reminder(phone_number):
    header = {
        "Authorization": f"Bearer {cm.get_whatsapp_key()}"
    }

    url = f"https://graph.facebook.com/v15.0/{cm.get_whatsapp_page_id()}/messages"

    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": "nice ones all so far"
        }
    }
    requests.post(url=url, json=body, headers=header)


def get_reminders():
    client = pymongo.MongoClient(cm.get_db_connection_string())

    reminders = client["PlusWord"]["Reminders"]

    reminder_table = list(reminders.find({"enabled": True}))

    submitted = client["PlusWord"]["Times"]

    today_date = datetime.date.today()
    today_datetime = datetime.datetime.now()
    today_start = datetime.datetime(today_date.year, today_date.month, today_date.day)

    submitted = list(submitted.find({"load_ts": {'$gte': today_start}}))

    players_submitted = [x.get("phone_number") for x in submitted]

    for row in reminder_table:
        if row.get("time") == today_datetime.strftime("%H:%M"):
            phone_number = row.get("phone_number")
            if phone_number not in players_submitted:
                send_reminder(phone_number)


if __name__ == "__main__":
    get_reminders()
