import copy
import sqlite3
from unittest.mock import Mock

import pytest
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError

from src.api.storage.chat_store import ChatStore
from src.api.storage.cosmos_service import CosmosService
from src.api.storage.db_service import ChatHistoryMigrationRequired, DbService


class SqlConnection:
    def __init__(self, db):
        self.db = db
        self.statements = []
        self.fail_insert = False
        self.closed = False

    def cursor(self):
        return self

    def execute(self, query, *params):
        self.statements.append(query)
        if self.fail_insert and query.startswith("INSERT INTO chat_messages"):
            raise RuntimeError("Simulated write failure")
        query = query.replace(" WITH (UPDLOCK, HOLDLOCK)", "")
        self.result = self.db.execute(query, params)
        self.rowcount = self.result.rowcount
        return self

    def fetchone(self):
        return self.result.fetchone()

    def fetchall(self):
        return self.result.fetchall()

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def close(self):
        self.closed = True


@pytest.fixture
def sql_store(monkeypatch):
    db = sqlite3.connect(":memory:")
    db.create_function("GETUTCDATE", 0, lambda: "2026-11-20")
    db.executescript("""
        CREATE TABLE chat_sessions (
            id TEXT PRIMARY KEY, user_id TEXT, title TEXT, message_count INTEGER,
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE chat_messages (
            id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
            sources TEXT, timestamp TEXT, sort_order INTEGER DEFAULT 0
        );
        INSERT INTO chat_sessions VALUES ('victim', 'alice', 'Original', 1, '', '');
        INSERT INTO chat_messages VALUES ('original', 'victim', 'user', 'Private', '[]', '', 0);
    """)
    connection = SqlConnection(db)
    store = ChatStore()
    sql = Mock(available=True)
    sql._get_connection.return_value = connection
    monkeypatch.setattr(store, "_get_sql", lambda: sql)
    yield store, db, connection
    db.close()


@pytest.mark.parametrize("operation", ["read", "save", "delete", "update", "append"])
def test_sql_foreign_session_cannot_be_read_or_modified(sql_store, operation):
    store, db, connection = sql_store
    if operation == "read":
        assert store.get_session("victim", "bob") is None
        assert store.get_messages("victim", "bob") == []
    elif operation == "save":
        assert not store.save_messages_bulk("victim", [], "bob")
    elif operation == "delete":
        assert not store.delete_session("victim", "bob")
    elif operation == "update":
        assert not store.update_session("victim", "bob", title="Changed")
    else:
        assert store.add_message("victim", "bob", "user", "Changed") is None
    assert db.execute("SELECT title FROM chat_sessions").fetchone() == ("Original",)
    assert db.execute("SELECT content FROM chat_messages").fetchall() == [("Private",)]
    assert connection.closed


def test_sql_owned_history_and_metadata_are_saved_under_ownership_lock(sql_store):
    store, db, connection = sql_store
    assert store.save_messages_bulk("victim", [{"content": "Updated"}], "alice", "New title")
    assert store.get_messages("victim", "alice")[0]["content"] == "Updated"
    assert db.execute("SELECT title, message_count FROM chat_sessions").fetchone() == ("New title", 1)
    assert "WITH (UPDLOCK, HOLDLOCK)" in connection.statements[0]
    assert store.delete_session("victim", "alice")
    assert db.execute("SELECT * FROM chat_messages").fetchall() == []


def test_sql_failed_replacement_rolls_back_original_history(sql_store):
    store, db, connection = sql_store
    connection.fail_insert = True
    with pytest.raises(RuntimeError, match="Simulated write failure"):
        store.save_messages_bulk("victim", [{"content": "Changed"}], "alice")
    assert db.execute("SELECT content FROM chat_messages").fetchall() == [("Private",)]
    assert db.execute("SELECT title, message_count FROM chat_sessions").fetchone() == ("Original", 1)
    assert connection.closed


class CosmosContainer:
    def __init__(self, partition_field):
        self.partition_field = partition_field
        self.items = {}
        self.fail_publish = False
        self.delete_on_publish = False

    def create_item(self, body):
        key = (body[self.partition_field], body["id"])
        if key in self.items:
            raise CosmosHttpResponseError(status_code=409, message="Duplicate")
        self.items[key] = copy.deepcopy({**body, "_etag": "1"})
        return copy.deepcopy(self.items[key])

    def read_item(self, item, partition_key):
        try:
            return copy.deepcopy(self.items[(partition_key, item)])
        except KeyError:
            raise CosmosResourceNotFoundError(status_code=404, message="Missing") from None

    def replace_item(self, item, body, etag, match_condition):
        key = (body[self.partition_field], item)
        if self.delete_on_publish:
            self.items.pop(key, None)
        if self.fail_publish:
            raise CosmosHttpResponseError(status_code=412, message="Concurrent change")
        current = self.read_item(item, key[0])
        if etag != current["_etag"]:
            raise CosmosHttpResponseError(status_code=412, message="Concurrent change")
        self.items[key] = copy.deepcopy({**body, "_etag": str(int(etag) + 1)})

    def delete_item(self, item, partition_key, **kwargs):
        current = self.read_item(item, partition_key)
        if kwargs.get("etag", current["_etag"]) != current["_etag"]:
            raise CosmosHttpResponseError(status_code=412, message="Concurrent change")
        del self.items[(partition_key, item)]

    def query_items(self, query, parameters, partition_key):
        return [
            copy.deepcopy({**body, "position": body.get("order")})
            for (partition, _), body in self.items.items() if partition == partition_key
        ]


