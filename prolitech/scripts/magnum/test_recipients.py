import unittest
from unittest.mock import patch
import monitor

class RecipientTests(unittest.TestCase):
    def test_legacy(self):
        with patch.object(monitor, 'telegram_one') as send:
            monitor.telegram({'chat_id': 1}, 'test')
            self.assertEqual(send.call_args[0][1], 1)

    def test_two_unique_recipients(self):
        with patch.object(monitor, 'telegram_one') as send:
            monitor.telegram({'chat_id': 1, 'chat_ids': [1,2,1]}, 'test')
            self.assertEqual([c[0][1] for c in send.call_args_list], [1,2])

    def test_attempts_second_after_failure(self):
        with patch.object(monitor, 'telegram_one', side_effect=[RuntimeError(), None]) as send:
            with self.assertRaises(RuntimeError):
                monitor.telegram({'chat_id': 1, 'chat_ids': [1,2]}, 'test')
            self.assertEqual(send.call_count, 2)

if __name__ == '__main__': unittest.main()
