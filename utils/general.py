def is_positive_integer(value):
    try:
        int(value)
        if int(value) < 0:
            return False
        return True
    except ValueError:
        return False
    except TypeError:
        return False


def humanize_number(num):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return "%d%s+" % (num, ["", "K", "M", "B", "T", "P"][magnitude])
