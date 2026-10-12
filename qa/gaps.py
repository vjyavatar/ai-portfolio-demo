"""Evidence-based regression memory; never edits source or certifies omitted checks."""
import hashlib


def track_gaps(checks, previous=None, *, target='local', observed_at=''):
    previous = previous or {}
    # An observation against another target cannot close a production issue.
    old = previous.get('gaps', []) if previous.get('target') == target else []
    known = {g['id']: dict(g) for g in old}
    seen = set()
    for check in checks:
        key = hashlib.sha256((target + '\n' + check['name']).encode()).hexdigest()[:16]
        seen.add(key)
        status = check['status']
        if status == 'PASS' and key not in known:
            continue
        gap = known.get(key, {'id': key, 'check': check['name'], 'first_seen': observed_at, 'observations': 0})
        gap.update(last_seen=observed_at, observations=gap['observations'] + 1,
                   status={'PASS': 'RESOLVED', 'FAIL': 'OPEN', 'UNVERIFIED': 'NEEDS_VERIFICATION'}[status],
                   evidence=check['detail'], last_check_status=status)
        known[key] = gap
    for key, gap in known.items():
        if key not in seen:
            gap.update(status='NEEDS_VERIFICATION', last_check_status='NOT_RUN',
                       evidence='Previously tracked check was not run; no resolution inferred.')
    return sorted(known.values(), key=lambda gap: (gap['status'] == 'RESOLVED', gap['check']))
