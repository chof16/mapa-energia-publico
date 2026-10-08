"""SQLAlchemy's SQLite compiler over TursoDB's remote DB-API driver."""

from __future__ import annotations

import turso_serverless
from sqlalchemy.dialects.sqlite.base import SQLiteDialect


class _TursoDBAPI:
    """Expose the DB-API attributes SQLAlchemy's SQLite dialect expects."""

    # TursoDB supports modern SQLite syntax. This is a capability floor, not
    # the remote server's exact version (which the driver does not expose).
    sqlite_version_info = (3, 35, 0)
    paramstyle = turso_serverless.paramstyle
    Error = turso_serverless.Error
    OperationalError = turso_serverless.OperationalError
    ProgrammingError = turso_serverless.ProgrammingError
    IntegrityError = turso_serverless.IntegrityError
    DatabaseError = turso_serverless.DatabaseError
    InterfaceError = turso_serverless.InterfaceError
    InternalError = turso_serverless.InternalError
    DataError = turso_serverless.DataError
    NotSupportedError = turso_serverless.NotSupportedError

    @staticmethod
    def connect(*args, **kwargs):
        return turso_serverless.connect(*args, **kwargs)


class TursoServerlessDialect(SQLiteDialect):
    """Compile SQLite SQL while using Turso's HTTP connection semantics."""

    driver = "turso_serverless"
    supports_statement_cache = True

    @classmethod
    def import_dbapi(cls):
        return _TursoDBAPI

    def create_connect_args(self, url):
        # The creator supplied by database.py owns the URL and auth token.
        return [], {}

    def _get_server_version_info(self, connection):
        return self.dbapi.sqlite_version_info
