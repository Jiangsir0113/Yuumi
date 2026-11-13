import math
import unittest
from cat_model import CatModel
from scene_model import SceneController,Ball,Scratcher

LIMITS=(0.,0.,900.,600.)

class SceneTests(unittest.TestCase):
    def scene(self,kind):
        model=CatModel();model.satiety=40
        scene=SceneController();scene.begin(kind,model,100,200,1,LIMITS)
        return scene,model

    def arrive(self,scene,model):
        scene.update(.016,model,100,200,1,True,0)
        x,y=scene.destination
        scene.update(.016,model,x,y,1,True,0)
        return x,y

    def test_repeated_feed_does_not_move_bowl_or_reset_approach(self):
        s,m=self.scene('food');bowl=s.bowl
        s.update(.2,m,100,200,1,True,0)
        elapsed=s.activity.elapsed
        self.assertFalse(s.begin('food',m,150,200,1,LIMITS))
        self.assertIs(s.bowl,bowl)
        self.assertEqual(s.activity.elapsed,elapsed)

    def test_food_cannot_begin_remotely_due_to_timeout(self):
        s,m=self.scene('food');initial=m.satiety
        for _ in range(80):
            s.update(.2,m,100,200,1,True,0)
            m.tick(.2)
        self.assertEqual(s.activity.stage,'approach')
        self.assertLess(m.satiety,initial)
        self.assertEqual(s.bowl.amount,1)

    def test_cancelled_food_never_replaces_new_touch(self):
        s,m=self.scene('food');s.cancel();m.touch('head',.2)
        for _ in range(50):s.update(.1,m,100,200,1,True,0)
        self.assertIsNone(s.activity)
        self.assertEqual(m.action,'head')
        self.assertIsNotNone(s.bowl)

    def test_bowl_consumes_only_after_arrival_and_actual_intake(self):
        s,m=self.scene('food');x,y=self.arrive(s,m)
        self.assertEqual(m.action,'sniff')
        m.tick(2)
        m.tick(1)
        s.update(.016,m,x,y,1,True,0)
        self.assertLess(s.bowl.amount,1)
        self.assertGreater(s.bowl.amount,.7)

    def test_ball_friction_bounce_and_dynamic_destination(self):
        ball=Ball(1190,400,160)
        ball.step(.2,0,1200)
        self.assertLess(ball.velocity,0)
        before=abs(ball.velocity);ball.step(.2,0,1200)
        self.assertLess(abs(ball.velocity),before)
        s,m=self.scene('ball')
        s.update(.1,m,100,200,1,True,0);first=s.destination
        s.ball.x+=80
        s.update(.1,m,100,200,1,True,0)
        self.assertNotEqual(s.destination,first)

    def test_rope_and_track_are_separate_and_stop_preserves_prop(self):
        s,m=self.scene('scratch');x,y=self.arrive(s,m)
        s.update(.016,m,x,y,1,True,.7)
        self.assertEqual(s.scratcher.scratches,1)
        self.assertEqual(s.scratcher.taps,0)
        s.cancel(m)
        self.assertIsNotNone(s.scratcher)
        s.begin('track',m,x,y,1,LIMITS)
        x,y=self.arrive(s,m)
        s.update(.016,m,x,y,1,True,.65)
        self.assertGreater(s.scratcher.taps,0)
        self.assertEqual(s.scratcher.scratches,1)

    def test_track_balls_remain_on_circle_and_slow_down(self):
        s=Scratcher(100,500)
        s.impulse(0,4)
        start=s.angles[0]
        for _ in range(300):s.step(1/64)
        self.assertNotEqual(start,s.angles[0])
        self.assertTrue(all(abs(w)<4 for w in s.speeds))
        for i in range(3):
            x,y=s.ball_position(i)
            ellipse=((x-s.x-s.width*.5)/(s.width*.365))**2+((y-s.y-s.height*.935)/(s.height*.035))**2
            self.assertAlmostEqual(ellipse,1,places=5)

    def test_moving_scratcher_updates_destination(self):
        s,m=self.scene('scratch')
        s.update(.1,m,100,200,1,True,0);before=s.destination
        s.scratcher.x+=100;s.scratcher.floor-=50
        s.update(.1,m,100,200,1,True,0)
        self.assertNotEqual(before,s.destination)

    def test_wand_respects_distance_and_can_be_cancelled(self):
        s,m=self.scene('wand')
        for _ in range(20):s.update(.1,m,100,200,1,True,0,pointer=(2000,2000))
        self.assertEqual(s.activity.stage,'watch')
        for _ in range(20):s.update(.1,m,100,200,1,True,0,pointer=(330,350))
        self.assertEqual(s.activity.stage,'pounce')
        s.cancel(m)
        for _ in range(20):s.update(.1,m,100,200,1,True,0,pointer=(330,350))
        self.assertEqual(m.action,'idle')
        self.assertIsNone(s.activity)

if __name__=='__main__':unittest.main()
