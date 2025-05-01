import pymongo
import credential_manager as cm
import datetime
import logging
import requests


def get_reminders() -> [{str: str}]:
    """
    Gets the dictionary of player reminder data from the DB.
    """

    client = pymongo.MongoClient(cm.get_db_connection_string())
    reminders = client["PlusWord"]["Reminders"]
    times = client["PlusWord"]["Times"]

    yesterday_date = datetime.date.today() + datetime.timedelta(days=-1)
    today_date = datetime.date.today()
    yesterday_start = datetime.datetime(yesterday_date.year, yesterday_date.month, yesterday_date.day)
    yesterday_end = datetime.datetime(today_date.year, today_date.month, today_date.day)

    yesterday_submissions = times.find({"load_ts": {'$gte': yesterday_start, '$lt': yesterday_end}})

    reminder_data = dict()
    for submission in yesterday_submissions:
        reminder_config = reminders.find_one({"phone_number": submission.get("phone_number")})
        if not reminder_config:
            continue
        reminder_time = datetime.datetime.strptime(reminder_config["time"],"%H:%M")
        reminder_delta = datetime.timedelta(hours=reminder_time.hour, minutes=reminder_time.minute)
        time_to_remind = min(submission.get("load_ts") + datetime.timedelta(hours=23, minutes=59),
                             datetime.datetime(today_date.year, today_date.month, today_date.day, 0, 0) + reminder_delta
                             )
        if time_to_remind <= datetime.datetime.now():
            continue
        reminder_data[submission.get("phone_number")] = {
            "enabled": reminder_config["enabled"],
            "reminder_time": reminder_config["time"]
        }

    return reminder_data


def send_reminder(phone_number):
    """
    Sends reminder to the player.

    Arguments:
        phone_number: the phone number of the player to remind
    """

    header = {
        "Authorization": f"Bearer {cm.get_whatsapp_key()}"
    }

    url = f"https://graph.facebook.com/v21.0/{cm.get_whatsapp_page_id()}/messages"

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
    logging.info(f"Sent reminder to {phone_number}.")


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
    today_start = datetime.datetime(today_date.year, today_date.month, today_date.day, 0, 0, 0)

    client = pymongo.MongoClient(cm.get_db_connection_string())

    reminders = client["PlusWord"]["Reminders"]
    player_reminder = reminders.find_one({"$and": [{"enabled": True}, {"phone_number": phone_number}]})

    submitted = client["PlusWord"]["Times"]
    player_submission = submitted.find_one(
        {"$and": [{"load_ts": {'$gte': today_start}}, {"phone_number": phone_number}]})

    if player_submission:
        return False

    if not player_reminder:
        return False

    return True


def main():
    logging.basicConfig(filename="reminder_log.log", level=logging.INFO)
    reminders = get_reminders()
    for phone_number, values in reminders.items():
        if check_if_valid_reminder(phone_number) and values.get('enabled'):
            if datetime.datetime.now().strftime('%H:%M') == values.get('reminder_time'):
                send_reminder(phone_number)


if __name__ == "__main__":
    main()
