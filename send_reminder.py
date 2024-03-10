import requests
import pymongo
import datetime
import credential_manager as cm
import sys


def send_reminder(phone_number):
    """
    Sends reminder to the player.

    Arguments:
        phone_number: the phone number of the player to remind
    """

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


def check_if_valid_reminder(phone_number: str):
    """
    Check the DB for two conditions:
        1) Has the player got a reminder set.
        2) Has the player failed to submit a time today.

    If both are true then we message the player to remind them to submit.

    Arguments:
        phone_number: the phone number of the player to remind
    """

    today_date = datetime.date.today()
    today_datetime = datetime.datetime.now()
    today_start = datetime.datetime(today_date.year, today_date.month, today_date.day)

    client = pymongo.MongoClient(cm.get_db_connection_string())

    reminders = client["PlusWord"]["Reminders"]
    player_reminder = reminders.find_one({"enabled": True, "phone_number": phone_number})

    submitted = client["PlusWord"]["Times"]
    player_submission = submitted.find_one({"load_ts": {'$gte': today_start}, "phone_number": phone_number})

    if player_submission:
        return False

    if not player_reminder:
        return False
    elif player_reminder.get("time") == today_datetime.strftime("%H:%M"):
        return True

    return False


def main():
    _, phone_number = sys.argv
    if check_if_valid_reminder(phone_number):
        send_reminder(phone_number)


if __name__ == "__main__":
    main()
