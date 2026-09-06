from backend.database.connection import (
    engine,
    Base
)

from backend.database.models import (
    User,
    Document
)


print(
    "Creating database tables..."
)


Base.metadata.create_all(
    bind=engine
)


print(
    "Database tables created successfully!"
)


print(
    "Tables:"
)

print(
    "- users"
)

print(
    "- documents"
)