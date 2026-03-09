from extensions import db


class ConsultancyFirm(db.Model):
    """A consultancy firm that manages students and uses credits."""

    __tablename__ = "consultancy_firms"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    credit_balance = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    # Relationships
    admins = db.relationship("FirmAdmin", backref="firm", lazy=True)
    students = db.relationship("StudentDetails", backref="firm", lazy=True)
    credit_transactions = db.relationship(
        "CreditTransaction", backref="firm", lazy=True
    )

    def __repr__(self):
        return f"<ConsultancyFirm id={self.id} name={self.name!r} credits={self.credit_balance}>"


class FirmAdmin(db.Model):
    """An administrator who belongs to a consultancy firm."""

    __tablename__ = "firm_admins"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    firm_id = db.Column(
        db.Integer,
        db.ForeignKey("consultancy_firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f"<FirmAdmin id={self.id} username={self.username!r} firm_id={self.firm_id}>"


class CreditTransaction(db.Model):
    """Audit log for every credit addition or deduction."""

    __tablename__ = "credit_transactions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    firm_id = db.Column(
        db.Integer,
        db.ForeignKey("consultancy_firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("student_details.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transaction_type = db.Column(
        db.String(10), nullable=False
    )  # "credit" or "debit"
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Relationship back to student (optional, since student_id is nullable)
    student = db.relationship("StudentDetails", backref="credit_transactions")

    def __repr__(self):
        return (
            f"<CreditTransaction id={self.id} type={self.transaction_type!r} "
            f"amount={self.amount} firm_id={self.firm_id}>"
        )
