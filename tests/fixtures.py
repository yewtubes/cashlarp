"""Explicit identities for tests only; production Store starts empty."""
from server import APIError, Store as EmptyStore, make_server as empty_server

DEMO_PASSWORD = "play-money-only"


def seed(store):
    for username, display in (("kotik", "Kotik"), ("friend", "Friend")):
        try:
            store.register(username, DEMO_PASSWORD, display)
        except APIError as error:
            if error.status != 409:
                raise
    return store


def Store(path):
    return seed(EmptyStore(path))


def make_server(host, port, path):
    server = empty_server(host, port, path)
    seed(server.store)
    return server
