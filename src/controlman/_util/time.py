import datetime as _datetime


_FORMAT = "%Y_%m_%d_%H_%M_%S"


def now():
    return _datetime.datetime.now(tz=_datetime.timezone.utc).strftime(_FORMAT)


def is_expired(timestamp: str, expiry_days: float) -> bool:
    exp_date = _datetime.datetime.strptime(timestamp, _FORMAT) + _datetime.timedelta(days=expiry_days)
    return exp_date <= _datetime.datetime.now()
