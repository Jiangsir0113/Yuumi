from pathlib import Path
import unittest
import numpy as np
from animation_engine import Animator,PostureGraph,EDGES

ASSETS=Path(__file__).resolve().parents[1]/"assets"


class PostureTests(unittest.TestCase):
    def test_reverses_current_edge_without_finishing_old_goal(self):
        graph=PostureGraph()
        graph.set_goal("stand_right",True)
        for _ in range(12):
            graph.advance(1/64)
        before=graph.progress
        self.assertGreater(before,0)
        self.assertLess(before,.8)
        graph.set_goal("sit",True)
        graph.advance(0)
        self.assertEqual(before,graph.progress)
        max_progress=before
        for _ in range(80):
            graph.advance(1/64)
            if graph.edge:
                max_progress=max(max_progress,graph.progress)
        self.assertTrue(graph.ready)
        self.assertEqual(graph.node,"sit")
        self.assertLess(max_progress,.9)

    def test_every_posture_can_reach_every_other_posture(self):
        nodes={node for edge in EDGES.values() for node in edge[:2]}
        for start in nodes:
            for goal in nodes:
                graph=PostureGraph()
                graph.node=start
                graph.set_goal(goal,True)
                for _ in range(160):
                    graph.advance(1/64)
                self.assertTrue(graph.ready,(start,goal))


class AnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.animator=Animator(ASSETS)

    @classmethod
    def tearDownClass(cls):
        cls.animator.close()

    def test_all_assets_are_60fps_or_more_and_removed_clips_absent(self):
        for name,info in self.animator.bank.info.items():
            self.assertGreaterEqual(info["fps"],60,name)
            self.assertGreaterEqual(info["output_frames"]/info["duration"],60,name)
        for name in ["roll","belly","side_sleep"]:
            self.assertNotIn(name,self.animator.bank.info)
            self.assertNotIn(name,self.animator.bank.source_info)

    def test_interrupt_is_pixel_continuous_even_during_existing_blend(self):
        a=self.animator
        a.reset_for_test("idle",.4)
        for goal in ["head","chin","back","head","sleep","groom"]:
            previous=a.last.copy()
            first=a.update(goal,0,urgent=True)
            self.assertTrue(np.array_equal(previous,first),goal)
            for _ in range(5):
                a.update(goal,1/64,urgent=True)
        self.assertGreater(a.interruptions,0)

    def test_walking_to_trot_retains_gait_phase(self):
        a=self.animator
        a.reset_for_test("walk",.55)
        old=a.phase
        a.update("trot",0)
        self.assertAlmostEqual(a.phase,old)
        a.update("trot",1/64)
        self.assertGreater(a.phase,old)
        self.assertLess(a.phase_speed,1.65)

    def test_local_action_enters_nearest_pose_instead_of_restarting(self):
        a=self.animator
        a.reset_for_test("head",.7)
        expected=a.bank.nearest_phase("chin",a.last)
        previous=a.last.copy()
        a.update("chin",0)
        self.assertAlmostEqual(a.phase,expected)
        self.assertTrue(np.array_equal(previous,a.last))


if __name__=="__main__":
    unittest.main()
