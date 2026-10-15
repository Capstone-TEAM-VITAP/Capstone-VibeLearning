def login_user(username, password):
    user = find_user(username)
    if user:
        return check_password(user, password)
    return False

def generate_token(user):
    return create_jwt(user)
