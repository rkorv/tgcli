from datetime import datetime
import parsedatetime as pdt


def str_to_interval(cfg):
    str_interval = "1200s"
    if isinstance(cfg, str):
        str_interval = cfg
    else:
        raise Exception("Can't parse interval '%s'" % cfg)

    t = pdt.Calendar().parseDT(str_interval, sourceTime=datetime.min)[0].time()
    interval = (t.hour * 60 + t.minute) * 60 + t.second
    if interval == 0:
        raise Exception("Can't parse interval '%s'" % cfg)

    day_in_secs = 60 * 60 * 24
    if interval > day_in_secs:
        print("Too large interval '%s' was modified to '1d'" % str_interval)
        interval = day_in_secs

    return interval
