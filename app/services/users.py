from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import UserModel


def get_or_create_dev_user(db: Session) -> UserModel:
    user = db.execute(select(UserModel).where(UserModel.username == "dev")).scalar_one_or_none()
    if user is not None:
        return user

    user = UserModel(username="dev", display_name="Development User", role="admin", is_active=True)
    db.add(user)
    db.flush()
    return user

