from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

import config


# base class
class Base(DeclarativeBase):
    pass


# user table
class User(Base):
    __tablename__ = "users"

    # account
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))

    # mailbox
    imap_host: Mapped[str] = mapped_column(String(100), default="")
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    imap_user: Mapped[str] = mapped_column(String(200), default="")
    imap_password_enc: Mapped[str] = mapped_column(Text, default="")

    # whatsapp
    wa_phone: Mapped[str] = mapped_column(String(30), default="")
    wa_apikey_enc: Mapped[str] = mapped_column(Text, default="")

    # notifications
    notify_channel: Mapped[str] = mapped_column(String(20), default="whatsapp")  # whatsapp/telegram
    tg_link_code: Mapped[str] = mapped_column(String(40), default="")
    tg_chat_id: Mapped[str] = mapped_column(String(30), default="")

    # ai model
    ai_provider: Mapped[str] = mapped_column(String(20), default="gemini")  # gemini/claude
    gemini_key_enc: Mapped[str] = mapped_column(Text, default="")
    anthropic_key_enc: Mapped[str] = mapped_column(Text, default="")

    # schedule
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    frequency: Mapped[str] = mapped_column(String(20), default="daily")  # daily/3 days/weekly
    send_hour: Mapped[int] = mapped_column(Integer, default=8)
    send_weekday: Mapped[int] = mapped_column(Integer, default=0)  # 0 = Monday
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Berlin")
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # summary
    summary_mode: Mapped[str] = mapped_column(String(20), default="short")  # short/per email
    sensitivity: Mapped[str] = mapped_column(String(20), default="normal")  # strict/normal/relaxed

    # features
    feat_attachments: Mapped[bool] = mapped_column(Boolean, default=True)
    feat_drafts: Mapped[bool] = mapped_column(Boolean, default=False)
    feat_calendar: Mapped[bool] = mapped_column(Boolean, default=True)
    calendar_type: Mapped[str] = mapped_column(String(20), default="google")  # google/apple
    feat_send_if_empty: Mapped[bool] = mapped_column(Boolean, default=False)

    # writing style
    style_profile: Mapped[str] = mapped_column(Text, default="")


# database engine
engine = create_engine(config.get("DATABASE_URL", "sqlite:///data.db"), pool_pre_ping=True)

# session factory
Session = sessionmaker(engine)

# create tables
Base.metadata.create_all(engine)