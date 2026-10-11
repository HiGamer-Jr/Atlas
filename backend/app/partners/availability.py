"""Gate A has no operational partner catalog or selectable contexts."""

from sqlalchemy.orm import Session

from app.identity.schemas import Principal
from app.partners.schemas import PartnerAvailability


def get_partner_availability(db: Session, principal: Principal) -> PartnerAvailability:
    return PartnerAvailability()
