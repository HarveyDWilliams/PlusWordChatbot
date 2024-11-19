import pymongo
import credential_manager as cm
import sys
import datetime
from subprocess import run


def schedule_reminder(phone_number: str, time: str):
    """
    Uses the linux at command to schedule the reminder python script.

    Arguments:
        phone_number (str): phone number to send the reminder to
        time (str): time at which to send the reminder
    """

    run(f'sh ./send_reminder.sh {phone_number} | at {time} ', shell=True)


def set_reminders(reminders):
    """
    Iterates through reminders scheduling a reminder for each.
    """

    if not reminders:
        return

    for phone_number, data in reminders.items():
        if data.get("enabled"):
            schedule_reminder(
                phone_number,
                data.get("reminder_time")
            )


def get_reminders() -> [{str: str}]:
    """
    Gets the dictionary of player reminder data from the DB.
    """

    client = pymongo.MongoClient(cm.get_db_connection_string())
    reminders = client["PlusWord"]["Reminders"]
    times = client["PlusWord"]["Times"]

    today_date = datetime.date.today()
    tomorrow_date = datetime.date.today() + datetime.timedelta(days=1)
    today_start = datetime.datetime(today_date.year, today_date.month, today_date.day)
    today_end = datetime.datetime(tomorrow_date.year, tomorrow_date.month, tomorrow_date.day)

    yesterday_submissions = times.find({"load_ts": {'$gte': today_start, '$lt': today_end}})

    reminder_data = dict()
    for submission in yesterday_submissions:
        reminder_config = reminders.find_one({"phone_number": submission.get("phone_number")})
        if not reminder_config:
            continue
        reminder_time = datetime.datetime.strptime(reminder_config["time"],"%H:%M")
        reminder_delta = datetime.timedelta(hours=reminder_time.hour, minutes=reminder_time.minute)
        time_to_remind = min(submission.get("load_ts") + datetime.timedelta(hours=23, minutes=59),
                             today_start + reminder_delta
                             )
        if time_to_remind <= datetime.datetime.now():
            continue
        reminder_data[submission.get("phone_number")] = {
            "enabled": reminder_config["enabled"],
            "reminder_time": reminder_config["time"]
        }

    return reminder_data


def main():
    reminders = get_reminders()
    set_reminders(reminders)


if __name__ == "__main__":
    main()
