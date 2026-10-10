from datetime import timezone

from models import Entry, Operation


def format_instant(instant) -> str:
    """ISO 8601 em UTC. A coluna guarda UTC sem fuso; aqui o fuso volta a ser dito."""
    return instant.replace(tzinfo=timezone.utc).isoformat()


class OperationDTO:

    @staticmethod
    def obj_to_dict(operation: Operation) -> dict:
        source_account = operation.source_account

        return {
            "operation_key": operation.operation_key,
            "type": operation.type,
            "source_account_key": source_account.account_key if source_account is not None else None,
            "destination_account_key": operation.destination_account.account_key,
            "amount": operation.amount,
            "fee_amount": operation.fee_amount,
            "completed_at": format_instant(operation.completed_at),
        }


class EntryDTO:

    @staticmethod
    def obj_to_dict(entry: Entry) -> dict:
        return {
            "entry_key": entry.entry_key,
            "operation_key": entry.operation.operation_key,
            "type": entry.type,
            "amount": entry.amount,
            "completed_at": format_instant(entry.operation.completed_at),
        }

    @staticmethod
    def list_obj_to_list_dict(entries: list) -> list:
        return [EntryDTO.obj_to_dict(entry) for entry in entries]
