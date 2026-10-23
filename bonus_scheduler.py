from app import create_app
from extensions import db
from models import Package
import logging
from bonus.daily import DailyBonusProcessor

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

app = create_app()


def run_daily_bonus():

    with app.app_context():

        logger.info("Bonus scheduler started...")

        user_ids = (
            db.session.query(Package.user_id)
            .filter(Package.status == "active")
            .distinct()
            .all()
        )
        # to do so that only users who are eligible are queried
#         WHERE status='active'
# AND (
#     last_bonus_at IS NULL
#     OR last_bonus_at <= NOW() - INTERVAL '24 hours'
# )
#         logger.info(
#             f"Found {len(user_ids)} users with active packages."
#         )

        processed = 0
        failed = 0
        total_bonus = 0

        for (user_id,) in user_ids:

            try:
                result = DailyBonusProcessor(user_id).run()

                processed += 1
                total_bonus += result.get("total_bonus", 0)

            except Exception:
                failed += 1
                logger.exception(
                    f"Failed processing user {user_id}"
                )


        logger.info(
            f"""
            Daily Bonus Scheduler Finished

            Users found: {len(user_ids)}
            Processed: {processed}
            Failed: {failed}
            Total bonus paid: {total_bonus}
            """
        )


if __name__ == "__main__":
    run_daily_bonus()


# from app import create_app
# from extensions import db
# from models import User, Package
# import logging
# from bonus.daily import DailyBonusProcessor

# logger = logging.getLogger(__name__)

# app = create_app()

# with app.app_context():
#     print("Bonus scheduler started...")
#     print("Quering the database for users with package.........")

#     user_ids = (
#     db.session.query(Package.user_id)
#     .filter(Package.status == "active")
#     .distinct()
#     .all()
# )
#     print("User query sucessful...........")
#     print(f"Found {len(user_ids)} users with active packages.")

#     processed = 0
#     failed = 0
#     total_bonus = 0
#     for (user_id,) in user_ids:
#         try:
#             result = DailyBonusProcessor(user_id).run()

#             processed += 1
#             total_bonus += result.get("total_bonus", 0)

#         except Exception:
#             failed += 1
#             logger.exception(f"Failed processing user {user_id}")
#     logger.info(
#         f"""
#     Daily Bonus Scheduler Finished

#     Users found: {len(user_ids)}
#     Processed: {processed}
#     Failed: {failed}
#     Total bonus paid: {total_bonus}
#     """
#     )