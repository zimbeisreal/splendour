# verify_bonus.py
from app import app
from extensions import db
from models import Wallet, Transaction
from bonus.daily import DailyBonusProcessor

user_id = 1  # change to a real test user

with app.app_context():
    w = Wallet.query.filter_by(user_id=user_id).first()
    print(f"BEFORE  balance={w.balance}  locked={w.locked_balance}")

    result = DailyBonusProcessor(user_id=user_id).run()
    print(f"RESULT  success={result['success']}  total_bonus={result.get('total_bonus')}")
    print(f"        packages_processed={result.get('packages_processed')}  "
          f"successful={result.get('packages_successful')}  "
          f"failed={result.get('packages_failed')}")
    for p in result.get('processed_packages', []):
        print(f"        - {p['package_name']}: success={p['success']} "
              f"bonus={p.get('bonus_amount')} error={p.get('error')}")

    db.session.refresh(w)
    print(f"AFTER   balance={w.balance}  locked={w.locked_balance}")

    tx = (Transaction.query
          .filter_by(user_id=user_id)
          .filter(Transaction.type.in_(['bonus_credit', 'bonus_credit_locked']))
          .order_by(Transaction.id.desc())
          .first())
    if tx:
        print(f"TX      status={tx.status}  matures_at={tx.matures_at}  amount={tx.amount}")

    before_b = w.balance
    before_l = w.locked_balance
    matured = DailyBonusProcessor.mature_pending_bonuses(user_id)
    db.session.refresh(w)
    print(f"MATURITY matured={matured}  "
          f"balance_changed={w.balance != before_b}  "
          f"locked_changed={w.locked_balance != before_l}")