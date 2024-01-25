import datetime


_FORMAT = "%Y_%m_%d_%H_%M_%S"


def now():
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime(_FORMAT)


def is_expired(timestamp: str, expiry_days: float) -> bool:
    exp_date = datetime.datetime.strptime(timestamp, _FORMAT) + datetime.timedelta(days=expiry_days)
    return exp_date <= datetime.datetime.now()
