import unittest
from qa.gaps import track_gaps


class GapTests(unittest.TestCase):
    def report(self, status='FAIL'):
        return {'target': 'local', 'gaps': track_gaps([{'name': 'Charts', 'status': status, 'detail': 'fixture'}], observed_at='first')}

    def test_same_check_pass_resolves(self):
        result = track_gaps([{'name': 'Charts', 'status': 'PASS', 'detail': 'rerun'}], self.report(), observed_at='second')[0]
        self.assertEqual(result['status'], 'RESOLVED')
        self.assertEqual(result['first_seen'], 'first')
        self.assertEqual(result['observations'], 2)

    def test_omitted_check_is_never_resolved(self):
        self.assertEqual(track_gaps([], self.report())[0]['status'], 'NEEDS_VERIFICATION')

    def test_unverified_is_never_resolved(self):
        result = track_gaps([{'name': 'Charts', 'status': 'UNVERIFIED', 'detail': 'no browser'}], self.report())[0]
        self.assertEqual(result['status'], 'NEEDS_VERIFICATION')

    def test_different_target_cannot_resolve(self):
        self.assertEqual(track_gaps([{'name': 'Charts', 'status': 'PASS', 'detail': 'local only'}], self.report(), target='https://celesys.ai'), [])

    def test_resolved_gap_can_reopen(self):
        result = self.report()
        result['gaps'][0]['status'] = 'RESOLVED'
        self.assertEqual(track_gaps([{'name': 'Charts', 'status': 'FAIL', 'detail': 'regressed'}], result)[0]['status'], 'OPEN')

    def test_new_passing_check_is_not_gap(self):
        self.assertEqual(self.report('PASS')['gaps'], [])
