from pathlib import Path
import unittest
import numpy as np
import threading
from unittest.mock import patch
from animation_engine import Animator,PostureGraph,EDGES

ASSETS=Path(__file__).resolve().parents[1]/"assets"


class PostureTests(unittest.TestCase):
    def test_turn_stays_on_standing_edge(self):
        graph=PostureGraph();graph.node='stand_right';graph.set_goal('stand_left',True)
        nodes=[]
        for _ in range(50):
            graph.advance(1/64)
            nodes.append(graph.node)
            self.assertNotIn(graph.edge,{'stand_right','stand_left'})
        self.assertTrue(graph.ready)
        self.assertEqual(graph.node,'stand_left')
        self.assertNotIn('sit',nodes)

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

    def test_target_phase_waits_for_structural_entry(self):
        a=self.animator;a.reset_for_test('sleep')
        a.update('stretch',0,urgent=True)
        for _ in range(12):a.update('stretch',1/64,urgent=True)
        self.assertFalse(a.graph.ready)
        self.assertEqual(a.phase,0)
        for _ in range(100):a.update('stretch',1/64,urgent=True)
        self.assertTrue(a.graph.ready)
        self.assertGreater(a.phase,0)

    def test_dynamic_optical_flow_is_never_on_calling_thread(self):
        import animation_engine as engine
        original=engine.PixelBlend
        threads=[]
        class Checked(original):
            def __init__(self,*args):
                threads.append(threading.current_thread().name)
                super().__init__(*args)
        with patch.object(engine,'PixelBlend',Checked):
            a=self.animator;a.reset_for_test('idle')
            a.update('head',0)
            if a.flow_future:a.flow_future.result(timeout=5)
        self.assertTrue(threads)
        self.assertTrue(all(name.startswith('Youmi-blend') for name in threads))

    def test_large_delta_has_same_visual_clock_as_simulation(self):
        a=self.animator;a.reset_for_test('walk',.4)
        before=a.phase
        a.update('walk',.2)
        self.assertAlmostEqual(a.phase-before,.2,places=5)


if __name__=="__main__":
    unittest.main()
