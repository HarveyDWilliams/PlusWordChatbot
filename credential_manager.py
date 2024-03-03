import json


def get_db_connection_string() -> str:
    try:
        with open("local/db_access.json") as file:
            file = json.loads(file.read())
            return file.get("connection_string")

    except Exception as e:
        print(e)


def get_whatsapp_key() -> str:
    try:
        with open("local/whatsapp_access.json") as file:
            file = json.loads(file.read())
            return file.get("key")
    except Exception as e:
        print(e)


def get_whatsapp_page_id() -> str:
    try:
        with open("local/whatsapp_access.json") as file:
            file = json.loads(file.read())
            return file.get("page_id")
    except Exception as e:
        print(e)
