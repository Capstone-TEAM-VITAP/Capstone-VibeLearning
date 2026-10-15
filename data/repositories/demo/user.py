def find_user(username):
    return database_find(username)

def create_user(username, password):
    return database_create(username, password)
