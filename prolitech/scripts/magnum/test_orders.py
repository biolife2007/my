import unittest
from unittest.mock import patch
from decimal import Decimal
import order_notify as n

class OrderTests(unittest.TestCase):
    def order(self, hid):
        return dict(order_history_id=hid, order_id=123, date_added='2026-09-23 12:34:56', total='100.125', currency_value='2', currency_code='UAH')

    def test_message_fields_and_currency(self):
        text = n.message('prolitech', self.order(1))
        for value in ['Пролітех', 'prolitech.com.ua', '123', '23.09.2026 12:34:56', '200,25 UAH']:
            self.assertIn(value, text)
        self.assertIn('ПроліМакс', n.message('prolimax', self.order(1)))

    def test_retry_skips_acknowledged_messages(self):
        state = {'prolitech': {'history_id': 10, 'delivered': []}}
        data = {'max_history_id': 12, 'orders': [self.order(11),self.order(12)]}
        with patch.object(n, 'read_orders', return_value=data), patch.object(n.time, 'sleep'), patch.object(n, 'telegram', side_effect=[None,RuntimeError('failure')]):
            with self.assertRaises(RuntimeError): n.process_site('prolitech',state,{},lambda:None)
        self.assertEqual(state['prolitech'], {'history_id':10,'delivered':[11]})
        with patch.object(n, 'read_orders', return_value=data), patch.object(n.time, 'sleep'), patch.object(n, 'telegram') as send:
            n.process_site('prolitech',state,{},lambda:None)
            self.assertEqual(send.call_count,1)
        self.assertEqual(state['prolitech'], {'history_id':12,'delivered':[]})

if __name__ == '__main__': unittest.main()
