"""Measurement. See EVAL-PLAN.md.

Application code, not test code: production writes records too, so this cannot live
under tests/. Nothing here decides anything — it observes a run and describes it.
"""

from app.eval.record import RunRecord, record_from_run

__all__ = ["RunRecord", "record_from_run"]
