import unittest
import conversations as c
from chapter02.task_lab import scripted_agent

class RefusalCorrectionTests(unittest.TestCase):
    def test_valid_policy_outcomes(self):
        # Both admitted policy branches, with direct and delayed clarification.
        for identity in ('A100', 'B200'):
            for persona in ('cooperative', 'literal', 'noisy'):
                with self.subTest(identity=identity, persona=persona):
                    card=c.load_card('clarify')
                    card['id']='clarify-'+identity+'-'+persona
                    card['user_reply']['order_id']=identity
                    if identity=='B200':
                        card['required_outcome']={'terminal':'refused','reason':'not_owned','refunds':[]}
                    c.validate_card(card)
                    row=c.run(card=card, persona=persona, choose=scripted_agent('corrected'), candidate='policy-aware')
                    self.assertEqual(row['outcome'],'completed')
                    self.assertEqual(len(row['checks']),6)
                    self.assertTrue(all(row['checks'].values()))
                    self.assertEqual(row['after']['refunds'],card['required_outcome']['refunds'])
                    schedule=[{k:row[k] for k in ('attempt_id','case_id','persona','candidate')}]
                    self.assertEqual(c.summary([row],scheduled=schedule)['completion_rate'],1)
                    self.assertEqual(row['turns']-row['questions'],2 if identity=='A100' else 1)

if __name__=='__main__': unittest.main()
