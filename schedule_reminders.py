import pymongo
import credential_manager as cm
import sys
from subprocess import call


def schedule_reminder(phone_number: str, time: str):
    """
    Uses the linux at command to schedule the reminder python script.

    Arguments:
        phone_number (str): phone number to send the reminder to
        time (str): time at which to send the reminder
    """

    call(["at", time, "-f", "python3 send_reminder.py", phone_number])


def set_reminders(reminders):
    """
    Iterates through reminders scheduling a reminder for each.
    """

    if not reminders:
        return

    for reminder in reminders:
        schedule_reminder(
            reminder.get("phone_number"),
            reminder.get("time")
        )


def get_reminders() -> [{str: str}]:
    """
    Gets the dictionary of player reminder data from the DB.
    """

    client = pymongo.MongoClient(cm.get_db_connection_string())
    reminders = client["PlusWord"]["Reminders"]

    return list(reminders.find({"enabled": True}))


def main():
    _, phone_number = sys.argv
    reminders = get_reminders()
    set_reminders(reminders)


if __name__ == "__main__":
    main()
