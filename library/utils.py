import datetime


def get_default_date():
    return datetime.date.today() + datetime.timedelta(days=14)