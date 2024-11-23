import logging
import random
import cv2
import pytesseract
from flask import Flask, request
import pymongo
import re
import datetime
import requests
import credential_manager as cm
from PIL import Image


class Bot:
    """
    Class for the digesting the data from the WhatsApp webhook.
    Contains methods for processing the data and responding to users via WhatsApp messages.

    Attributes:
        client: pymongo client for accessing MongoDB
        type (str): message type for received message
        msg_from (str): username of user who sent received message
        number (str): phone number of user who sent received message
        img_id (str): image id of the attached image in the received message
        msg_text (str): text contained in the received message
    """

    def __init__(self, json_in):
        """
        Constructor for Bot class.

        Arguments:
            json_in: incoming json received from webhook containing message data
        """

        value = json_in.get("entry")[0].get("changes")[0].get("value")
        self.client = pymongo.MongoClient(cm.get_db_connection_string())
        self.type = value.get("messages")[0].get("type")
        self.msg_from = value.get("contacts")[0].get("profile").get("name")
        self.number = value.get("contacts")[0].get("wa_id")
        if self.type == "image":
            self.img_id = value.get("messages")[0].get("image").get("id")
        elif self.type == "text":
            self.msg_text = value.get("messages")[0].get("text").get("body")

    def send_text(self, text: str):
        """
        Sends a text to the user from which the initial message was received.
        Arguments:
            text (str): text message body to be sent
        """

        print(f"Sending text to {self.number}: {text}")

        header = {
            "Authorization": f"Bearer {cm.get_whatsapp_key()}"
        }

        url = f"https://graph.facebook.com/v21.0/{cm.get_whatsapp_page_id()}/messages"

        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self.number,
            "type": "text",
            "text": {
                "preview_url": True,
                "body": text
            }
        }
        requests.post(url=url, json=body, headers=header)

    def store_time_from_image(self):
        """
        Saves the image data from graph api to be read by pytesseract and stored in db.
        """

        header = {
            "Authorization": f"Bearer {cm.get_whatsapp_key()}"
        }

        print("Getting whatsapp reponse")
        response = requests.get(url=f"https://graph.facebook.com/v21.0/{self.img_id}", headers=header)
        print("Got whatsapp response", response.content)

        img_url = response.json().get("url")

        image = requests.get(url=img_url, headers=header).content

        with open('submission.jpg', 'wb') as handler:
            handler.write(image)

        image = Image.open("submission.jpg")
        upscaled_image = image.resize((image.width * 2, image.height * 2), resample=Image.BOX)
        upscaled_image.save("submission.jpg")

        img = cv2.imread('submission.jpg')
        text = pytesseract.image_to_string(img)

        db = self.get_db_collection("PlusWord", "Times")

        today_date = datetime.date.today()
        today_start = datetime.datetime(today_date.year, today_date.month, today_date.day)

        print("Checking db")
        if db.find_one({"phone_number": self.number, "load_ts": {'$gte': today_start}}):
            self.send_text(f"You have already submitted a time for today. Use !edit to change your time.")
            return

        time = re.search(r"(?<=You completed today's PlusWord in\n\n)((\d+:)?[0-5][0-9]:[0-5][0-9])", text)

        if time:
            time = time.group()
            data = {
                "user": self.msg_from,
                "phone_number": self.number,
                "time": time,
                "load_ts": datetime.datetime.now()
            }
            print("Inserting time", time)
            db.insert_one(data)

            self.send_text(f"Saved time {time}.")
            self.send_random_message()
            self.send_motivation(time)
            return

        self.send_text("No time found in message. Please use !submit to submit your time.")
        return

    def store_time(self):
        """
        Saves a manual time submission into the db.
        """

        db = self.get_db_collection("PlusWord", "Times")

        today_date = datetime.date.today()
        today_start = datetime.datetime(today_date.year, today_date.month, today_date.day)

        if db.find_one({"phone_number": self.number, "load_ts": {'$gte': today_start}}):
            self.send_text(f"You have already submitted a time for today. Use !edit to change your time.")
            return
        time = re.search(r"((\d+:)?[0-5][0-9]:[0-5][0-9])", self.msg_text)

        if time:
            time = time.group()
            data = {
                "user": self.msg_from,
                "phone_number": self.number,
                "time": time,
                "load_ts": datetime.datetime.now()
            }
            db.insert_one(data)

            self.send_text(f"Saved time {time}.")
            self.send_random_message()
            self.send_motivation(time)
            return

        self.send_text("No time found in message. Please use format 00:00 to submit.")
        return

    def edit_time(self):
        """
        Replaces a preexisting time in the db with data entered by the user.
        """

        db = self.get_db_collection("PlusWord", "Times")

        today_date = datetime.date.today()
        today_start = datetime.datetime(today_date.year, today_date.month, today_date.day)

        if db.find_one({"phone_number": self.number, "load_ts": {'$gte': today_start}}) is None:
            self.send_text(f"You have not submitted a time for today. Use !submit to submit your time.")
            return

        time = re.search(r"((\d+:)?[0-5][0-9]:[0-5][0-9])", self.msg_text)

        if time:
            time = time.group()
            data = {
                "$set": {"time": time}
            }
            db.update_one(
                {
                    "phone_number": self.number,
                    "load_ts": {'$gte': today_start}
                },
                data
            )

            self.send_text(f"Updated time to {time}.")
            return

        self.send_text("No time found in message. Please use format 00:00 to submit.")
        return

    def reminder(self):
        """
        Enables, disables, or sets a reminder time in the db for use in the reminder script.

        NOTE: Currently non-functional, WhatsApp only allow replies within 24 hours of contact from user.
        Working on a new solution based on reminding 24 hours from previous submission.
        """

        option = re.search(r"^!reminder ([A-z]+)", self.msg_text)

        if not option:
            self.send_text("Please specify an option from enable, disable and set. Format: !reminder option [time].")
            return

        option = option.group(1).lower()
        db = self.get_db_collection("PlusWord", "Reminders")

        if option == "enable":
            time = re.search(r"^!reminder [A-z]+ ((?:[0-1]?[0-9]|2[0-3]):[0-5][0-9])", self.msg_text)
            if time:
                time = time.group(1)
                if db.find_one({"phone_number": self.number}):
                    data = {
                        "$set": {"enabled": True, "time": time}
                    }
                    db.update_one(
                        {
                            "phone_number": self.number
                        },
                        data
                    )
                    self.send_text(f"Notifications enabled, time set to {time}.")
                else:
                    data = {
                        "phone_number": self.number,
                        "time": time,
                        "enabled": True
                    }
                    db.insert_one(data)
                    self.send_text(f"Notifications enabled, time set to {time}.")
            else:
                if db.find_one({"phone_number": self.number}):
                    data = {
                        "$set": {"enabled": True}
                    }
                    db.update_one(
                        {
                            "phone_number": self.number
                        },
                        data
                    )
                    self.send_text(f"Notifications re-enabled.")
                else:
                    self.send_text("No time provided in message and no existing time found in database. "
                                   "Please provide a time to enable notifications.")
        elif option == "disable":
            if db.find_one({"phone_number": self.number}):
                data = {
                    "$set": {"enabled": False}
                }
                db.update_one(
                    {
                        "phone_number": self.number
                    },
                    data
                )
                self.send_text("Notifications disabled.")
        elif option == "set":
            time = re.search(r"^!reminder [A-z]+ ((?:[0-1]?[0-9]|2[0-3]):[0-5][0-9])", self.msg_text)
            if time:
                time = time.group(1)
                if db.find_one({"phone_number": self.number}):
                    data = {
                        "$set": {"enabled": True, "time": time}
                    }
                    db.update_one(
                        {
                            "phone_number": self.number
                        },
                        data
                    )
                    self.send_text(f"Reminder time updated to {time}.")
            else:
                self.send_text("No time found in message. Format: !reminder set time.")
        else:
            self.send_text("Please specify an option from enable, disable and set. Format: !reminder option [time].")

    def retro(self):
        """
        Submits a retroactive PlusWord time. For use when the user doesn't submit on the day of the puzzle.
        """

        # format
        # !retro 15-08-2023:13:15 01:45
        db = self.get_db_collection("PlusWord", "Times")

        match = re.search(
            r"([0-9]{2}-[0-9]{2}-[0-9]{4}:[0-9]{2}:[0-9]{2}) ((\d+:)?[0-5][0-9]:[0-5][0-9])",
            self.msg_text
        )

        if match:
            date = match.group(1)
            time = match.group(2)

            try:
                submission_datetime = datetime.datetime.strptime(date, "%d-%m-%Y:%H:%M")
            except ValueError:
                self.send_text(f"Please use format !retro DD-MM-YYYY:hh:mm [hh:]mm:ss for retro submission.")
                return

            submission_datetime_start = datetime.datetime(
                submission_datetime.year,
                submission_datetime.month,
                submission_datetime.day)
            submission_datetime_end = submission_datetime_start + datetime.timedelta(days=1)

            if db.find_one({
                "phone_number": self.number,
                '$and': [
                    {"load_ts": {'$gte': submission_datetime_start}},
                    {"load_ts": {'$lt': submission_datetime_end}}
                ]
            }) is not None:
                self.send_text(f"You have already submitted a time for this day.")
                return

            data = {
                "user": self.msg_from,
                "phone_number": self.number,
                "time": time,
                "load_ts": submission_datetime,
                "retro": True
            }
            db.insert_one(data)

            self.send_text(f"Saved time {time} for {date}.")
            return

        self.send_text(f"Please use format !retro DD-MM-YYYY:hh:mm [hh:]mm:ss for retro submission.")
        return

    def get_db_collection(self, database: str, collection: str):
        """
        Gets a collection object using pymongo.
        Arguments:
            database (str): name of the database on the MongoDB server to access
            collection (str): name of the collection within the database to access
        """

        db = self.client[database]
        collection = db[collection]
        return collection

    def send_random_message(self):
        """
        Sends a random message to the user. Called as part of any submission received message as a little easter egg.
        """

        if random.randint(0, 99) != 99:
            return

        messages = [
            "Thank you so much for submitting a time.",
            "Don't forget, a PlusWord a day keeps the \"nice ones all so far\"s away!",
            "Some people call me PlusBot or maybe even Harv-E, but all I've ever wanted was to be called your friend.",
            "nice one",
            "poggers time bruh",
            "Don't tell the others but you're my favourite.",
            "A wise man once said, \"As distance tests a horse's strength, "
            "PlusWord times reveal a person's character.\"",
            "Chris Lancaster is the way and the truth and the life. No one comes "
            "close to the sub-minny except through him.",
            "I'll be back. (When you post your next PlusWord time)"
        ]

        self.send_text(random.choice(messages))

    def motivation(self):
        """
        Enables, disables, or sets a motivation message flag in the db for use in the send_motivation function.
        """
        option = re.search(r"^!motivation ([A-z]+)", self.msg_text)
        if not option:
            self.send_text("Please specify an option from enable, disable, or set. Format: !motivation option.")

        option = option.group(1).lower()

        db = self.get_db_collection("PlusWord", "Motivation")

        if option == "enable":
            data = {
                "$set": {"enabled": True, "phone_number": self.number}
            }
            db.update_one(
                {
                    "phone_number": self.number
                },
                data,
                upsert=True
            )
            self.send_text(f"""Motivation enabled for you my {
            random.choice([
                'adorable sweetheart',
                'brilliant genius',
                'caring angel',
                'dazzling beauty',
                'enchanting star',
                'fabulous wonder',
                'gentle soul',
                'heavenly delight',
                'incredible hero',
                'joyful sunshine',
                'lovely gem',
                'magical dreamer',
                'noble guardian',
                'perfect treasure',
                'radiant light',
                'stunning muse',
                'tender friend',
                'unique miracle',
                'vibrant spirit',
                'wise sage',
                'zesty enthusiast',
                'amazing visionary',
                'bold explorer',
                'charming delight',
                'delightful smile',
                'elegant princess',
                'fearless leader',
                'graceful swan'
            ])
            }.""")
        elif option == "disable":
            data = {
                "$set": {"enabled": False, "phone_number": self.number}
            }
            db.update_one(
                {
                    "phone_number": self.number
                },
                data,
                upsert=True
            )
            self.send_text(f"""Motivation disabled. I'm always here for you if you need me 🤖.""")
        elif option == "set":
            time = re.search(r"^!motivation [A-z]+ ((\d+:)?[0-5][0-9]:[0-5][0-9])", self.msg_text)
            if not time:
                self.send_text("Please specify a valid time.")
                return

            data = {
                "$set": {"enabled": False, "phone_number": self.number, "minimum_time": time.group(1)}
            }

            db.update_one(
                {
                    "phone_number": self.number
                },
                data,
                upsert=True
            )
            self.send_text(f"""Motivation minimum set to {time}. I'm sure it won't be there for long! 🦾""")

    def send_motivation(self, time):
        """
        Sends a variable motivational message based on the users time and their preset minimum time.
        """
        db = self.get_db_collection("PlusWord", "Motivation")

        if result := db.find_one({"$and": [{"phone_number": self.number}, {"enabled": True}]}):
            minimum_time = re.match(
                r"(\d+:)?([0-5][0-9]):([0-5][0-9])",
                result.get("minimum_time") if result.get("minimum_time") is not None else "01:00",
            )
            minimum_time = datetime.timedelta(
                hours=int(minimum_time.group(1)) if minimum_time.group(1) else 0,
                minutes=int(minimum_time.group(2)),
                seconds=int(minimum_time.group(3))
            )
            time = re.match(r"(\d+:)?([0-5][0-9]):([0-5][0-9])", time)
            time = datetime.timedelta(
                hours=int(time.group(1)) if time.group(1) else 0,
                minutes=int(time.group(2)),
                seconds=int(time.group(3))
            )
            messages = [
                "Lightning fast! You crushed it! ⚡",
                "You're a puzzle-solving wizard! 🧙‍️",
                "Amazing speed! You nailed it! 🚀",
                "Incredible! You solved that in no time! ⏱️",
                "Wow! You're a puzzle master! 🏆",
                "Outstanding! You didn't even break a sweat! 💪",
                "Brilliant! You're unbeatable! 🥇",
                "You're on fire! Keep it up! 🔥",
                "Phenomenal speed! You're amazing! ⭐",
                "You're unstoppable! Fantastic job! 🌟",
                "Mind-blowing speed! Well done! 👏",
                "You're a genius! That was lightning quick! ⚡",
                "Exceptional! You're a true puzzle pro! 🧩",
                "Top-notch performance! You're the best! 🥳",
                "Unbelievable! You solved it like a champ! 🏅",
                "Spectacular! You made that look easy! 😎",
                "Superb! You're a puzzle-solving superstar! 🌠",
                "Outstanding! You're on a roll! 🎉",
                "Bravo! That was impressive! 🌟",
                "Astonishing speed! You're a natural! 🌈",
                "You did it! You're a puzzle-solving machine! 🤖",
                "Fantastic work! You make it look effortless! 💫",
                "Incredible job! You crushed that puzzle! 🧠",
                "You're a puzzle-solving legend! 🦸‍",
                "Perfect! You solved it in record time! 🏁",
                "Amazing! You have lightning reflexes! ⏳",
                "You're a superstar! That was blazing fast! 🌟",
                "Outstanding work! You aced it! 📈",
                "You're brilliant! Keep shining! 🌟",
                "You did it again! You're unstoppable! 🌠"
            ] if time < minimum_time else [
                "Great effort! You'll nail it next time! 🧩",
                "Almost there! Keep trying, success is within reach! 💪",
                "Nice try! Every attempt brings you closer! 🌟",
                "Don't give up, you're doing fantastic! You’ll get it soon! 🚀",
                "So close! Keep going, you'll crack it next time! ⭐",
                "Great work! Persistence will pay off soon! 👍",
                "You're on the right track, success is near! 🌈",
                "Fantastic effort! You're learning and improving each time! 🏅",
                "You're doing great! Keep trying, you'll succeed soon! 💪",
                "Wonderful try! Every attempt is a step towards victory! 🌟",
                "You're making progress! Keep at it, you’ll get it next time! 🚀",
                "Almost there! Keep pushing, success is around the corner! 🌟",
                "You're amazing! Keep going, you’ll succeed soon! 🧠",
                "Great job! Each try brings you closer to solving it! 🌈",
                "Nice work! You're closer than you think! Keep at it! 👍",
                "You're doing fantastic! Success is just a step away! 🏅",
                "Wonderful effort! Keep pushing, you’ll get there! 🌟",
                "You're so close! Keep trying, victory is near! 💪",
                "Excellent attempt! Keep going, you’ll crack it next time! 🚀",
                "Great effort! Keep at it, you’ll succeed soon! ⭐",
                "Almost there! Stay determined, success is within reach! 🌈",
                "Well done! Keep trying, you’re improving every time! 👍",
                "You're doing great! Keep going, you'll get there soon! 🏅",
                "Fantastic try! You're on the right path, keep at it! 🌟",
                "You're amazing! Keep pushing, you’ll succeed next time! 💪",
                "Wonderful effort! Success is just around the corner! 🚀",
                "Great job! Each try gets you closer to your goal! ⭐",
                "You're almost there! Keep trying, victory is near! 🌈",
                "Nice work! Keep pushing, you’ll get it soon! 👍",
                "You're doing fantastic! Every attempt brings you closer to success! 🏅"
            ]
            self.send_text(random.choice(messages))


app = Flask(__name__)


@app.route('/', methods=['POST', 'GET'])
def home():
    """
    Default and only access point to the API, handles creation of bot for each instance of webhook data.
    """
    logging.basicConfig(filename="log.txt", level=logging.INFO)
    try:
        if request.method == "GET":
            if request.args.get('hub.verify_token') == "vtoken":
                return request.args.get('hub.challenge')
            return "Authentication failed. Invalid Token."
        if request.method == 'POST':
            if not request.json.get("entry")[0].get("changes")[0].get("value").get("messages"):
                return ""
            bot = Bot(request.json)
            if bot.type == "image":
                bot.store_time_from_image()
            if re.search("^!submit", bot.msg_text):
                bot.store_time()
            if re.search("^!edit", bot.msg_text):
                bot.edit_time()
            if re.search("^!reminder", bot.msg_text):
                bot.reminder()
            if re.search("^!retro", bot.msg_text):
                bot.retro()
            if re.search("^!motivation", bot.msg_text):
                bot.motivation()
        return ""
    except Exception as ex:
        logging.exception(f"{datetime.datetime.now()}: {ex}")
        return ""
