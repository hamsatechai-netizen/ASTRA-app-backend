"""
Persistence infrastructure: SQLAlchemy engine, session factory, and the
declarative base. This package owns *how* we connect to PostgreSQL;
`app/models` owns *what* is persisted (schema-carrying models will import
`Base` and the mixins from here).
"""
