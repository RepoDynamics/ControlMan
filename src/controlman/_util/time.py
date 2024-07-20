import datetime as _datetime


_FORMAT = "%Y_%m_%d_%H_%M_%S"


def now():
    return _datetime.datetime.now(tz=_datetime.timezone.utc).strftime(_FORMAT)


def is_expired(timestamp: str, expiry_hours: float) -> bool:
    exp_date = _datetime.datetime.strptime(timestamp, _FORMAT) + _datetime.timedelta(hours=expiry_hours)
    return exp_date <= _datetime.datetime.now()
