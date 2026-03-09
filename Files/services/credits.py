"""Credit management service for consultancy firms."""

from extensions import db
from models.consultancy import ConsultancyFirm, CreditTransaction


def add_credits(firm_id: int, credits: int, description: str = "Manual credit top-up") -> CreditTransaction:
    """Add credits to a consultancy firm's balance.

    Args:
        firm_id: The ID of the firm to credit.
        credits: The number of credits to add (must be positive).
        description: A human-readable note for the transaction log.

    Returns:
        The created CreditTransaction record.

    Raises:
        ValueError: If credits is not a positive integer or firm not found.
    """
    if credits <= 0:
        raise ValueError("Credits to add must be a positive integer.")

    firm = db.session.get(ConsultancyFirm, firm_id)
    if firm is None:
        raise ValueError(f"Consultancy firm with id {firm_id} not found.")

    firm.credit_balance += credits

    transaction = CreditTransaction(
        firm_id=firm.id,
        student_id=None,
        transaction_type="purchase",
        credits_used=credits,
        description=description,
    )
    db.session.add(transaction)
    db.session.commit()

    return transaction


def deduct_credit(student_id: int, firm_id: int, description: str = "Assessment completed") -> CreditTransaction:
    """Deduct one credit from a firm when a student completes an assessment.

    Args:
        student_id: The ID of the student who completed the assessment.
        firm_id: The ID of the firm to debit.
        description: A human-readable note for the transaction log.

    Returns:
        The created CreditTransaction record.

    Raises:
        ValueError: If the firm is not found or has insufficient credits.
    """
    firm = db.session.get(ConsultancyFirm, firm_id)
    if firm is None:
        raise ValueError(f"Consultancy firm with id {firm_id} not found.")

    if firm.credit_balance <= 0:
        raise ValueError(
            f"Firm '{firm.firm_name}' (id={firm_id}) has insufficient credits "
            f"(balance={firm.credit_balance})."
        )

    firm.credit_balance -= 1

    transaction = CreditTransaction(
        firm_id=firm.id,
        student_id=student_id,
        transaction_type="usage",
        credits_used=1,
        description=description,
    )
    db.session.add(transaction)
    db.session.commit()

    return transaction
