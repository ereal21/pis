import datetime

from bot.database.models import User, ItemValues, Goods, Categories, PromoCode
from bot.database import Database
from bot.misc import EnvKeys
from bot.database.methods.read import get_role_id_by_name


def set_role(telegram_id: str, role: int) -> None:
    session = Database().session
    owner_raw = EnvKeys.OWNER_ID
    owner_id = None
    if owner_raw:
        try:
            owner_id = int(owner_raw)
        except (TypeError, ValueError):
            owner_id = None

    owner_role_id = get_role_id_by_name('OWNER')
    admin_role_id = get_role_id_by_name('ADMIN')
    target_id = None
    try:
        target_id = int(telegram_id)
    except (TypeError, ValueError):
        pass

    if owner_id is not None and target_id == owner_id:
        # Always keep the environment owner as OWNER in the database
        if owner_role_id is not None:
            role = owner_role_id
    elif owner_role_id is not None and role == owner_role_id and target_id != owner_id:
        # Prevent elevating other accounts to OWNER role
        if admin_role_id is not None:
            role = admin_role_id
        else:
            role = 1

    session.query(User).filter(User.telegram_id == telegram_id).update(
        values={User.role_id: role})
    session.commit()


def update_balance(telegram_id: int | str, summ: int) -> None:
    old_balance = User.balance
    new_balance = old_balance + summ
    Database().session.query(User).filter(User.telegram_id == telegram_id).update(
        values={User.balance: new_balance})
    Database().session.commit()


def update_user_language(telegram_id: int, language: str) -> None:
    Database().session.query(User).filter(User.telegram_id == telegram_id).update(
        values={User.language: language})
    Database().session.commit()


def update_last_activity(telegram_id: int, timestamp: str | None = None) -> None:
    session = Database().session
    if timestamp is None:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    session.query(User).filter(User.telegram_id == telegram_id).update(
        values={User.last_activity: timestamp, User.last_reminder_sent: None}
    )
    session.commit()


def update_last_reminder_sent(telegram_id: int, timestamp: str) -> None:
    session = Database().session
    session.query(User).filter(User.telegram_id == telegram_id).update(
        values={User.last_reminder_sent: timestamp}
    )
    session.commit()


def buy_item_for_balance(telegram_id: str, summ: int) -> int:
    old_balance = User.balance
    new_balance = old_balance - summ
    Database().session.query(User).filter(User.telegram_id == telegram_id).update(
        values={User.balance: new_balance})
    Database().session.commit()
    return Database().session.query(User.balance).filter(User.telegram_id == telegram_id).one()[0]


def update_item(item_name: str, new_name: str, new_description: str, new_price: int,
                new_category_name: str, new_delivery_description: str | None) -> None:
    Database().session.query(ItemValues).filter(ItemValues.item_name == item_name).update(
        values={ItemValues.item_name: new_name}
    )
    Database().session.query(Goods).filter(Goods.name == item_name).update(
        values={Goods.name: new_name,
                Goods.description: new_description,
                Goods.price: new_price,
                Goods.category_name: new_category_name,
                Goods.delivery_description: new_delivery_description}
    )
    Database().session.commit()


def update_category(category_name: str, new_name: str) -> None:
    Database().session.query(Goods).filter(Goods.category_name == category_name).update(
        values={Goods.category_name: new_name})
    Database().session.query(Categories).filter(Categories.name == category_name).update(
        values={Categories.name: new_name})
    Database().session.commit()


def update_promocode(code: str, discount: int | None = None, expires_at: str | None = None) -> None:
    """Update promo code discount or expiry date."""
    values = {}
    if discount is not None:
        values[PromoCode.discount] = discount
    if expires_at is not None or expires_at is None:
        values[PromoCode.expires_at] = expires_at
    if not values:
        return
    Database().session.query(PromoCode).filter(PromoCode.code == code).update(values=values)
    Database().session.commit()
