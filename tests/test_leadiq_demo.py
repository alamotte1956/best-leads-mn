import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import unittest
from app import app,db,RewardCredit,RewardSpin,RewardMonth,Delivery


class LeadIQDemoTests(unittest.TestCase):
    def setUp(self):
        self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all()
        self.client=app.test_client()

    def tearDown(self):
        db.session.remove();self.ctx.pop()

    def test_public_demo_is_read_only_and_real_rewards_stay_closed(self):
        for _ in range(3):
            response=self.client.get('/leadiq-demo')
            self.assertEqual(response.status_code,200)
            self.assertIn('INTERACTIVE DEMO',response.text)
            self.assertIn('no discounts, credits or rewards are issued',response.text)
        self.assertEqual(self.client.post('/leadiq-demo').status_code,405)
        for action in ('spin','free-entry','redeem'):
            self.assertEqual(self.client.post('/contractor/rewards/'+action,json={'demo':True,'prize_index':0}).status_code,503)
        for model in (RewardCredit,RewardSpin,RewardMonth,Delivery):
            self.assertEqual(model.query.count(),0)
