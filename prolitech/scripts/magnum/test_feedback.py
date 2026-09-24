import unittest
from unittest.mock import patch
import feedback_notify as f

class FeedbackTests(unittest.TestCase):
    def row(self,answer=''):
        return dict(id=1,kind='question',date_added='2026-09-24 12:30:00',date_modified='2026-09-24 13:45:00',answer_hash=answer)
    def test_baseline_no_history_or_moderation_duplicates(self):
        r=self.row('a');state=f.baseline([r])
        r['date_modified']='2026-09-24 14:00:00'
        with patch.object(f,'telegram') as send:
            self.assertEqual(f.process('prolitech',[r],state,{},lambda:None),0)
            send.assert_not_called()
    def test_question_answer_change_and_retry(self):
        state={};r=self.row('a')
        with patch.object(f.time,'sleep'),patch.object(f,'telegram',side_effect=[None,RuntimeError()]):
            with self.assertRaises(RuntimeError):f.process('prolitech',[r],state,{},lambda:None)
        self.assertTrue(state['question:1']['seen']);self.assertEqual(state['question:1']['answer_hash'],'')
        with patch.object(f.time,'sleep'),patch.object(f,'telegram') as send:
            self.assertEqual(f.process('prolitech',[r],state,{},lambda:None),1)
            self.assertIn('Відповідь на питання',send.call_args[0][1])
            self.assertEqual(f.process('prolitech',[r],state,{},lambda:None),0)
            r['answer_hash']='b'
            self.assertEqual(f.process('prolitech',[r],state,{},lambda:None),1)
    def test_format(self):
        self.assertEqual(f.message('prolimax','blog','2026-09-24 12:30:00'),'24.09.2026, 12:30 | Коментар блогу | ПроліМакс')
if __name__=='__main__':unittest.main()
