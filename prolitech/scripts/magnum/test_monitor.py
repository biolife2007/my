import unittest
from unittest.mock import patch
import monitor

URL = 'https://hmel-master.com/p1-test.html'


class MonitorTests(unittest.TestCase):
    def test_only_repeated_404_is_missing(self):
        for statuses, expected in [([404,404], 'missing'), ([404,200], 'exists'), ([500,404], 'unknown'), ([404,503], 'unknown'), ([403], 'unknown'), ([410], 'unknown'), ([None,None], 'unknown'), ([200], 'exists')]:
            with self.subTest(statuses=statuses), patch.object(monitor, 'request_status', side_effect=statuses), patch.object(monitor.time, 'sleep'):
                self.assertEqual(monitor.check_url(URL)['status'], expected)

    def test_no_duplicates_and_recovery_rearms_alert(self):
        products = [{'url': URL, 'sku': 'A', 'name': '<item>'}]
        results = {URL: {'status': 'missing'}}
        state = monitor.update_state({}, results)
        self.assertEqual(len(list(monitor.alert_groups(products, results, state))), 1)
        state[URL]['notified'] = True
        state = monitor.update_state(state, results)
        self.assertEqual(list(monitor.alert_groups(products, results, state)), [])
        state = monitor.update_state(state, {URL: {'status': 'unknown'}})
        self.assertTrue(state[URL]['notified'])
        state = monitor.update_state(state, {URL: {'status': 'exists'}})
        state = monitor.update_state(state, results)
        self.assertEqual(len(list(monitor.alert_groups(products, results, state))), 1)

    def test_duplicate_urls_combine_and_escape(self):
        p = {'url': URL, 'sku': 'A', 'name': '<item>'}
        messages = list(monitor.alert_groups([p,p], {URL: {'status':'missing'}}, {URL:{'notified':False}}))
        self.assertEqual(len(messages), 1)
        self.assertIn('&lt;item&gt;', messages[0][1])

    def test_rejects_other_hosts(self):
        for url in ['http://127.0.0.1', 'file:///etc/passwd', 'https://hmel-master.com.evil.com/', 'https://hmel-master.com:22/', 'https://x:y@hmel-master.com/']:
            with self.assertRaises(ValueError): monitor.validate_url(url)


if __name__ == '__main__': unittest.main()
