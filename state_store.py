"""Conflict-aware snapshots for legacy JSON state; no schema migration required."""
from copy import deepcopy


class StateConflict(Exception):
    pass


class StateSnapshot(list):
    def __init__(self, items):
        super().__init__(items)
        self.original = deepcopy(list(self))


def merge_records(current, snapshot):
    """Merge only edited fields; reject competing edits instead of losing data."""
    before = {item['id']: item for item in snapshot.original}
    desired = {item['id']: item for item in snapshot}
    live = {item['id']: deepcopy(item) for item in current}
    for key, old in before.items():
        if key not in desired:
            if key in live and live[key] != old:
                raise StateConflict('This record changed before it could be removed.')
            live.pop(key, None)
    for key, item in desired.items():
        old = before.get(key)
        if old is None:
            if key in live and live[key] != item:
                raise StateConflict('This record was created by another request.')
            live[key] = deepcopy(item)
            continue
        if item == old:
            continue
        if key not in live:
            raise StateConflict('This record was removed by another request.')
        for field in set(old) | set(item):
            if old.get(field) == item.get(field):
                continue
            actual = live[key].get(field)
            if field == 'activity':
                additions = [entry for entry in item.get(field, []) if entry not in old.get(field, [])]
                live[key][field] = (additions + [entry for entry in actual or [] if entry not in additions])[:80]
                continue
            if field not in {'updatedAt', 'lastActiveAt', 'lastActivity'} and actual != old.get(field) and actual != item.get(field):
                raise StateConflict('This record changed elsewhere. Reload it before saving again.')
            if field in item:
                live[key][field] = deepcopy(item[field])
            else:
                live[key].pop(field, None)
    emails = [item.get('email', '').casefold() for item in live.values() if item.get('email')]
    if len(emails) != len(set(emails)):
        raise StateConflict('An account with this email already exists.')
    return list(live.values())
