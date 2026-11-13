import unittest
from cat_model import CatModel
from scene_model import SceneController

LIMITS=(0.,0.,900.,600.)

class EquipmentTests(unittest.TestCase):
    def setup_scene(self,kind='food'):
        s=SceneController();m=CatModel();m.satiety=m.thirst=30
        s.begin(kind,m,100,200,1,LIMITS)
        return s,m

    def test_devices_are_independent_and_stop_retains_all(self):
        s,m=self.setup_scene();feeder=s.feeder
        s.begin('water',m,100,200,1,LIMITS);fountain=s.fountain
        s.begin('snack',m,100,200,1,LIMITS)
        self.assertIs(s.feeder,feeder);self.assertIs(s.fountain,fountain)
        self.assertNotEqual(feeder.x,fountain.x)
        s.cancel(m)
        self.assertTrue(s.feeder and s.fountain and s.snack)
        s.put_away(m)
        self.assertIsNone(s.feeder);self.assertIsNone(s.fountain);self.assertIsNone(s.snack)

    def test_dispensing_does_not_feed_cat_remotely_or_duplicate_portions(self):
        s,m=self.setup_scene();f=s.feeder
        self.assertEqual(f.stock,7)
        for _ in range(6):s.update(.25,m,100,200,1,True,0)
        self.assertAlmostEqual(f.amount,1)
        self.assertEqual(m.satiety,30)
        self.assertFalse(f.dispense())
        self.assertEqual(f.stock,7)
        f.amount=0;self.assertTrue(f.dispense());self.assertEqual(f.stock,6)

    def test_empty_feeder_needs_refill_and_does_not_spawn_infinite_food(self):
        s,m=self.setup_scene();f=s.feeder
        s.cancel(m);f.dispensing=0;f.amount=0;f.stock=0
        self.assertFalse(s.begin('food',m,100,200,1,LIMITS))
        self.assertIsNone(s.activity)
        self.assertTrue(s.refill('food'));self.assertEqual(f.stock,8)
        self.assertTrue(s.begin('food',m,100,200,1,LIMITS))
        self.assertEqual(f.stock,7)

    def test_empty_water_and_treat_require_explicit_refill(self):
        for kind,attr in [('water','fountain'),('snack','snack')]:
            s,m=self.setup_scene(kind);obj=getattr(s,attr)
            s.cancel(m);obj.amount=0
            self.assertFalse(s.begin(kind,m,100,200,1,LIMITS))
            s.refill(kind);self.assertEqual(obj.amount,1)
            self.assertTrue(s.begin(kind,m,100,200,1,LIMITS))

    def test_contact_geometry_keeps_common_floor_and_correct_mouth_height(self):
        for kind in ['food','water','snack']:
            for scale in [.65,1.,1.5]:
                s=SceneController();m=CatModel();m.satiety=m.thirst=30
                s.begin(kind,m,300,200,scale,LIMITS)
                obj=s.bowl
                s.update(0,m,300,200,scale,True,0)
                x,y=s.destination or (300,200)
                offset=286 if s.direction>0 else 34
                self.assertLessEqual(abs(x+offset*scale-obj.x),4*scale)
                reference=39 if kind=='food' else 94
                self.assertLess(abs(y+286*scale-obj.contact_y-reference*scale),3*scale)
                self.assertAlmostEqual(obj.width/obj.height,obj.aspect)

    def test_moving_active_equipment_restarts_approach(self):
        s,m=self.setup_scene('water')
        s.update(0,m,100,200,1,True,0);x,y=s.destination
        s.update(0,m,x,y,1,True,0)
        self.assertEqual(s.activity.stage,'interact')
        s.fountain.x+=90
        s.update(.016,m,x,y,1,True,0)
        self.assertEqual(s.activity.stage,'approach');self.assertEqual(m.action,'walk')

    def test_touch_cancels_goal_while_device_finishes_dispensing(self):
        s,m=self.setup_scene();s.cancel();m.touch('head',.1)
        for _ in range(8):s.update(.2,m,100,200,1,True,0)
        self.assertEqual(m.action,'head');self.assertIsNone(s.activity)
        self.assertAlmostEqual(s.feeder.amount,1)

    def test_resuming_partial_portion_cannot_grant_more_than_remaining_food(self):
        s,m=self.setup_scene()
        for _ in range(6):s.update(.25,m,100,200,1,True,0)
        x,y=s.destination
        s.update(0,m,x,y,1,True,0)
        s.feeder.amount=.2;s.last_need=m.satiety
        initial=m.satiety;m.start('eat',7)
        for _ in range(35):
            m.tick(.1)
            s.update(.1,m,x,y,1,True,0)
        self.assertAlmostEqual(s.feeder.amount,0)
        self.assertLessEqual(m.satiety,initial+7.0001)
        self.assertNotEqual(m.action,'eat')

if __name__=='__main__':unittest.main()
