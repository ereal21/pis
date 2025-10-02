import sqlalchemy.exc
from sqlalchemy import func
import random
from bot.database.models import (
    User,
    ItemValues,
    Goods,
    Categories,
    BoughtGoods,
    Operations,
    UnfinishedOperations,
    PromoCode,
    PendingPurchase,
    Role,
)
from bot.database import Database
from bot.misc import EnvKeys


def _resolve_owner_id() -> int | None:
    owner_raw = EnvKeys.OWNER_ID
    if not owner_raw:
        return None
    try:
        return int(owner_raw)
    except (TypeError, ValueError):
        return None


def _get_owner_role_id(session) -> int | None:
    owner_role = session.query(Role.id).filter(Role.name == 'OWNER').first()
    if owner_role:
        return owner_role[0]
    return session.query(func.max(Role.id)).scalar()


def create_user(telegram_id: int, registration_date, referral_id, role: int = 1,
                language: str | None = None, username: str | None = None) -> None:
    session = Database().session
    owner_id = _resolve_owner_id()
    desired_role = role
    if owner_id is not None and telegram_id == owner_id:
        owner_role_id = _get_owner_role_id(session)
        if owner_role_id is not None:
            desired_role = owner_role_id
    try:
        user = session.query(User).filter(User.telegram_id == telegram_id).one()
        updated = False
        if user.username != username:
            user.username = username
            updated = True
        if not user.last_activity:
            user.last_activity = registration_date
            updated = True
        if owner_id is not None and telegram_id == owner_id:
            owner_role_id = _get_owner_role_id(session)
            if owner_role_id is not None and user.role_id != owner_role_id:
                user.role_id = owner_role_id
                updated = True
        if updated:
            session.commit()
    except sqlalchemy.exc.NoResultFound:
        if referral_id != '':
            session.add(
                User(telegram_id=telegram_id, role_id=desired_role, registration_date=registration_date,
                     referral_id=referral_id, language=language, username=username))
            session.commit()
        else:
            session.add(
                User(telegram_id=telegram_id, role_id=desired_role, registration_date=registration_date,
                     referral_id=None, language=language, username=username))
            session.commit()


def create_item(item_name: str, item_description: str, item_price: int, category_name: str,
                delivery_description: str | None = None) -> None:
    session = Database().session
    session.add(
        Goods(name=item_name, description=item_description, price=item_price,
              category_name=category_name, delivery_description=delivery_description))
    session.commit()


def add_values_to_item(item_name: str, value: str, is_infinity: bool) -> None:
    session = Database().session
    if is_infinity is False:
        session.add(
            ItemValues(name=item_name, value=value, is_infinity=False))
    else:
        session.add(
            ItemValues(name=item_name, value=value, is_infinity=True))
    session.commit()


def create_category(category_name: str, parent: str | None = None) -> None:
    session = Database().session
    session.add(
        Categories(name=category_name, parent_name=parent))
    session.commit()


def create_operation(user_id: int, value: int, operation_time: str) -> None:
    session = Database().session
    session.add(
        Operations(user_id=user_id, operation_value=value, operation_time=operation_time))
    session.commit()


def start_operation(user_id: int, value: int, operation_id: str, message_id: int | None = None) -> None:
    session = Database().session
    session.add(
        UnfinishedOperations(user_id=user_id, operation_value=value, operation_id=operation_id, message_id=message_id))
    session.commit()


def create_pending_purchase(user_id: int, payment_id: str, item_name: str, price: float,
                            message_id: int | None = None) -> None:
    session = Database().session
    session.add(
        PendingPurchase(payment_id=payment_id, user_id=user_id, item_name=item_name,
                         price=price, message_id=message_id)
    )
    session.commit()


def add_bought_item(item_name: str, value: str, price: int, buyer_id: int,
                    bought_time: str) -> int:
    session = Database().session
    unique_id = random.randint(1000000000, 9999999999)
    session.add(
        BoughtGoods(name=item_name, value=value, price=price, buyer_id=buyer_id, bought_datetime=bought_time,
                    unique_id=str(unique_id)))
    session.commit()
    return unique_id


def create_promocode(code: str, discount: int, expires_at: str | None) -> None:
    session = Database().session
    session.add(PromoCode(code=code, discount=discount, expires_at=expires_at, active=True))
    session.commit()
