from extensions import db


class ConsultancyFirm(db.Model):
    __tablename__ = 'consultancy_firms'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    firm_name = db.Column(db.String(255), unique=True, nullable=False)
    contact_email = db.Column(db.String(255), unique=True, nullable=False)
    contact_phone = db.Column(db.String(20), nullable=True)
    credit_balance = db.Column(db.Integer, nullable=False, default=0)
    price_per_assessment = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    # Relationships
    admins = db.relationship('FirmAdmin', backref='firm', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('CreditTransaction', backref='firm', lazy=True, cascade='all, delete-orphan')
    students = db.relationship('StudentDetails', backref='firm', lazy=True)

    def __repr__(self):
        return f"<ConsultancyFirm id={self.id} name={self.firm_name}>"


class FirmAdmin(db.Model):
    __tablename__ = 'firm_admins'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    firm_id = db.Column(
        db.Integer,
        db.ForeignKey('consultancy_firms.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    def __repr__(self):
        return f"<FirmAdmin id={self.id} username={self.username}>"


class CreditTransaction(db.Model):
    __tablename__ = 'credit_transactions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    firm_id = db.Column(
        db.Integer,
        db.ForeignKey('consultancy_firms.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    student_id = db.Column(
        db.Integer,
        db.ForeignKey('student_details.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    credits_used = db.Column(db.Integer, nullable=False, default=0)
    transaction_type = db.Column(
        db.Enum('purchase', 'usage', 'refund', 'adjustment', name='transaction_type_enum'),
        nullable=False,
    )
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    def __repr__(self):
        return f"<CreditTransaction id={self.id} type={self.transaction_type}>"