@pytest.fixture
def cosmos_store():
    sessions = CosmosContainer("user_id")
    messages = CosmosContainer("session_id")
    db = Mock()
    db.get_container_client.side_effect = lambda name: (
        sessions if name == CosmosService.SESSIONS_CONTAINER else messages
    )
    store = CosmosService()
    store._initialized = True
    store._db = db
    assert store.create_session("alice", session_id="victim")
    assert store.save_messages_bulk("victim", [{"content": "Private"}], "alice")
    return store, sessions, messages


@pytest.mark.parametrize("operation", ["read", "save", "delete", "update", "append"])
def test_cosmos_foreign_session_cannot_be_read_or_modified(cosmos_store, operation):
    store, sessions, messages = cosmos_store
    original = copy.deepcopy((sessions.items, messages.items))
    if operation == "read":
        assert store.get_messages("victim", "bob") == []
    elif operation == "save":
        assert not store.save_messages_bulk("victim", [], "bob")
    elif operation == "delete":
        assert not store.delete_session("victim", "bob")
    elif operation == "update":
        assert not store.update_session("victim", "bob", title="Changed")
    else:
        assert store.add_message("victim", "bob", "user", "Changed") is None
    assert (sessions.items, messages.items) == original


def test_cosmos_same_session_id_in_different_owner_partitions_is_isolated(cosmos_store):
    store, _, _ = cosmos_store
    assert store.create_session("bob", session_id="victim")
    assert store.save_messages_bulk("victim", [{"content": "Bob"}], "bob")
    assert store.get_messages("victim", "alice")[0]["content"] == "Private"
    assert store.get_messages("victim", "bob")[0]["content"] == "Bob"
    assert store.delete_session("victim", "bob")
    assert store.get_messages("victim", "alice")[0]["content"] == "Private"


@pytest.mark.parametrize("delete_during_save", [False, True])
def test_cosmos_failed_publish_does_not_replace_or_recreate_session(cosmos_store, delete_during_save):
    store, sessions, messages = cosmos_store
    original_history = copy.deepcopy(messages.items)
    sessions.fail_publish = not delete_during_save
    sessions.delete_on_publish = delete_during_save
    with pytest.raises(CosmosHttpResponseError):
        store.save_messages_bulk("victim", [{"content": "Changed"}], "alice")
    assert messages.items == original_history
    if delete_during_save:
        assert store.get_session("victim", "alice") is None
    else:
        assert store.get_messages("victim", "alice")[0]["content"] == "Private"


def test_cosmos_legacy_history_is_blocked_and_never_deleted_as_shared_data(cosmos_store):
    store, sessions, messages = cosmos_store
    del sessions.items[("alice", "victim")]["message_partition"]
    messages.create_item({"id": "legacy", "session_id": "victim", "content": "Legacy"})
    original = copy.deepcopy(messages.items)
    with pytest.raises(ChatHistoryMigrationRequired):
        store.get_messages("victim", "alice")
    with pytest.raises(ChatHistoryMigrationRequired):
        store.save_messages_bulk("victim", [], "alice")
    assert store.delete_session("victim", "alice")
    assert messages.items == original


def test_cosmos_publication_timeout_does_not_delete_committed_snapshot(cosmos_store, monkeypatch):
    store, sessions, _ = cosmos_store
    replace = sessions.replace_item

    def committed_then_timeout(**kwargs):
        replace(**kwargs)
        raise CosmosHttpResponseError(status_code=408, message="Uncertain write outcome")

    monkeypatch.setattr(sessions, "replace_item", committed_then_timeout)
    with pytest.raises(CosmosHttpResponseError):
        store.save_messages_bulk("victim", [{"content": "Committed"}], "alice")
    assert store.get_messages("victim", "alice")[0]["content"] == "Committed"


@pytest.mark.parametrize("backend", ["sql_store", "cosmos_store"])
def test_database_facade_passes_verified_owner_to_storage(request, backend):
    store = request.getfixturevalue(backend)[0]
    db = DbService()
    db._provider = "test"
    db._chat = store
    assert db.get_session("victim", "bob") is None
    assert db.get_messages("victim", "bob") == []
    assert not db.save_messages_bulk("victim", [], "bob")
