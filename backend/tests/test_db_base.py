from sqlalchemy import create_engine, String
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from app.db.base import Base, TimestampMixin


class _WidgetForTest(Base, TimestampMixin):
    __tablename__ = "widgets_test_only"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))


def test_timestamp_mixin_sets_created_updated_and_leaves_deleted_null():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    widget = _WidgetForTest(name="bolt")
    session.add(widget)
    session.commit()
    session.refresh(widget)

    assert widget.created_at is not None
    assert widget.updated_at is not None
    assert widget.deleted_at is None
