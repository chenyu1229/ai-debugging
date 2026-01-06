from app_under_test.buggy import divide, get_user, parse_user

def test_divide_ok():
    assert divide(4, 2) == 2

def test_divide_zero():
    # intentionally fails: ZeroDivisionError
    divide(1, 0)

def test_get_user_timeout():
    # intentionally fails: TimeoutError
    get_user(1)

def test_parse_user_keyerror():
    # intentionally fails: KeyError
    parse_user({})
